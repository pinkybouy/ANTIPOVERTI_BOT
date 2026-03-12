import asyncio
import collections
from harvester import BinanceHarvester
from storage import DataStorage
import websockets
import json

async def main():
    storage = DataStorage(base_dir="test_data")
    harvester = BinanceHarvester(storage)
    
    # We will manualy test just the connection handling
    uri = "wss://stream.binance.com:9443/ws"
    subscribe_msg = {
        "method": "SUBSCRIBE",
        "params": harvester._get_stream_names(),
        "id": 1
    }
    
    print("Testing parser with actual binance exchange...")
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps(subscribe_msg))
        for _ in range(3):
            reply = await ws.recv()
            print(f"recv: {reply[:100]}")
            try:
                data = json.loads(reply)
                await harvester._process_message(data)
                print(f"success process_message. recent_logs: {len(harvester.recent_logs)}")
            except Exception as e:
                import traceback
                print(f"ERROR: {e}")
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
