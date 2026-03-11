"""
TCP Subscriber - Connects to the Rust HFT Engine and receives real-time metrics.
Runs as a background asyncio task. Stores latest snapshot for other modules.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("ai_core.engine_sub")


@dataclass
class EngineSnapshot:
    """Latest HFT metrics received from the Rust Engine."""
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0
    mid: float = 0.0
    obi5: float = 0.0
    obi10: float = 0.0
    bid_wall: float = 0.0
    ask_wall: float = 0.0
    bid_density: float = 0.0
    ask_density: float = 0.0
    vol_delta: float = 0.0
    price_delta: float = 0.0
    trades: int = 0
    timestamp: float = 0.0  # local receive time


class EngineSubscriber:
    """Async TCP client that subscribes to the Rust HFT Engine stream."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.snapshot = EngineSnapshot()
        self._connected = False
        self._callbacks = []

    def on_update(self, callback):
        """Register a callback for every new snapshot."""
        self._callbacks.append(callback)

    @property
    def connected(self) -> bool:
        return self._connected

    async def run(self):
        """Main loop with auto-reconnect."""
        import time
        while True:
            try:
                logger.info(f"Connecting to Rust Engine at {self.host}:{self.port}...")
                reader, writer = await asyncio.open_connection(self.host, self.port)
                self._connected = True
                logger.info("✅ Connected to Rust Engine.")

                async for line in reader:
                    try:
                        data = json.loads(line.decode().strip())
                        self.snapshot = EngineSnapshot(
                            bid=data.get("bid", 0),
                            ask=data.get("ask", 0),
                            spread=data.get("spread", 0),
                            mid=data.get("mid", 0),
                            obi5=data.get("obi5", 0),
                            obi10=data.get("obi10", 0),
                            bid_wall=data.get("bidWall", 0),
                            ask_wall=data.get("askWall", 0),
                            bid_density=data.get("bidDens", 0),
                            ask_density=data.get("askDens", 0),
                            vol_delta=data.get("vDelta", 0),
                            price_delta=data.get("pDelta", 0),
                            trades=data.get("trades", 0),
                            timestamp=time.time(),
                        )
                        for cb in self._callbacks:
                            await cb(self.snapshot)
                    except json.JSONDecodeError:
                        continue

                logger.warning("Engine stream ended. Reconnecting...")

            except (ConnectionRefusedError, OSError) as e:
                logger.warning(f"Engine connection failed: {e}. Retrying in 3s...")
            finally:
                self._connected = False

            await asyncio.sleep(3)
