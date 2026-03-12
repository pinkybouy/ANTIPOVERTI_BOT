# Data Structure Overview

This document explains the organization and format of the data collected by the Binance Tick Harvester.

## Directory Structure

All data is stored sequentially inside the `data/` root directory. The hierarchy is organized by **Trading Pair**, followed by **Stream Type**, and broken down into **Daily Files**.

```text
data/
├── BTCUSDT/
│   ├── trade/
│   │   ├── btcusdt_trade_2026-03-07.jsonl
│   │   └── btcusdt_trade_2026-03-08.jsonl
│   ├── depth/
│   │   └── btcusdt_depth_2026-03-07.jsonl
│   └── bookTicker/
│       └── btcusdt_bookTicker_2026-03-07.jsonl
└── BTCUSDC/
    ├── trade/
    ├── depth/
    └── bookTicker/
```

- **Data Partitioning**: By splitting the data into separate days (`..._2026-03-07.jsonl`), we ensure file sizes remain manageable, preventing high RAM consumption when loading the files later for data analysis.

---

## What is a JSONL File?

A **JSONL** (JSON Lines) file is a text file where **every line is a distinct, valid JSON object**. 

**Standard JSON:**
```json
[
  {"id": 1, "price": 100},
  {"id": 2, "price": 101}
]
```

**JSONL Format:**
```json
{"id": 1, "price": 100}
{"id": 2, "price": 101}
```

### Why JSONL for the Harvester?
1. **Streaming Optimized**: The harvester can instantly append a new line to the end of the file without parsing or modifying the rest of the file.
2. **Crash Resilience**: If the system crashes, only the unwritten lines are lost. The rest of the file remains 100% valid.
3. **Memory Efficiency**: You can read a 50GB `.jsonl` file line-by-line without loading the entire 50GB into memory, which would be impossible with a standard JSON array.

---

## Data Payloads (Stream Schemas)

The harvester directly saves the standard Binance WebSocket stream payloads, along with one custom field attached by our application:
* `_local_timestamp`: A float representing the exact UNIX timestamp when our server *received* the message. This is critical for measuring network latency and determining realistic algorithmic trading delays.

Below are the exact shapes of the records you will find in each folder:

### 1. Trade Stream (`trade`)
Captures every single transaction executed on the order book.

```json
{
  "e": "trade",         // Event type
  "E": 1672515233123,   // Event time (Binance server time)
  "s": "BTCUSDT",       // Symbol
  "t": 12345,           // Trade ID
  "p": "67000.50",      // Execution Price
  "q": "1.500",         // Execution Quantity
  "b": 88,              // Buyer order ID
  "a": 50,              // Seller order ID
  "T": 1672515233120,   // Trade time
  "m": true,            // Is the buyer the market maker? (True means the trade was a market SELL into the bids)
  "M": true,            // Ignore (deprecated by Binance)
  "_local_timestamp": 1672515233.1534
}
```

### 2. Depth Stream (`depth`)
Captures updates to the Order Book (resting limit, buy/sell orders). We subscribe to `depth@100ms`, meaning updates are grouped and sent every 100 milliseconds.

```json
{
  "e": "depthUpdate",   // Event type
  "E": 1672515235555,   // Event time
  "s": "BTCUSDT",       // Symbol
  "U": 157,             // First update ID in event
  "u": 160,             // Final update ID in event
  "b": [                // BIDS (Buyers) to be updated
    [
      "66500.00",       // Price level to be updated
      "10.5"            // New total quantity at this price level
    ]
  ],
  "a": [                // ASKS (Sellers) to be updated
    [
      "67100.00",       // Price level to be updated
      "5.2"             // New total quantity at this price level
    ]
  ],
  "_local_timestamp": 1672515235.5801
}
```

### 3. Book Ticker Stream (`bookTicker`)
The Best Bid and Best Ask. It provides the tightest spread immediately without calculating the entire Depth stream. This is pushed in real-time.

```json
{
  "u": 400900217,       // Order book updateId
  "s": "BTCUSDT",       // Symbol
  "b": "67000.00",      // Best bid price
  "B": "3.1000",        // Best bid quantity
  "a": "67000.10",      // Best ask price
  "A": "4.5000",        // Best ask quantity
  "_local_timestamp": 1672515238.1022
}
```
