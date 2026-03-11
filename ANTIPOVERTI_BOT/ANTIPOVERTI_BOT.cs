using System;
using System.IO;
using System.Linq;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots;

[Robot(AccessRights = AccessRights.FullAccess, AddIndicators = true)]
public class ANTIPOVERTI_BOT : Robot
{
    // ═══════════════════════════════════════════════════════════
    //  PARAMETERS (visible in cTrader UI)
    // ═══════════════════════════════════════════════════════════

    // ─── Connection ──────────────────────────────────────────
    [Parameter("Engine Host", DefaultValue = "127.0.0.1", Group = "Connection")]
    public string EngineHost { get; set; }

    [Parameter("Engine Port", DefaultValue = 5555, Group = "Connection")]
    public int EnginePort { get; set; }

    // ─── Trade Parameters ────────────────────────────────────
    // [Parameter("Risk Per Trade (%)", ...)]
    public double RiskPercent { get; set; } = 1.0;

    // [Parameter("Min Confidence", ...)]
    public double MinConfidence { get; set; } = 0.01;

    // [Parameter("TP Multiplier", ...)]
    public double TpMultiplier { get; set; } = 8.0;

    // [Parameter("SL Multiplier", ...)]
    public double SlMultiplier { get; set; } = 4.0;

    // [Parameter("Cooldown (sec)", ...)]
    public int CooldownSeconds { get; set; } = 5;

    // [Parameter("Auto-Trade Enabled", ...)]
    public bool AutoTradeEnabled { get; set; } = true;

    // ─── CAPITAL PROTECTION ──────────────────────────────────
    // [Parameter("Daily Loss Limit (%)", ...)]
    public double DailyLossLimitPercent { get; set; } = 50.0; // Szeroki limit testowy

    // [Parameter("Max Drawdown (%)", ...)]
    public double MaxDrawdownPercent { get; set; } = 50.0; // Szeroki limit testowy

    // [Parameter("Max Consecutive Losses", ...)]
    public int MaxConsecutiveLosses { get; set; } = 50; // Szeroki limit testowy

    // ─── Constants ───────────────────────────────────────────
    private const string BotLabel = "ANTIPOVERTI";

    // ═══════════════════════════════════════════════════════════
    //  STATE
    // ═══════════════════════════════════════════════════════════

    private TcpClient _tcpClient;
    private CancellationTokenSource _cts;
    private DateTime _lastTradeTime = DateTime.MinValue;
    private string _currentPosition = "FLAT";

    // ─── Capital Protection State ────────────────────────────
    private double _sessionStartEquity;
    private double _sessionPeakEquity;
    private double _sessionRealizedPnl;
    private int _consecutiveLosses;
    private int _sessionTradeCount;
    private int _sessionWins;
    private int _sessionLosses;
    private bool _circuitBreakerTripped;
    private string _circuitBreakerReason = "";
    private bool _botActive = true;  // ON/OFF toggle state
    private bool _engineActive = true;  // Engine ON/OFF toggle

    // ─── UI Elements ─────────────────────────────────────────
    private TextBlock _statusText;
    private TextBlock _bidAskText;
    private TextBlock _metricsText;
    private TextBlock _signalText;
    private TextBlock _positionText;
    private TextBlock _tradeText;
    private TextBlock _protectionText;
    private Button _toggleButton;
    private Button _engineButton;

    // ─── Latest Engine Data ──────────────────────────────────
    private double _lastBid, _lastAsk, _lastSpread, _lastMid;
    private double _lastObi5, _lastObi10;
    private double _lastBidWall, _lastAskWall;
    private double _lastVolDelta, _lastPriceDelta;
    private long _lastTradeCount;
    private string _lastAiBias = "NEUTRAL";
    private double _lastAiConf = 0.0;

    // ═══════════════════════════════════════════════════════════
    //  LIFECYCLE
    // ═══════════════════════════════════════════════════════════

    protected override void OnStart()
    {
        // Initialize capital protection tracking
        _sessionStartEquity = Account.Equity;
        _sessionPeakEquity = Account.Equity;
        _sessionRealizedPnl = 0;
        _consecutiveLosses = 0;
        _sessionTradeCount = 0;
        _sessionWins = 0;
        _sessionLosses = 0;
        _circuitBreakerTripped = false;

        // Listen for position closes to track P&L
        Positions.Closed += OnPositionClosed;

        BuildUI();
        _cts = new CancellationTokenSource();
        Task.Run(() => ConnectToEngineAsync());

        // Start a 1 second timer to ensure UI updates even on slow markets
        Timer.Start(1);

        Print($"[PROTECTION] Session started | Equity: ${_sessionStartEquity:F2} | " +
              $"Daily Limit: {DailyLossLimitPercent}% | Max DD: {MaxDrawdownPercent}% | " +
              $"Max Consec. Losses: {MaxConsecutiveLosses}");
    }

