import os
import time
import asyncio
import aiofiles
import json
import collections
from datetime import datetime

class DataStorage:
    def __init__(self, base_dir="data"):
        self.base_dir = base_dir
        self.buffers = {}
        self.buffer_locks = {}
        self.flush_interval = 2.0  # Wrzucamy pakiety co 2 sekundy (ratowanie I/O)
        self.max_buffer_size = 50000  # Zabezpieczenie na wypadek braku flushingu
        self.total_saved_count = 0
        self.initial_count_done = False
        
        # Per-second throughput tracking: stores count of records saved each second
        # maxlen=3600 stores the last hour of per-second counts
        self._second_history = collections.deque(maxlen=3600)
        self._current_second_count = 0  # accumulator reset every second
        
        # Tworzenie katalogu
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            
    def start(self):
        asyncio.create_task(self._flush_loop())
        asyncio.create_task(self._count_historical_records())
        asyncio.create_task(self._throughput_loop())

    async def _count_historical_records(self):
        print("Trwa zliczanie historycznych rekordow z dysku...")
        total_lines = 0
        for root, dirs, files in os.walk(self.base_dir):
            for file in files:
                if file.endswith(".jsonl"):
                    file_path = os.path.join(root, file)
                    try:
                        # Zliczanie blokowe jest szybsze dla dużych plików
                        async with aiofiles.open(file_path, mode='rb') as f:
                            while True:
                                chunk = await f.read(1024 * 1024)
                                if not chunk:
                                    break
                                total_lines += chunk.count(b'\n')
                    except Exception as e:
                        print(f"Blad podczas zliczania linii w {file_path}: {e}")
        self.total_saved_count += total_lines
        self.initial_count_done = True
        print(f"Zakonczono zliczanie. Znaleziono {self.total_saved_count} rekordow.")
        
    def _get_file_path(self, symbol: str, stream_type: str):
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        
        dir_path = os.path.join(self.base_dir, symbol, stream_type)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            
        file_name = f"{symbol}_{stream_type}_{date_str}.jsonl"
        return os.path.join(dir_path, file_name)

    async def add_to_buffer(self, symbol: str, stream_type: str, data: dict):
        key = f"{symbol}_{stream_type}"
        
        if key not in self.buffers:
            self.buffers[key] = []
            self.buffer_locks[key] = asyncio.Lock()
            
        async with self.buffer_locks[key]:
            # Dodajemy timestamp lokalny (czas odebrania pakietu przez nasz serwer)
            data['_local_timestamp'] = time.time()
            self.buffers[key].append(data)
            self._current_second_count += 1  # track for throughput widget
            
            if len(self.buffers[key]) >= self.max_buffer_size:
                await self._flush_buffer(key)

    async def _flush_buffer(self, key: str):
        if key not in self.buffers or not self.buffers[key]:
            return
            
        parts = key.split('_', 1)
        if len(parts) != 2:
            return
        symbol, stream_type = parts
        
        async with self.buffer_locks[key]:
            messages_to_write = self.buffers[key]
            self.buffers[key] = []  # Czyścimy bufor przed oddaniem locka, by nie blokować kolejnych dodawań
            
        if not messages_to_write:
            return
            
        file_path = self._get_file_path(symbol, stream_type)
        try:
            async with aiofiles.open(file_path, mode='a', encoding='utf-8') as f:
                # Kompresujemy do JSONL
                lines = [json.dumps(msg) + '\n' for msg in messages_to_write]
                await f.writelines(lines)
            self.total_saved_count += len(messages_to_write)
        except Exception as e:
            print(f"[{datetime.now()}] Błąd zapisu pliku {file_path}: {e}")
            # Ratowanie zrzuconych message'y (oddajemy je do bufora awaryjnego lub na początek obecnego)
            async with self.buffer_locks[key]:
                self.buffers[key] = messages_to_write + self.buffers[key]
                print(f"Przywrócono {len(messages_to_write)} wpisów do bufora pod kątem następnej szansy.")

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(self.flush_interval)
            
            # Kopia kluczy pod iterację
            keys = list(self.buffers.keys())
            for key in keys:
                await self._flush_buffer(key)

    async def _throughput_loop(self):
        """Every second, snapshot the accumulated count and push to history deque."""
        while True:
            await asyncio.sleep(1.0)
            count = self._current_second_count
            self._current_second_count = 0
            self._second_history.append(count)
                
    def get_stats(self):
        stats = {
            "total_size_mb": 0,
            "buffer_sizes": {},
            "total_saved_count": self.total_saved_count,
            "initial_count_done": self.initial_count_done
        }
        
        for root, dirs, files in os.walk(self.base_dir):
            for file in files:
                stats["total_size_mb"] += os.path.getsize(os.path.join(root, file))
        
        stats["total_size_mb"] = round(stats["total_size_mb"] / (1024 * 1024), 2)
        
        for key, buffer in self.buffers.items():
            stats["buffer_sizes"][key] = len(buffer)
        
        # Throughput calculations from per-second history
        hist = list(self._second_history)  # oldest first
        stats["throughput_last_1s"] = hist[-1] if hist else 0
        
        last_60 = hist[-60:] if len(hist) >= 1 else []
        stats["throughput_last_1min_total"] = sum(last_60)
        stats["throughput_last_1min_avg_per_sec"] = round(sum(last_60) / len(last_60), 1) if last_60 else 0
        
        last_3600 = hist[-3600:] if len(hist) >= 1 else []
        stats["throughput_last_1h_total"] = sum(last_3600)
        stats["throughput_last_1h_avg_per_sec"] = round(sum(last_3600) / len(last_3600), 1) if last_3600 else 0
            
        return stats
