mod orderbook;
mod binance_ws;

use std::sync::Arc;
use std::sync::atomic::{AtomicI64, Ordering};
use parking_lot::RwLock;
use orderbook::OrderBook;
use binance_ws::{TradeMetrics, SharedTradeMetrics};
use tokio::sync::watch;
use tokio::net::TcpListener;
use tokio::io::{AsyncWriteExt, AsyncBufReadExt, BufReader};

// ─── AI Bias (shared between Python listener and cTrader streamer) ───

pub struct AiBias {
    /// -1000 = BEARISH, 0 = NEUTRAL, 1000 = BULLISH (scaled i64 for atomics)
    pub direction: AtomicI64,
    /// Confidence 0-1000 (representing 0.0 - 1.0)
    pub confidence: AtomicI64,
}

impl AiBias {
    pub fn new() -> Self {
        Self {
            direction: AtomicI64::new(0),
            confidence: AtomicI64::new(0),
        }
    }

    pub fn direction_str(&self) -> &'static str {
        let d = self.direction.load(Ordering::Relaxed);
        if d > 0 { "BULLISH" }
        else if d < 0 { "BEARISH" }
        else { "NEUTRAL" }
    }

    pub fn confidence_f64(&self) -> f64 {
        self.confidence.load(Ordering::Relaxed) as f64 / 1000.0
    }
}

pub type SharedAiBias = Arc<AiBias>;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::init();
    println!("╔══════════════════════════════════════════════╗");
    println!("║  ANTIPOVERTI HFT Engine v0.4 (Rust Core)    ║");
    println!("╚══════════════════════════════════════════════╝");

    // ─── Shared State (Thread-Safe Architecture) ─────────────
    let btc_ob = Arc::new(RwLock::new(OrderBook::new("BTCUSDT")));
    let trade_metrics: SharedTradeMetrics = Arc::new(TradeMetrics::new());
    let ai_bias: SharedAiBias = Arc::new(AiBias::new());

    // Event-driven: watch channel notifies engine loop on every depth update
    let (notify_tx, _notify_rx) = watch::channel(());

    // ─── Spawn Binance WebSocket Streams ─────────────────────
    let ws_ob = btc_ob.clone();
    tokio::spawn(async move {
        binance_ws::start_depth_stream("BTCUSDT", ws_ob, notify_tx).await;
    });

    let ws_metrics = trade_metrics.clone();
    tokio::spawn(async move {
        binance_ws::start_aggtrade_stream("BTCUSDT", ws_metrics).await;
    });

    // ─── TCP Server: Python AI Bias Receiver (port 5556) ─────
    let bias_clone = ai_bias.clone();
    tokio::spawn(async move {
        start_bias_listener(bias_clone).await;
    });

    // ─── TCP Server: cTrader Data Stream (port 5555) ─────────
    let listener = TcpListener::bind("127.0.0.1:5555").await?;
    println!("[TCP:5555] cTrader feed server ready.");
    println!("[Engine] Fully operational. Waiting for connections...");

    // Accept multiple cTrader connections
    loop {
        let (mut socket, addr) = listener.accept().await?;
        println!("[TCP:5555] ✅ cTrader connected from {}", addr);

        let ob_clone = btc_ob.clone();
        let metrics_clone = trade_metrics.clone();
        let bias_ref = ai_bias.clone();
        let mut rx = _notify_rx.clone();

        tokio::spawn(async move {
            loop {
                if rx.changed().await.is_err() {
                    break;
                }

                let line = {
                    let ob = ob_clone.read();
                    if ob.bids.is_empty() || ob.asks.is_empty() { continue; }

                    let best_bid = ob.best_bid().unwrap_or(0.0);
                    let best_ask = ob.best_ask().unwrap_or(0.0);
                    let spread = ob.spread();
                    let mid = ob.mid_price();
                    let obi_5 = ob.obi(5);
                    let obi_10 = ob.obi(10);
                    let bid_wall = ob.wall_volume(true, 5);
                    let ask_wall = ob.wall_volume(false, 5);
                    let bid_density = ob.liquidity_density(true, 10);
                    let ask_density = ob.liquidity_density(false, 10);

                    let vol_delta = metrics_clone.volume_delta();
                    let price_delta = metrics_clone.price_delta();
                    let trade_count = metrics_clone.trade_count.load(Ordering::Relaxed);
                    metrics_clone.reset_window();

                    // Read AI bias (lock-free atomic read)
                    let bias_dir = bias_ref.direction_str();
                    let bias_conf = bias_ref.confidence_f64();

                    format!(
                        r#"{{"s":"BTCUSDT","bid":{:.2},"ask":{:.2},"spread":{:.4},"mid":{:.2},"obi5":{:.4},"obi10":{:.4},"bidWall":{:.4},"askWall":{:.4},"bidDens":{:.4},"askDens":{:.4},"vDelta":{:.4},"pDelta":{:.4},"trades":{},"aiBias":"{}","aiConf":{:.3}}}{}"#,
                        best_bid, best_ask, spread, mid, obi_5, obi_10,
                        bid_wall, ask_wall, bid_density, ask_density,
                        vol_delta, price_delta, trade_count,
                        bias_dir, bias_conf, "\n"
                    )
                };

                if let Err(e) = socket.write_all(line.as_bytes()).await {
                    println!("[TCP:5555] Client {} disconnected: {}", addr, e);
                    break;
                }
            }
        });
    }
}

// ─── Bias Listener: Python AI Core → Rust Engine ─────────────
// Listens on port 5556 for JSON lines like: {"bias":"BULLISH","confidence":0.73}

async fn start_bias_listener(bias: SharedAiBias) {
    let listener = match TcpListener::bind("127.0.0.1:5556").await {
        Ok(l) => l,
        Err(e) => {
            eprintln!("[TCP:5556] Failed to bind bias listener: {}", e);
            return;
        }
    };
    println!("[TCP:5556] AI Bias receiver ready (Python → Rust).");

    loop {
        match listener.accept().await {
            Ok((stream, addr)) => {
                println!("[TCP:5556] ✅ Python AI Core connected from {}", addr);
                let bias_clone = bias.clone();

                tokio::spawn(async move {
                    let reader = BufReader::new(stream);
                    let mut lines = reader.lines();

                    while let Ok(Some(line)) = lines.next_line().await {
                        // Parse: {"bias":"BULLISH","confidence":0.73}
                        if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&line) {
                            if let Some(bias_str) = parsed.get("bias").and_then(|v| v.as_str()) {
                                let dir = match bias_str {
                                    "BULLISH" => 1000i64,
                                    "BEARISH" => -1000i64,
                                    _ => 0i64,
                                };
                                bias_clone.direction.store(dir, Ordering::Relaxed);
                            }
                            if let Some(conf) = parsed.get("confidence").and_then(|v| v.as_f64()) {
                                bias_clone.confidence.store((conf * 1000.0) as i64, Ordering::Relaxed);
                            }
                            println!(
                                "[Bias] Updated: {} (conf={:.3})",
                                bias_clone.direction_str(),
                                bias_clone.confidence_f64()
                            );
                        }
                    }
                    println!("[TCP:5556] Python AI Core disconnected from {}", addr);
                });
            }
            Err(e) => {
                eprintln!("[TCP:5556] Accept error: {}", e);
            }
        }
    }
}
