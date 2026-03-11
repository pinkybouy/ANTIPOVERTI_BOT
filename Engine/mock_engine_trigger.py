import asyncio
import json
import logging
import random
import sys

# Windows workaround for asyncio standard input
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MockEngine")

PORT = 5555

# Global state for the mock market
state = {
    "bid": 65000.0,
    "ask": 65000.1,
    "spread": 0.1,
    "mid": 65000.05,
    "obi5": 0.0,
    "obi10": 0.0,
    "bidWall": 1.5,
    "askWall": 1.5,
    "vDelta": 0.0,
    "pDelta": 0.0,
    "trades": 1200,
    "aiBias": "NEUTRAL",
    "aiConf": 0.0
}

clients = []

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    logger.info(f"Polaączono z cTrader Botem: {addr}")
    clients.append(writer)
    
    try:
        while True:
            # Pumping heartbeat data every 200ms
            state["bid"] += random.uniform(-0.5, 0.5)
            state["ask"] = state["bid"] + 0.1
            state["mid"] = (state["bid"] + state["ask"]) / 2
            
            # Simulate realistic Binance BTCUSDT trade volume per 200ms message.
            # Real market: ~50-80 TPS average. Per 200ms tick = ~10-16 trades normally.
            # Occasional bursts: spikes up to ~150 TPS on news/volatility events.
            burst = random.random() < 0.05  # 5% chance of a burst
            if burst:
                state["trades"] = random.randint(25, 35)  # burst: ~125-175 TPS
            else:
                state["trades"] = random.randint(8, 18)   # normal: ~40-90 TPS
            
            # Add dynamic organic movement to other mocked metrics
            state["vDelta"] = random.uniform(-2.0, 2.0)
            state["obi5"] = max(-1.0, min(1.0, state["obi5"] + random.uniform(-0.2, 0.2)))
            state["bidWall"] = max(0.1, state["bidWall"] + random.uniform(-0.2, 0.2))
            state["askWall"] = max(0.1, state["askWall"] + random.uniform(-0.2, 0.2))
            state["bidDens"] = max(0.01, random.uniform(0.01, 1.0))
            state["askDens"] = max(0.01, random.uniform(0.01, 1.0))
            
            # Occasionally shift AI signal for testing
            if random.random() < 0.05:
                state["aiBias"] = random.choice(["BULLISH", "BEARISH", "NEUTRAL"])
            state["aiConf"] = max(0.0, min(1.0, state["aiConf"] + random.uniform(-0.1, 0.1)))
            
            payload = json.dumps(state) + "\n"
            writer.write(payload.encode('utf-8'))
            await writer.drain()
            
            await asyncio.sleep(0.2)
            
            # If a client disconnects, reader.read() would return empty, 
            # but we are just pushing. We can check if connection is closed.
            if writer.is_closing():
                break
                
    except ConnectionResetError:
        logger.warning(f"Zresetowano polaczenie z {addr}")
    except Exception as e:
        logger.error(f"Blad klienta: {e}")
    finally:
        logger.info(f"Odlaczono: {addr}")
        clients.remove(writer)
        writer.close()

async def ainput(prompt: str = "") -> str:
    # Asynchronous input for Windows
    await asyncio.get_event_loop().run_in_executor(None, sys.stdout.write, prompt)
    await asyncio.get_event_loop().run_in_executor(None, sys.stdout.flush)
    return await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

async def user_input_loop():
    print("\n" + "="*50)
    print("MOCK RUST ENGINE - TESTOWANIE CTRADER BOTA")
    print("="*50)
    print("Oczekuje na polaczenie z cTradera na porcie 5555...")
    print("\nKomendy:")
    print("  [L] - Wymus pozycje LONG (BULLISH, Conf: 0.99)")
    print("  [S] - Wymus pozycje SHORT (BEARISH, Conf: 0.99)")
    print("  [F] - Wymus pozycje FLAT (NEUTRAL, Conf: 0.0)")
    print("  [Q] - Wyjscie")
    print("="*50 + "\n")
    
    while True:
        try:
            cmd = await ainput("Podaj komende (L/S/F/Q): ")
            cmd = cmd.strip().upper()
            
            if cmd == 'L':
                state["aiBias"] = "BULLISH"
                state["aiConf"] = 0.99
                logger.info("Wyslano sygnal: BULLISH (Wymuszenie wejscia w LONG)")
            elif cmd == 'S':
                state["aiBias"] = "BEARISH"
                state["aiConf"] = 0.99
                logger.info("Wyslano sygnal: BEARISH (Wymuszenie wejscia w SHORT)")
            elif cmd == 'F':
                state["aiBias"] = "NEUTRAL"
                state["aiConf"] = 0.0
                logger.info("Wyslano sygnal: NEUTRAL (Wymuszenie zamkniecia - FLAT)")
            elif cmd == 'Q':
                logger.info("Zamykanie serwera testowego...")
                for w in clients:
                    w.close()
                sys.exit(0)
            elif cmd != "":
                print("Nieznana komenda.")
                
        except KeyboardInterrupt:
            break

async def main():
    server = await asyncio.start_server(handle_client, '0.0.0.0', PORT)
    addr = server.sockets[0].getsockname()
    logger.info(f"Uruchomiono testowy serwer TCP na {addr}")

    # Uruchom obsluge inputu
    asyncio.create_task(user_input_loop())

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Zakonczono test.")
