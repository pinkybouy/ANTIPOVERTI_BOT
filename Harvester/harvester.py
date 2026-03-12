import asyncio
import websockets
import json
import time
import collections
from datetime import datetime

class BinanceHarvester:
    def __init__(self, storage_manager, pairs=["btcusdt", "btcusdc"], streams=["trade", "depth@100ms", "bookTicker"]):
        self.storage = storage_manager
        self.pairs = pairs
        self.streams = streams
        self.running = False
        self.ws_tasks = []
        self.reconnect_delay = 5
        self.message_count = 0
        self.start_time = None
        self.last_msg_time = time.time()
        self.recent_logs = collections.deque(maxlen=50)
        self.stream_counts = collections.defaultdict(int)
        self.current_prices = collections.defaultdict(lambda: "0.00")
        
    def _get_stream_names(self):
        names = []
        for pair in self.pairs:
            for stream in self.streams:
                names.append(f"{pair.lower()}@{stream}")
        return names

    async def _handle_connection(self):
        url = "wss://stream.binance.com:9443/ws"
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": self._get_stream_names(),
            "id": 1
        }
        
        while self.running:
            try:
                # max_size=None jest kluczowe, bo pakiety full depth potrafią przekroczyć limity
                async with websockets.connect(url, max_size=None, ping_interval=20, ping_timeout=20) as ws:
                    print(f"[{time.strftime('%H:%M:%S')}] Polaczono z Binance. Subskrybcja strumieni...")
                    await ws.send(json.dumps(subscribe_msg))
                    
                    while self.running:
                        msg = await asyncio.wait_for(ws.recv(), timeout=60.0) # Binance wymusza frame 1x/sek
                        self.last_msg_time = time.time()
                        self.message_count += 1
                        
                        data = json.loads(msg)
                        await self._process_message(data)
                        
            except asyncio.TimeoutError:
                print("Przekroczono czas oczekiwania (Timeout). Reconnecting...")
            except websockets.exceptions.ConnectionClosed as e:
                print(f"Polaczenie zamkniete przez gielde: {e}. Reconnecting w {self.reconnect_delay}s...")
            except Exception as e:
                print(f"Nieoczekiwany blad WebSockets: {e}. Reconnecting w {self.reconnect_delay}s...")
            
            if self.running:
                await asyncio.sleep(self.reconnect_delay)

    async def _process_message(self, data: dict):
        if "e" not in data and "stream" not in data and not ("u" in data and "b" in data and "a" in data): # Komunikat powitalny lub Ping/Pong
            return
            
        stream_name = ""
        payload = data
        
        # Obsługa Multi-Stream format albo Single-Stream format
        if "stream" in data and "data" in data:
            stream_name = data["stream"]
            payload = data["data"]
            
        # Gdy nie ma stream, sam parser (e) event type
        event_type = payload.get("e")
        symbol = payload.get("s", "UNKNOWN").upper()
        
        if event_type == "trade" or event_type == "aggTrade":
             self.stream_counts["trade"] += 1
             await self.storage.add_to_buffer(symbol, event_type, payload)
             if 'p' in payload:
                 self.current_prices[symbol] = payload['p']
        elif event_type == "depthUpdate":
             self.stream_counts["depth"] += 1
             await self.storage.add_to_buffer(symbol, "depth", payload)
             if len(self.recent_logs) < 50 or self.message_count % 10 == 0:
                 self.recent_logs.appendleft(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {symbol} | DEPTH | Bids: {len(payload.get('b', []))} Asks: {len(payload.get('a', []))}")
        elif event_type == "bookTicker": # bookTicker to czasem brak "e" na starych API
             self.stream_counts["bookTicker"] += 1
             await self.storage.add_to_buffer(symbol, "bookTicker", payload)
        elif "u" in payload and "b" in payload and "a" in payload:
             # Często bookTicker leci goły bez event_type ('e')
             self.stream_counts["bookTicker"] += 1
             await self.storage.add_to_buffer(symbol, "bookTicker", payload)
             
        if event_type == "trade" or event_type == "aggTrade":
             # Zawsze pokazujemy trade'y w UI, bo są ciekawsze
             price = payload.get('p', '0')
             qty = payload.get('q', '0')
             self.recent_logs.appendleft(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {symbol} | TRADE | Cena: {price} | Ilość: {qty}")

    def start(self):
        if not self.running:
            self.running = True
            self.start_time = time.time()
            # Używamy create_task na aktywnym loopie
            self.ws_tasks.append(asyncio.create_task(self._handle_connection()))
            print("Zbieracz (Harvester) zostal Uruchomiony.")

    def stop(self):
        self.running = False
        for task in self.ws_tasks:
            task.cancel()
        self.ws_tasks.clear()
        print("Zbieracz (Harvester) zostal Zatrzymany.")
        
    def get_stats(self):
        uptime = time.time() - self.start_time if self.start_time else 0
        msg_rate = self.message_count / uptime if uptime > 0 else 0
        return {
            "status": "Running" if self.running else "Stopped",
            "uptime_seconds": round(uptime, 2),
            "messages_collected": self.message_count,
            "messages_per_sec": round(msg_rate, 2),
            "ping": round(time.time() - self.last_msg_time, 2),
            "recent_logs": list(self.recent_logs),
            "stream_counts": dict(self.stream_counts),
            "current_prices": dict(self.current_prices)
        }