    protected override void OnTick()
    {
        // Track peak equity for drawdown calculation
        if (Account.Equity > _sessionPeakEquity)
            _sessionPeakEquity = Account.Equity;
    }

    protected override void OnTimer()
    {
        if (!_engineActive) return;  // Skip chart drawing when engine is off
        // Draw visuals on a 1s timer to guarantee cTrader renders them even without incoming broker price ticks
        UpdateChartVisuals();
    }

    protected override void OnStop()
    {
        Positions.Closed -= OnPositionClosed;

        BeginInvokeOnMainThread(() =>
        {
            _statusText.Text = "🔴 ENGINE: Stopped";
            _statusText.ForegroundColor = Color.Red;
        });

        _cts?.Cancel();
        _cts?.Dispose();
        _tcpClient?.Dispose();

        Print($"[SESSION END] Trades: {_sessionTradeCount} | W/L: {_sessionWins}/{_sessionLosses} | " +
              $"P&L: ${_sessionRealizedPnl:F2} | Final Equity: ${Account.Equity:F2}");
    }

    // ═══════════════════════════════════════════════════════════
    //  CAPITAL PROTECTION ENGINE
    // ═══════════════════════════════════════════════════════════

    private void OnPositionClosed(PositionClosedEventArgs args)
    {
        var pos = args.Position;
        if (pos.Label != BotLabel) return;

        double pnl = pos.NetProfit;
        _sessionRealizedPnl += pnl;
        _sessionTradeCount++;

        if (pnl >= 0)
        {
            _sessionWins++;
            _consecutiveLosses = 0;
        }
        else
        {
            _sessionLosses++;
            _consecutiveLosses++;
        }

        Print($"[P&L] Trade closed: ${pnl:F2} | Session: ${_sessionRealizedPnl:F2} | " +
              $"W/L: {_sessionWins}/{_sessionLosses} | Consec.Losses: {_consecutiveLosses}");

        // Check circuit breakers after every close
        CheckCircuitBreakers();
    }

    private void CheckCircuitBreakers()
    {
        if (_circuitBreakerTripped) return;

        // 1. Daily Loss Limit
        double dailyLossLimit = _sessionStartEquity * (DailyLossLimitPercent / 100.0);
        if (_sessionRealizedPnl < 0 && Math.Abs(_sessionRealizedPnl) >= dailyLossLimit)
        {
            TripCircuitBreaker($"DAILY LOSS LIMIT hit (${_sessionRealizedPnl:F2} ≥ ${dailyLossLimit:F2})");
            return;
        }

        // 2. Max Drawdown from Peak
        double drawdownPercent = (_sessionPeakEquity - Account.Equity) / _sessionPeakEquity * 100;
        if (drawdownPercent >= MaxDrawdownPercent)
        {
            TripCircuitBreaker($"MAX DRAWDOWN hit ({drawdownPercent:F1}% ≥ {MaxDrawdownPercent}%)");
            return;
        }

        // 3. Max Consecutive Losses
        if (_consecutiveLosses >= MaxConsecutiveLosses)
        {
            TripCircuitBreaker($"MAX CONSECUTIVE LOSSES hit ({_consecutiveLosses} ≥ {MaxConsecutiveLosses})");
            return;
        }
    }

    private void TripCircuitBreaker(string reason)
    {
        _circuitBreakerTripped = true;
        _circuitBreakerReason = reason;

        // Immediately close all positions
        CloseAllPositions();

        Print($"[🚨 CIRCUIT BREAKER] {reason}");
        Print("[🚨 CIRCUIT BREAKER] ALL TRADING HALTED. Restart bot to reset.");

        BeginInvokeOnMainThread(() =>
        {
            _protectionText.Text = $"🚨 HALTED: {reason}";
            _protectionText.ForegroundColor = Color.Red;
            _tradeText.Text = "⛔ TRADING DISABLED BY CIRCUIT BREAKER";
            _tradeText.ForegroundColor = Color.Red;
        });
    }

    // ═══════════════════════════════════════════════════════════
    //  UI
    // ═══════════════════════════════════════════════════════════

