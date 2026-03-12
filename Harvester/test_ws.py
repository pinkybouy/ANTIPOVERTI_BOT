import asyncio
import websockets
import time

async def main():
    uri = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected! Waiting for messages...")
            for i in range(5):
                msg = await ws.recv()
                print(f"Message {i+1}: {msg[:100]}...")
            print("Done")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
