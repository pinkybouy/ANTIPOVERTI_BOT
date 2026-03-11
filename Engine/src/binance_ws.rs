use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use futures_util::StreamExt;
use url::Url;
use serde::Deserialize;
use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::Arc;
use tokio::sync::watch;

use crate::orderbook::SharedOrderBook;

// ─── Binance JSON Schemas ────────────────────────────────────

#[derive(Deserialize, Debug)]
struct DepthUpdate {
    #[serde(rename = "u")]
    pub final_update_id: u64,
    #[serde(rename = "b")]
    pub bids: Vec<[String; 2]>,
    #[serde(rename = "a")]
    pub asks: Vec<[String; 2]>,
}

#[derive(Deserialize, Debug)]
struct AggTrade {
    #[serde(rename = "p")]
    pub price: String,
    #[serde(rename = "q")]
    pub quantity: String,
    #[serde(rename = "m")]
    pub is_buyer_maker: bool, // true = seller-initiated (sell aggressor)
}

// ─── Trade Metrics (shared atomics) ──────────────────────────

pub struct TradeMetrics {
    pub buy_volume_x1000: AtomicI64,   // buyer-initiated volume * 1000 (for precision)
    pub sell_volume_x1000: AtomicI64,  // seller-initiated volume * 1000
    pub last_price_x100: AtomicI64,    // last trade price * 100
    pub prev_price_x100: AtomicI64,    // previous trade price * 100
    pub trade_count: AtomicI64,        // number of trades in current window
}

impl TradeMetrics {
    pub fn new() -> Self {
        Self {
            buy_volume_x1000: AtomicI64::new(0),
            sell_volume_x1000: AtomicI64::new(0),
            last_price_x100: AtomicI64::new(0),
            prev_price_x100: AtomicI64::new(0),
            trade_count: AtomicI64::new(0),
        }
    }

    /// Volume Delta = Buy Volume - Sell Volume (trade aggressiveness)
    pub fn volume_delta(&self) -> f64 {
        let buy = self.buy_volume_x1000.load(Ordering::Relaxed) as f64 / 1000.0;
        let sell = self.sell_volume_x1000.load(Ordering::Relaxed) as f64 / 1000.0;
        buy - sell
    }

    /// Price Delta = Last Price - Previous Price (momentum)
    pub fn price_delta(&self) -> f64 {
        let last = self.last_price_x100.load(Ordering::Relaxed) as f64 / 100.0;
        let prev = self.prev_price_x100.load(Ordering::Relaxed) as f64 / 100.0;
        last - prev
    }

    /// Reset accumulators for next window
    pub fn reset_window(&self) {
        self.buy_volume_x1000.store(0, Ordering::Relaxed);
        self.sell_volume_x1000.store(0, Ordering::Relaxed);
        self.trade_count.store(0, Ordering::Relaxed);
    }
}

pub type SharedTradeMetrics = Arc<TradeMetrics>;

// ─── Depth Stream with Auto-Reconnect ────────────────────────

pub async fn start_depth_stream(symbol: &str, orderbook: SharedOrderBook, notify: watch::Sender<()>) {
    let ws_url = format!(
        "wss://stream.binance.com:9443/ws/{}@depth@100ms",
        symbol.to_lowercase()
    );

    loop {
        println!("[Depth] Connecting to Binance...");
        let url = Url::parse(&ws_url).unwrap();

        match connect_async(url).await {
            Ok((ws_stream, _)) => {
                println!("[Depth] ✅ Connected for {}", symbol);
                let (_, mut read) = ws_stream.split();

                while let Some(msg) = read.next().await {
                    if let Ok(Message::Text(text)) = msg {
                        if let Ok(update) = serde_json::from_str::<DepthUpdate>(&text) {
                            let mut ob = orderbook.write();
                            ob.last_update_id = update.final_update_id;

                            for bid in update.bids {
                                if let (Ok(price), Ok(qty)) = (bid[0].parse::<f64>(), bid[1].parse::<f64>()) {
                                    ob.update(true, price, qty);
                                }
                            }
                            for ask in update.asks {
                                if let (Ok(price), Ok(qty)) = (ask[0].parse::<f64>(), ask[1].parse::<f64>()) {
                                    ob.update(false, price, qty);
                                }
                            }
                            // Drop lock before notify
                            drop(ob);
                            // Signal the engine loop that new data arrived
                            let _ = notify.send(());
                        }
                    }
                }
                println!("[Depth] ⚠️ Stream ended. Reconnecting in 2s...");
            }
            Err(e) => {
                println!("[Depth] ❌ Connection failed: {}. Retrying in 3s...", e);
            }
        }
        // Backoff before reconnect
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
    }
}

// ─── AggTrade Stream with Auto-Reconnect ─────────────────────

pub async fn start_aggtrade_stream(symbol: &str, metrics: SharedTradeMetrics) {
    let ws_url = format!(
        "wss://stream.binance.com:9443/ws/{}@aggTrade",
        symbol.to_lowercase()
    );

    loop {
        println!("[AggTrade] Connecting to Binance...");
        let url = Url::parse(&ws_url).unwrap();

        match connect_async(url).await {
            Ok((ws_stream, _)) => {
                println!("[AggTrade] ✅ Connected for {}", symbol);
                let (_, mut read) = ws_stream.split();

                while let Some(msg) = read.next().await {
                    if let Ok(Message::Text(text)) = msg {
                        if let Ok(trade) = serde_json::from_str::<AggTrade>(&text) {
                            if let (Ok(price), Ok(qty)) = (trade.price.parse::<f64>(), trade.quantity.parse::<f64>()) {
                                let qty_i = (qty * 1000.0) as i64;
                                let price_i = (price * 100.0) as i64;

                                // Update price tracking
                                let prev = metrics.last_price_x100.swap(price_i, Ordering::Relaxed);
                                metrics.prev_price_x100.store(prev, Ordering::Relaxed);

                                // Track volume delta (buyer vs seller aggressor)
                                if trade.is_buyer_maker {
                                    // is_buyer_maker=true means the SELLER hit the bid (sell aggressor)
                                    metrics.sell_volume_x1000.fetch_add(qty_i, Ordering::Relaxed);
                                } else {
                                    // Buyer lifted the ask (buy aggressor)
                                    metrics.buy_volume_x1000.fetch_add(qty_i, Ordering::Relaxed);
                                }
                                metrics.trade_count.fetch_add(1, Ordering::Relaxed);
                            }
                        }
                    }
                }
                println!("[AggTrade] ⚠️ Stream ended. Reconnecting in 2s...");
            }
            Err(e) => {
                println!("[AggTrade] ❌ Connection failed: {}. Retrying in 3s...", e);
            }
        }
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
    }
}
