"""
ANTIPOVERTI AI Core - Main Orchestrator
Launches all background analysis modules as concurrent asyncio tasks.

Modules:
  1. EngineSubscriber - Receives real-time HFT metrics from Rust Engine
  2. TrendAnalyzer    - Multi-timeframe K-line analysis (channels, S&R)
  3. NewsEngine       - RSS/LLM sentiment analysis
  4. DecisionLogger   - RAG-based continuous learning scaffold
  5. BiasSender       - Sends aggregated bias back to Rust Engine (port 5556)
"""
import asyncio
import logging
import time
import json

import importlib
from config import ENGINE_HOST, ENGINE_PORT, BIAS_PORT, CHROMA_PERSIST_DIR, ACTIVE_STRATEGY
from engine_subscriber import EngineSubscriber, EngineSnapshot
from trend_analyzer import TrendAnalyzer
from news_engine import NewsEngine
from decision_logger import DecisionLogger, DecisionRecord

# ─── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ai_core")

# Port for sending bias back to Rust Engine
# Imporotowany z config.py


class AICore:
    """Central orchestrator for all background AI analysis."""

    def __init__(self):
        self.engine_sub = EngineSubscriber(ENGINE_HOST, ENGINE_PORT)
        self.trend = TrendAnalyzer()
        self.news = NewsEngine()
        self.decisions = DecisionLogger(CHROMA_PERSIST_DIR)

        # ── Strategy Manager ────────────────────────────────────
        self._load_strategy()

        # Current bias output
        self.current_bias = "NEUTRAL"
        self.bias_confidence = 0.0

        # TCP writer for bias feedback (set when connected)
        self._bias_writer: asyncio.StreamWriter | None = None

        # Register callback for Engine updates
        self.engine_sub.on_update(self._on_engine_update)

        # Throttle bias recomputation
        self._last_bias_compute = 0

    def _load_strategy(self):
        """Dynamically loads the chosen strategy from the strategies directory."""
        import strategies
        logger.info(f"Loading Strategy: {ACTIVE_STRATEGY}...")
        try:
            strategy_class = getattr(strategies, ACTIVE_STRATEGY)
            self.strategy = strategy_class()
            logger.info(f"✅ Loaded {ACTIVE_STRATEGY} correctly.")
        except AttributeError:
            logger.error(f"❌ Failed to find '{ACTIVE_STRATEGY}' inside strategies/__init__.py. Falling back to default.")
            from strategies.default_strategy import DefaultStrategy
            self.strategy = DefaultStrategy()

    async def _on_engine_update(self, snapshot: EngineSnapshot):
        """Called on every tick from the Rust Engine."""
        now = time.time()

        # Recompute bias every 5 seconds (not on every tick)
        if now - self._last_bias_compute < 5.0:
            return
        self._last_bias_compute = now

        # ── Dynamic Strategy Evaluation ──────────
        macro = self.trend.get_macro_bias()
        news_score = self.news.get_news_bias()

        new_bias, new_confidence = self.strategy.evaluate(snapshot, macro, news_score)

        self.current_bias = new_bias
        self.bias_confidence = new_confidence

        logger.info(
            f"[Bias] {self.current_bias} (conf={self.bias_confidence:.3f}) | "
            f"Strategy={self.strategy.__class__.__name__} | "
            f"BID={snapshot.bid:.2f} ASK={snapshot.ask:.2f}"
        )


        # ── Send bias back to Rust Engine ─────────────────────
        await self._send_bias()

    async def _send_bias(self):
        """Send current bias to Rust Engine via TCP (port 5556)."""
        payload = json.dumps({
            "bias": self.current_bias,
            "confidence": round(self.bias_confidence, 4),
        }) + "\n"

        try:
            if self._bias_writer is None or self._bias_writer.is_closing():
                _, self._bias_writer = await asyncio.open_connection(
                    ENGINE_HOST, BIAS_PORT
                )
                logger.info(f"[BiasSender] ✅ Connected to Rust Engine on port {BIAS_PORT}")

            self._bias_writer.write(payload.encode())
            await self._bias_writer.drain()

        except (ConnectionRefusedError, OSError, ConnectionResetError) as e:
            logger.warning(f"[BiasSender] Cannot reach Engine:{BIAS_PORT}: {e}")
            self._bias_writer = None

    async def run(self):
        """Launch all modules as concurrent tasks."""
        print("╔══════════════════════════════════════════════╗")
        print("║  ANTIPOVERTI AI Core v0.2 (Python Module 2) ║")
        print("╚══════════════════════════════════════════════╝")

        tasks = [
            asyncio.create_task(self.engine_sub.run()),
            asyncio.create_task(self.trend.run(refresh_seconds=60)),
            asyncio.create_task(self.news.run(refresh_seconds=300)),
            asyncio.create_task(self._periodic_self_eval()),
        ]

        logger.info("All AI Core modules launched (with bias feedback).")
        await asyncio.gather(*tasks)

    async def _periodic_self_eval(self):
        """Run RAG self-evaluation every 10 minutes."""
        while True:
            await asyncio.sleep(600)
            try:
                stats = self.decisions.evaluate_past_decisions(lookback_hours=1)
                if stats["total"] > 0:
                    logger.info(
                        f"[RAG Self-Eval] Last 1h: {stats['correct']}/{stats['total']} "
                        f"correct ({stats['accuracy']:.1%})"
                    )
            except Exception as e:
                logger.error(f"[RAG Self-Eval] Error: {e}")


if __name__ == "__main__":
    core = AICore()
    asyncio.run(core.run())