    private void BuildUI()
    {
        _statusText = new TextBlock
        {
            Text = "🔴 ENGINE: Disconnected",
            ForegroundColor = Color.Red,
            Margin = new Thickness(10, 5, 10, 0),
            FontWeight = FontWeight.ExtraBold,
            FontSize = 13
        };

        _bidAskText = new TextBlock
        {
            Text = "BID: --- | ASK: --- | Spread: ---",
            ForegroundColor = Color.White,
            Margin = new Thickness(10, 2, 10, 0),
            FontSize = 12
        };

        _metricsText = new TextBlock
        {
            Text = "OBI: --- | Walls: --- | VolΔ: ---",
            ForegroundColor = Color.DodgerBlue,
            Margin = new Thickness(10, 2, 10, 0),
            FontSize = 11
        };

        _signalText = new TextBlock
        {
            Text = "AI SIGNAL: WAITING",
            ForegroundColor = Color.Gray,
            Margin = new Thickness(10, 2, 10, 0),
            FontWeight = FontWeight.Bold,
            FontSize = 14
        };

        _positionText = new TextBlock
        {
            Text = "POS: FLAT | P&L: $0.00",
            ForegroundColor = Color.White,
            Margin = new Thickness(10, 2, 10, 0),
            FontSize = 12
        };

        _tradeText = new TextBlock
        {
            Text = AutoTradeEnabled ? "⚡ AUTO-TRADE: ON" : "🔒 AUTO-TRADE: OFF (display only)",
            ForegroundColor = AutoTradeEnabled ? Color.Gold : Color.DarkGray,
            Margin = new Thickness(10, 2, 10, 0),
            FontSize = 11
        };

        _protectionText = new TextBlock
        {
            Text = $"🛡 PROTECTION: Loss<{DailyLossLimitPercent}% | DD<{MaxDrawdownPercent}% | Streak<{MaxConsecutiveLosses}",
            ForegroundColor = Color.FromArgb(255, 100, 200, 100),
            Margin = new Thickness(10, 2, 10, 5),
            FontSize = 10
        };

        _toggleButton = new Button
        {
            Text = "⏸  PAUSE BOT",
            FontSize = 13,
            FontWeight = FontWeight.ExtraBold,
            Margin = new Thickness(10, 6, 10, 6),
            Padding = new Thickness(16, 6, 16, 6),
            BackgroundColor = Color.FromArgb(255, 200, 60, 60),
            ForegroundColor = Color.White,
            HorizontalAlignment = HorizontalAlignment.Stretch
        };
        _toggleButton.Click += OnToggleButtonClick;

        _engineButton = new Button
        {
            Text = "⚙  ENGINE: ON",
            FontSize = 11,
            FontWeight = FontWeight.Bold,
            Margin = new Thickness(10, 2, 10, 6),
            Padding = new Thickness(12, 4, 12, 4),
            BackgroundColor = Color.FromArgb(255, 50, 120, 180),
            ForegroundColor = Color.White,
            HorizontalAlignment = HorizontalAlignment.Stretch
        };
        _engineButton.Click += OnEngineButtonClick;

        var panel = new StackPanel
        {
            Orientation = Orientation.Vertical,
            HorizontalAlignment = HorizontalAlignment.Left,
            VerticalAlignment = VerticalAlignment.Top,
            BackgroundColor = Color.FromArgb(220, 10, 10, 30),
            Margin = new Thickness(5)
        };

        panel.AddChild(_statusText);
        panel.AddChild(_toggleButton);
        panel.AddChild(_engineButton);
        panel.AddChild(_bidAskText);
        panel.AddChild(_metricsText);
        panel.AddChild(_signalText);
        panel.AddChild(_positionText);
        panel.AddChild(_tradeText);
        panel.AddChild(_protectionText);
        Chart.AddControl(panel);
    }

    private void OnToggleButtonClick(ButtonClickEventArgs args)
    {
        _botActive = !_botActive;

        if (_botActive)
        {
            // RESUME
            _toggleButton.Text = "⏸  PAUSE BOT";
            _toggleButton.BackgroundColor = Color.FromArgb(255, 200, 60, 60);
            _tradeText.Text = "⚡ AUTO-TRADE: RESUMED";
            _tradeText.ForegroundColor = Color.Gold;
            Print("[BOT] ▶ Bot RESUMED — trading active.");
        }
        else
        {
            // PAUSE — close all open positions for safety
            CloseAllPositions();
            _toggleButton.Text = "▶  START BOT";
            _toggleButton.BackgroundColor = Color.FromArgb(255, 40, 160, 60);
            _tradeText.Text = "⏸ BOT PAUSED — no trades";
            _tradeText.ForegroundColor = Color.DarkGray;
            Print("[BOT] ⏸ Bot PAUSED — all positions closed, trading halted.");
        }
    }

