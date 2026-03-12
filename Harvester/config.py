import os
from dotenv import load_dotenv

# Szukamy .env w głównym katalogu projektu
# Zakładamy, że Harvester jest podkatalogiem projektu
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# --- Binance Configuration ---
BINANCE_PAIRS = os.getenv("BINANCE_PAIRS", "btcusdt,btcusdc").split(",")
BINANCE_STREAMS = os.getenv("BINANCE_STREAMS", "trade,depth@100ms,bookTicker").split(",")

# --- Storage Configuration ---
STORAGE_DIR = os.getenv("STORAGE_DIR", "data")

# --- Server Configuration ---
SERVER_HOST = os.getenv("HARVESTER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("HARVESTER_PORT", "8000"))
