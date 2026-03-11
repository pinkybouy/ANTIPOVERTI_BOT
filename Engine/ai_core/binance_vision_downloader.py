import os
import urllib.request
import zipfile
from datetime import datetime, timedelta
import time
import argparse

# Base URL for Binance Vision Daily Spot data
BASE_URL = "https://data.binance.vision/data/spot/daily"

# Default configuration
DEFAULT_SYMBOLS = ["BTCUSDT", "BTCUSDC"]
DEFAULT_TYPES = ["aggTrades", "trades", "klines"] 
DEFAULT_EXT_URL = ""
DEFAULT_INTERVAL = "1m" # Used only for klines
# aggTrades: Provides tick-by-tick trades with Volume/Maker-Buyer flag (for Volume Delta)
# bookTicker: Provides Best Bid/Ask Price & Qty at the time of orderbook updates (for Spread & Micro-price OBI)

def download_file(url, target_path):
    print(f"Pobieranie: {url} ...")
    try:
        # Increase timeout and handle request
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response, open(target_path, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  [POMINIETO] Plik nie istnieje na serwerze (404): {url}")
        else:
            print(f"  [BLAD HTTP] {e.code} dla {url}")
        return False
    except Exception as e:
        print(f"  [BLAD] Nie mozna pobrac {url}: {e}")
        return False

def extract_zip(zip_path, extract_to):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print(f"  [OK] Rozpakowano {os.path.basename(zip_path)}")
        os.remove(zip_path) # Clean up zip after extraction
    except Exception as e:
        print(f"  [BLAD] Nie mozna rozpakowac {zip_path}: {e}")

def get_dates(start_date_str, end_date_str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
    return dates

def download_daily_data(symbols, data_types, dates, dest_folder, interval="1m"):
    for symbol in symbols:
        for dtype in data_types:
            folder_path = os.path.join(dest_folder, symbol, dtype)
            os.makedirs(folder_path, exist_ok=True)
            
            print(f"\n=== Przetwarzanie: {symbol} | Typ: {dtype} ===")
            for date in dates:
                if dtype == "klines":
                    # URL dla klines: https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-03-01.zip
                    filename = f"{symbol}-{interval}-{date}.zip"
                    url = f"{BASE_URL}/{dtype}/{symbol}/{interval}/{filename}"
                    csv_filename = f"{symbol}-{interval}-{date}.csv"
                else:
                    # URL dla trades/aggTrades: https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2024-03-01.zip
                    filename = f"{symbol}-{dtype}-{date}.zip"
                    url = f"{BASE_URL}/{dtype}/{symbol}/{filename}"
                    csv_filename = f"{symbol}-{dtype}-{date}.csv"
                    
                target_zip = os.path.join(folder_path, filename)
                csv_target = os.path.join(folder_path, csv_filename)
                
                # Check if unzipped CSV already exists to skip
                if os.path.exists(csv_target):
                    print(f"  [ZROBIONE] Plik {csv_filename} juz istnieje, pomijam.")
                    continue
                
                success = download_file(url, target_zip)
                if success:
                    extract_zip(target_zip, folder_path)
                    
                time.sleep(0.3) # Small delay to prevent Binance rate limiting

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pobieracz danych historycznych z Binance Vision (Daily Spot)")
    parser.add_argument("--start", type=str, required=True, help="Data poczatkowa np. 2024-01-01")
    parser.add_argument("--end", type=str, required=True, help="Data koncowa np. 2024-01-31")
    parser.add_argument("--symbols", type=str, nargs="+", default=DEFAULT_SYMBOLS, help="Lista symboli m.in BTCUSDT BTCUSDC")
    parser.add_argument("--types", type=str, nargs="+", default=DEFAULT_TYPES, help="Typy danych (aggTrades, trades, klines)")
    parser.add_argument("--interval", type=str, default=DEFAULT_INTERVAL, help="Interwal dla klines np. 1m, 5m, 1h")
    parser.add_argument("--dest", type=str, default="C:/HFT_DATA", help="Katalog docelowy zapisu danych")
    
    args = parser.parse_args()
    
    try:
        dates = get_dates(args.start, args.end)
    except ValueError:
        print("Blad: Uzyj poprawnego formatu daty YYYY-MM-DD")
        exit(1)
        
    print(f"Rozpoczynam pobieranie danych dla {len(dates)} dni...")
    print(f"Symbole docelowe: {args.symbols}")
    print(f"Typy plikow: {args.types}")
    print(f"Katalog docelowy: {args.dest}")
    print("-" * 50)
    
    download_daily_data(args.symbols, args.types, dates, args.dest, args.interval)
    print("\nZakonczono pobieranie wszystkich dostepnych plikow z zadanego zakresu.")