    private void OnEngineButtonClick(ButtonClickEventArgs args)
    {
        _engineActive = !_engineActive;

        if (_engineActive)
        {
            // Restart engine connection
            _cts = new CancellationTokenSource();
            Task.Run(() => ConnectToEngineAsync());
            Timer.Start(1);

            _engineButton.Text = "⚙  ENGINE: ON";
            _engineButton.BackgroundColor = Color.FromArgb(255, 50, 120, 180);
            _statusText.Text = "🔄 ENGINE: Reconnecting...";
            _statusText.ForegroundColor = Color.Orange;
            Print("[ENGINE] ▶ Engine STARTED — reconnecting to data stream.");
        }
        else
        {
            // Stop engine: cancel TCP, stop timer, clear chart lines
            _cts?.Cancel();
            _cts?.Dispose();
            _tcpClient?.Dispose();
            _tcpClient = null;
            Timer.Stop();

            // Also pause trading
            if (_botActive)
            {
                _botActive = false;
                CloseAllPositions();
                _toggleButton.Text = "▶  START BOT";
                _toggleButton.BackgroundColor = Color.FromArgb(255, 40, 160, 60);
            }

            _engineButton.Text = "⚙  ENGINE: OFF";
            _engineButton.BackgroundColor = Color.FromArgb(255, 80, 80, 80);
            _statusText.Text = "⏹ ENGINE: Stopped (saving CPU)";
            _statusText.ForegroundColor = Color.DarkGray;
            _tradeText.Text = "💤 ALL PROCESSES PAUSED";
            _tradeText.ForegroundColor = Color.DarkGray;

            // Clear chart lines
            Chart.RemoveObject("Z_MidPrice");
            Chart.RemoveObject("Z_BidPrice");
            Chart.RemoveObject("Z_AskPrice");
            Chart.RemoveObject("Z_ChartBid");

            Print("[ENGINE] ⏹ Engine STOPPED — TCP disconnected, timer off, CPU saved.");
        }
    }

    // ═══════════════════════════════════════════════════════════
    //  TCP CONNECTION
    // ═══════════════════════════════════════════════════════════

    private async Task ConnectToEngineAsync()
    {
        while (!_cts.IsCancellationRequested)
        {
            try
            {
                _tcpClient = new TcpClient();
                await _tcpClient.ConnectAsync(EngineHost, EnginePort);

                BeginInvokeOnMainThread(() =>
                {
                    _statusText.Text = "🟢 ENGINE: Connected";
                    _statusText.ForegroundColor = Color.LimeGreen;
                });
                Print($"Connected to HFT Engine at {EngineHost}:{EnginePort}");

                using var stream = _tcpClient.GetStream();
                using var reader = new StreamReader(stream, Encoding.UTF8);

                while (!_cts.IsCancellationRequested)
                {
                    string line = await reader.ReadLineAsync();
                    if (line == null) break;
                    ProcessEngineMessage(line);
                }

                Print("Engine stream ended. Reconnecting...");
            }
            catch (OperationCanceledException) { break; }
            catch (Exception ex) { Print($"Engine connection error: {ex.Message}"); }
            finally
            {
                _tcpClient?.Dispose();
                _tcpClient = null;
            }

            BeginInvokeOnMainThread(() =>
            {
                _statusText.Text = "🔴 ENGINE: Reconnecting...";
                _statusText.ForegroundColor = Color.Orange;
            });

            await Task.Delay(2000);
        }
    }

    // ═══════════════════════════════════════════════════════════
    //  MESSAGE PROCESSING
    // ═══════════════════════════════════════════════════════════

