"""
ANTIPOVERTI Dashboard - Real-time Web UI
Python aiohttp server that:
  1. Subscribes to Rust Engine TCP:5555 (same as cTrader)
  2. Serves a static HTML dashboard
  3. Proxies data to browser via WebSocket

Run: python dashboard.py
Open: http://localhost:8080
"""
import asyncio
import json
import logging
import os
import time

from resource_monitor import ResourceMonitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("dashboard")

ENGINE_HOST = os.getenv("ENGINE_HOST", "127.0.0.1")
ENGINE_PORT = int(os.getenv("ENGINE_PORT", "5555"))
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))

# Connected browser WebSocket clients
ws_clients: set[web.WebSocketResponse] = set()

# Latest snapshots
latest_snapshot: dict = {}
latest_resources: dict = {}


async def engine_subscriber():
    """Connect to Rust Engine TCP and broadcast data to all WS clients."""
    global latest_snapshot, ws_clients

    while True:
        try:
            logger.info(f"Connecting to Rust Engine at {ENGINE_HOST}:{ENGINE_PORT}...")
            reader, writer = await asyncio.open_connection(ENGINE_HOST, ENGINE_PORT)
            logger.info("✅ Connected to Rust Engine.")

            async for line in reader:
                try:
                    data = json.loads(line.decode().strip())
                    data["_ts"] = time.time()
                    latest_snapshot = data

                    # Add resource data if available
                    if latest_resources:
                        data.update(latest_resources)

                    # Broadcast to all connected browsers
                    msg = json.dumps(data)
                    dead = set()
                    for ws in ws_clients:
                        try:
                            await ws.send_str(msg)
                        except Exception:
                            dead.add(ws)
                    ws_clients -= dead

                except json.JSONDecodeError:
                    continue

            logger.warning("Engine stream ended. Reconnecting...")

        except (ConnectionRefusedError, OSError) as e:
            logger.warning(f"Engine connection failed: {e}. Retrying in 3s...")

        await asyncio.sleep(3)


async def resource_monitor_task():
    """Periodically poll resource metrics for the 'brain'."""
    global latest_resources
    monitor = ResourceMonitor(tdp_watts=65)  # Can be configured via ENV
    
    while True:
        try:
            latest_resources = monitor.get_metrics()
        except Exception as e:
            logger.warning(f"Resource monitor error: {e}")
            
        await asyncio.sleep(1)


async def websocket_handler(request):
    """WebSocket endpoint for browser clients."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)
    logger.info(f"Browser connected ({len(ws_clients)} total)")

    # Send latest snapshot immediately
    data = latest_snapshot.copy()
    if latest_resources:
        data.update(latest_resources)
        
    if data:
        await ws.send_str(json.dumps(data))

    try:
        async for msg in ws:
            pass  # We don't expect messages from browser
    finally:
        ws_clients.discard(ws)
        logger.info(f"Browser disconnected ({len(ws_clients)} total)")

    return ws


async def index_handler(request):
    """Serve the dashboard HTML."""
    path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return web.FileResponse(path)


async def on_startup(app):
    """Start the Engine subscriber as a background task."""
    app["engine_task"] = asyncio.create_task(engine_subscriber())
    app["resource_task"] = asyncio.create_task(resource_monitor_task())


def main():
    app = web.Application()
    app.on_startup.append(on_startup)

    app.router.add_get("/", index_handler)
    app.router.add_get("/ws", websocket_handler)

    # Serve static files (CSS, JS, images)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.router.add_static("/static/", static_dir)

    print("=" * 48)
    print("  ANTIPOVERTI Dashboard v1.0")
    print(f"  http://localhost:{DASHBOARD_PORT}")
    print("=" * 48)

    web.run_app(app, host="0.0.0.0", port=DASHBOARD_PORT, print=None)


if __name__ == "__main__":
    main()
