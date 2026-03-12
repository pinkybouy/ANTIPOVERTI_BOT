import asyncio
import websockets
import json
import time

async def main():
    uri = "wss://stream.binance.com:9443/ws"
    subscribe_msg = {
        "method": "SUBSCRIBE",
        "params": ["btcusdt@trade", "btcusdc@trade", "btcusdt@depth@100ms"],
        "id": 1
    }
    
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected! Sending subscribe...")
            await ws.send(json.dumps(subscribe_msg))
            
            for i in range(10):
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print(f"Message {i+1}: {msg[:100]}...")
            print("Done")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