    private void ProcessEngineMessage(string json)
    {
        try
        {
            using JsonDocument doc = JsonDocument.Parse(json);
            var root = doc.RootElement;

            _lastBid = root.GetProperty("bid").GetDouble();
            _lastAsk = root.GetProperty("ask").GetDouble();
            _lastSpread = root.GetProperty("spread").GetDouble();
            _lastMid = root.GetProperty("mid").GetDouble();
            _lastObi5 = root.GetProperty("obi5").GetDouble();
            _lastObi10 = root.GetProperty("obi10").GetDouble();
            _lastBidWall = root.GetProperty("bidWall").GetDouble();
            _lastAskWall = root.GetProperty("askWall").GetDouble();
            _lastVolDelta = root.GetProperty("vDelta").GetDouble();
            _lastPriceDelta = root.GetProperty("pDelta").GetDouble();
            _lastTradeCount = root.GetProperty("trades").GetInt64();

            if (root.TryGetProperty("aiBias", out JsonElement biasEl))
                _lastAiBias = biasEl.GetString() ?? "NEUTRAL";
            if (root.TryGetProperty("aiConf", out JsonElement confEl))
                _lastAiConf = confEl.GetDouble();

            BeginInvokeOnMainThread(() =>
            {
                UpdateSignalUI();
                UpdatePositionUI();
                UpdateProtectionUI();

                if (_botActive && AutoTradeEnabled && !_circuitBreakerTripped)
                    EvaluateAndExecuteTrade();
            });
        }
        catch (Exception ex)
        {
            Print($"JSON parse error: {ex.Message}");
        }
    }

    // ═══════════════════════════════════════════════════════════
    //  UI UPDATES
    // ═══════════════════════════════════════════════════════════

    private void UpdateSignalUI()
    {
        string signal;
        Color signalColor;

        switch (_lastAiBias)
        {
            case "BULLISH":
                signal = $"⬆ BULLISH ({_lastAiConf:P0})";
                signalColor = Color.LimeGreen;
                break;
            case "BEARISH":
                signal = $"⬇ BEARISH ({_lastAiConf:P0})";
                signalColor = Color.Red;
                break;
            default:
                signal = "◼ NEUTRAL";
                signalColor = Color.Gray;
                break;
        }

        _bidAskText.Text = $"BID: {_lastBid:F2} | ASK: {_lastAsk:F2} | Spread: {_lastSpread:F4}";
        _metricsText.Text = $"OBI₅: {_lastObi5:F3} | OBI₁₀: {_lastObi10:F3} | " +
                            $"Walls B/A: {_lastBidWall:F2}/{_lastAskWall:F2} | " +
                            $"VolΔ: {_lastVolDelta:F3} | Trades: {_lastTradeCount}";
        _signalText.Text = $"AI SIGNAL: {signal}";
        _signalText.ForegroundColor = signalColor;
    }

    private void UpdatePositionUI()
    {
        var myPositions = Positions.Where(p => p.Label == BotLabel).ToList();

        if (myPositions.Count == 0)
        {
            _currentPosition = "FLAT";
            _positionText.Text = "POS: FLAT | P&L: $0.00";
            _positionText.ForegroundColor = Color.White;
        }
        else
        {
            var pos = myPositions.First();
            double pnl = pos.NetProfit;
            _currentPosition = pos.TradeType == TradeType.Buy ? "LONG" : "SHORT";

            _positionText.Text = $"POS: {_currentPosition} {pos.VolumeInUnits:F0}u | " +
                                 $"Entry: {pos.EntryPrice:F2} | P&L: ${pnl:F2}";
            _positionText.ForegroundColor = pnl >= 0 ? Color.LimeGreen : Color.Red;
        }
    }

    private void UpdateProtectionUI()
    {
        if (_circuitBreakerTripped) return; // Keep the halt message

        double drawdown = (_sessionPeakEquity - Account.Equity) / _sessionPeakEquity * 100;
        double dailyLossUsed = _sessionRealizedPnl < 0
            ? Math.Abs(_sessionRealizedPnl) / (_sessionStartEquity * DailyLossLimitPercent / 100) * 100
            : 0;

        Color protColor;
        if (dailyLossUsed > 80 || drawdown > MaxDrawdownPercent * 0.8 || _consecutiveLosses >= MaxConsecutiveLosses - 1)
            protColor = Color.Orange; // Warning
        else
            protColor = Color.FromArgb(255, 100, 200, 100); // Green = safe

        _protectionText.Text = $"🛡 W/L: {_sessionWins}/{_sessionLosses} | " +
                               $"P&L: ${_sessionRealizedPnl:F2} | " +
                               $"DD: {drawdown:F1}%/{MaxDrawdownPercent}% | " +
                               $"Streak: {_consecutiveLosses}/{MaxConsecutiveLosses}";
        _protectionText.ForegroundColor = protColor;
    }

