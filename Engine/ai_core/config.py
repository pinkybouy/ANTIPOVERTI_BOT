"""
ANTIPOVERTI AI Core - Configuration
All environment-level settings for the Background AI module.
"""
import os
# Szukamy .env w głównym katalogu projektu
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root_dir, '.env'))

# ─── Rust Engine Connection ───────────────────────────────────
ENGINE_HOST = os.getenv("ENGINE_HOST", "127.0.0.1")
ENGINE_PORT = int(os.getenv("ENGINE_PORT", "5555"))
BIAS_PORT = int(os.getenv("BIAS_PORT", "5556"))

# ─── Binance API ──────────────────────────────────────────────
BINANCE_REST_URL = os.getenv("BINANCE_REST_URL", "https://api.binance.com")
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
KLINE_INTERVALS = os.getenv("KLINE_INTERVALS", "1m,5m,1h,1d").split(",")

# ─── Local LLM (vLLM) ────────────────────────────────────────
VLLM_API_URL = os.getenv("VLLM_API_URL", "http://127.0.0.1:8000/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B")

# ─── ChromaDB (Vector Store for RAG) ─────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_DIR", "./data/chroma_db")

# ─── News & Social ───────────────────────────────────────────
RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
]

# ─── Analysis Params ─────────────────────────────────────────
TREND_LOOKBACK_CANDLES = 100   # How many candles to analyze per timeframe
SR_SENSITIVITY = 0.02          # 2% tolerance for Support/Resistance clustering
CHANNEL_DEVIATION = 2.0        # Standard deviations for price channel

# ─── Strategy Pattern ────────────────────────────────────────
ACTIVE_STRATEGY = os.getenv("ACTIVE_STRATEGY", "DefaultStrategy")

