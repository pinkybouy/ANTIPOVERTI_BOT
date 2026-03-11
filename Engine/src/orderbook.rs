use std::collections::BTreeMap;
use parking_lot::RwLock;
use std::sync::Arc;

/// Thread-safe Order Book with HFT metric computation.
/// Uses BTreeMap for O(log n) sorted access to price levels.
/// Key = price * 100_000_000 (integer) for lossless precision sorting.
#[derive(Debug, Clone)]
pub struct OrderBook {
    pub symbol: String,
    pub bids: BTreeMap<u64, f64>, // key = price * 100_000_000
    pub asks: BTreeMap<u64, f64>,
    pub last_update_id: u64,
}

impl OrderBook {
    pub fn new(symbol: &str) -> Self {
        Self {
            symbol: symbol.to_string(),
            bids: BTreeMap::new(),
            asks: BTreeMap::new(),
            last_update_id: 0,
        }
    }

    /// Update a single price level. Quantity <= 0 removes the level.
    pub fn update(&mut self, is_bid: bool, price: f64, quantity: f64) {
        let price_key = (price * 100_000_000.0) as u64;
        let target = if is_bid { &mut self.bids } else { &mut self.asks };

        if quantity <= 0.0 {
            target.remove(&price_key);
        } else {
            target.insert(price_key, quantity);
        }
    }

    // ─── HFT Metrics ────────────────────────────────────────────

    /// Best Bid price (highest bid)
    pub fn best_bid(&self) -> Option<f64> {
        self.bids.iter().next_back().map(|(p, _)| *p as f64 / 100_000_000.0)
    }

    /// Best Ask price (lowest ask)
    pub fn best_ask(&self) -> Option<f64> {
        self.asks.iter().next().map(|(p, _)| *p as f64 / 100_000_000.0)
    }

    /// Spread = Best Ask - Best Bid
    pub fn spread(&self) -> f64 {
        match (self.best_ask(), self.best_bid()) {
            (Some(ask), Some(bid)) => ask - bid,
            _ => 0.0,
        }
    }

    /// Order Book Imbalance (OBI) over top N levels.
    /// OBI = (sum_bids - sum_asks) / (sum_bids + sum_asks)
    /// Range: [-1.0, 1.0]. Positive = buy pressure, negative = sell pressure.
    pub fn obi(&self, levels: usize) -> f64 {
        let bid_vol: f64 = self.bids.iter().rev().take(levels).map(|(_, q)| q).sum();
        let ask_vol: f64 = self.asks.iter().take(levels).map(|(_, q)| q).sum();
        let total = bid_vol + ask_vol;
        if total == 0.0 { return 0.0; }
        (bid_vol - ask_vol) / total
    }

    /// Wall Aggregation: sum volume of top N levels on specified side
    pub fn wall_volume(&self, is_bid: bool, levels: usize) -> f64 {
        if is_bid {
            self.bids.iter().rev().take(levels).map(|(_, q)| q).sum()
        } else {
            self.asks.iter().take(levels).map(|(_, q)| q).sum()
        }
    }

    /// Liquidity Density: average volume per level over top N levels
    pub fn liquidity_density(&self, is_bid: bool, levels: usize) -> f64 {
        let vol = self.wall_volume(is_bid, levels);
        if levels == 0 { return 0.0; }
        vol / levels as f64
    }

    /// Mid Price = (Best Bid + Best Ask) / 2
    pub fn mid_price(&self) -> f64 {
        match (self.best_bid(), self.best_ask()) {
            (Some(bid), Some(ask)) => (bid + ask) / 2.0,
            (Some(bid), None) => bid,
            (None, Some(ask)) => ask,
            _ => 0.0,
        }
    }
}

pub type SharedOrderBook = Arc<RwLock<OrderBook>>;