    private void UpdateChartVisuals()
    {
        try
        {
            // Debug print to see if we are drawing off-screen
            // Print($"[DEBUG] Drawing lines: Mid={_lastMid}, Bid={_lastBid}, Ask={_lastAsk}");
            
            // Draw horizontal lines across the entire chart. 
            // Simplified signature to ensure maximum compatibility.
            Chart.DrawHorizontalLine("Z_MidPrice", _lastMid, Color.Cyan);
            Chart.DrawHorizontalLine("Z_BidPrice", _lastBid, Color.LimeGreen);
            Chart.DrawHorizontalLine("Z_AskPrice", _lastAsk, Color.Magenta);

            // Fallback diagnostic line: Draw at the actual chart's Bid price so it's guaranteed to be visible on any symbol
            Chart.DrawHorizontalLine("Z_ChartBid", Symbol.Bid, Color.Yellow, 2, LineStyle.Dots);
        }
        catch (Exception ex)
        {
            // Catch any UI thread drawing exceptions so they don't break the loop
            Print($"[CHART ERROR] Could not draw lines: {ex.Message}");
        }
    }

    // ═══════════════════════════════════════════════════════════
    //  TRADE EXECUTION (with Protection Checks)
    // ═══════════════════════════════════════════════════════════

    private void EvaluateAndExecuteTrade()
    {
        // 0. Circuit breaker check (redundant safety)
        if (_circuitBreakerTripped) return;

        // 1. Pre-trade protection check
        CheckCircuitBreakers();
        if (_circuitBreakerTripped) return;

        // 2. Cooldown
        if ((DateTime.UtcNow - _lastTradeTime).TotalSeconds < CooldownSeconds)
            return;

        // 3. Minimum confidence
        if (_lastAiConf < MinConfidence)
            return;

        string desiredPosition = _lastAiBias switch
        {
            "BULLISH" => "LONG",
            "BEARISH" => "SHORT",
            _ => "FLAT"
        };

        // 4. Already aligned
        if (desiredPosition == _currentPosition)
            return;

        // 5. Close opposite
        if (_currentPosition != "FLAT")
        {
            CloseAllPositions();
            Print($"[TRADE] Closed {_currentPosition} (→ {desiredPosition})");
        }

        // 6. Re-check breaker after close (the close might have tripped it)
        CheckCircuitBreakers();
        if (_circuitBreakerTripped) return;

        // 7. Open new position
        if (desiredPosition != "FLAT")
        {
            OpenPosition(desiredPosition);
        }
    }

    // ═══════════════════════════════════════════════════════════
    //  POSITION MANAGEMENT
    // ═══════════════════════════════════════════════════════════

    private double CalculateLotSize()
    {
        // USER OVERRIDE: Hardcoded test volume 0.01 lot
        return 0.01;
    }

    private (double tpPips, double slPips) CalculateTpSl()
    {
        // USER OVERRIDE: Hardcoded micro values 
        // ~0.1$ TP, ~0.3$ SL on 0.01 lot BTC is roughly 10 pips and 30 pips depending on the broker
        // We will hardcode 10 pips and 30 pips so it actually goes through the broker's minimum limits
        
        return (10.0, 30.0);
    }

    private void OpenPosition(string direction)
    {
        var tradeType = direction == "LONG" ? TradeType.Buy : TradeType.Sell;
        double volume = CalculateLotSize();
        var (tpPips, slPips) = CalculateTpSl();

        var result = ExecuteMarketOrder(
            tradeType, SymbolName, volume, BotLabel,
            slPips, tpPips,
            $"TEST:{_lastAiBias} Conf:{_lastAiConf:F2}"
        );

        if (result.IsSuccessful)
        {
            _lastTradeTime = DateTime.UtcNow;
            _currentPosition = direction;
            Print($"[TRADE DEMO] ✅ {direction} | Vol={volume:F2} | TP={tpPips:F1} SL={slPips:F1}");

            BeginInvokeOnMainThread(() =>
            {
                _tradeText.Text = $"⚡ LAST: {direction} @ {DateTime.UtcNow:HH:mm:ss}";
                _tradeText.ForegroundColor = direction == "LONG" ? Color.LimeGreen : Color.Red;
            });
        }
        else
        {
            Print($"[TRADE] ❌ Failed: {result.Error}");
        }
    }

    private void CloseAllPositions()
    {
        foreach (var pos in Positions.Where(p => p.Label == BotLabel).ToList())
        {
            var result = ClosePosition(pos);
            if (result.IsSuccessful)
                Print($"[TRADE] Closed {pos.TradeType} @ P&L: ${pos.NetProfit:F2}");
            else
                Print($"[TRADE] ❌ Close failed: {result.Error}");
        }
        _currentPosition = "FLAT";
    }
}