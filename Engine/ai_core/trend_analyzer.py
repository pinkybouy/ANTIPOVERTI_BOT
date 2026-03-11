"""
Multi-Timeframe Trend Analyzer
Fetches K-line data from Binance REST API and computes:
- Dynamic Price Channels (Linear Regression ± std dev)
- Support & Resistance levels (pivot clustering)
- Trend direction per timeframe
"""
import asyncio
import logging
import time
from typing import List, Tuple, Optional

import aiohttp
import numpy as np
import pandas as pd
from dataclasses import dataclass

from config import BINANCE_REST_URL, SYMBOL, KLINE_INTERVALS, TREND_LOOKBACK_CANDLES, CHANNEL_DEVIATION, SR_SENSITIVITY

logger = logging.getLogger("ai_core.trend")


@dataclass
class TrendResult:
    interval: str
    direction: str           # "UP", "DOWN", "SIDEWAYS"
    channel_upper: float
    channel_lower: float
    channel_mid: float
    support_levels: List[float]
    resistance_levels: List[float]
    slope: float             # Linear regression slope (price per candle)
    r_squared: float         # Goodness of fit
    timestamp: float



class TrendAnalyzer:
    """Periodically fetches K-lines and computes macro trend signals."""

    def __init__(self):
        self.results: dict[str, TrendResult] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def fetch_klines(self, interval: str, limit: int = TREND_LOOKBACK_CANDLES) -> pd.DataFrame:
        """Fetch K-line data from Binance REST API."""
        session = await self._get_session()
        url = f"{BINANCE_REST_URL}/api/v3/klines"
        params = {"symbol": SYMBOL, "interval": interval, "limit": limit}

        async with session.get(url, params=params) as resp:
            data = await resp.json()

        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_vol",
            "taker_buy_quote_vol", "ignore"
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        return df

    def compute_channel(self, closes: np.ndarray) -> Tuple[float, float, float, float, float]:
        """Linear regression channel: mid, upper, lower, slope, r²."""
        x = np.arange(len(closes))
        coeffs = np.polyfit(x, closes, 1)
        slope, intercept = coeffs
        fitted = np.polyval(coeffs, x)
        residuals = closes - fitted
        std = np.std(residuals)

        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((closes - np.mean(closes)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        last_fit = fitted[-1]
        upper = last_fit + CHANNEL_DEVIATION * std
        lower = last_fit - CHANNEL_DEVIATION * std

        return last_fit, upper, lower, slope, r_squared

    def find_support_resistance(self, highs: np.ndarray, lows: np.ndarray) -> Tuple[List[float], List[float]]:
        """Cluster pivot highs/lows into Support & Resistance zones."""
        pivots = np.concatenate([highs, lows])
        pivots.sort()

        clusters = []
        current_cluster = [pivots[0]]

        for p in pivots[1:]:
            if abs(p - np.mean(current_cluster)) / np.mean(current_cluster) < SR_SENSITIVITY:
                current_cluster.append(p)
            else:
                if len(current_cluster) >= 3:  # Minimum touches
                    clusters.append(np.mean(current_cluster))
                current_cluster = [p]
        if len(current_cluster) >= 3:
            clusters.append(np.mean(current_cluster))

        if not clusters:
            return [], []

        mid = np.median(pivots)
        supports = [c for c in clusters if c < mid]
        resistances = [c for c in clusters if c >= mid]
        return supports, resistances

    async def analyze_interval(self, interval: str) -> TrendResult:
        """Full analysis for one timeframe."""
        df = await self.fetch_klines(interval)
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values

        mid, upper, lower, slope, r_sq = self.compute_channel(closes)
        supports, resistances = self.find_support_resistance(highs, lows)

        # Determine direction
        if slope > 0 and r_sq > 0.5:
            direction = "UP"
        elif slope < 0 and r_sq > 0.5:
            direction = "DOWN"
        else:
            direction = "SIDEWAYS"

        result = TrendResult(
            interval=interval,
            direction=direction,
            channel_upper=upper,
            channel_lower=lower,
            channel_mid=mid,
            support_levels=supports,
            resistance_levels=resistances,
            slope=slope,
            r_squared=r_sq,
            timestamp=time.time(),
        )
        self.results[interval] = result
        return result

    async def run(self, refresh_seconds: int = 60):
        """Continuously analyze all timeframes."""
        while True:
            for interval in KLINE_INTERVALS:
                try:
                    result = await self.analyze_interval(interval)
                    logger.info(f"[Trend {interval}] {result.direction} | "
                                f"Channel: {result.channel_lower:.2f}-{result.channel_upper:.2f} | "
                                f"S/R: {len(result.support_levels)}s/{len(result.resistance_levels)}r")
                except Exception as e:
                    logger.error(f"[Trend {interval}] Error: {e}")

            await asyncio.sleep(refresh_seconds)

    def get_macro_bias(self) -> str:
        """Aggregate trend across all timeframes into a single bias."""
        if not self.results:
            return "NEUTRAL"

        scores = {"UP": 0, "DOWN": 0, "SIDEWAYS": 0}
        weights = {"1m": 1, "5m": 2, "1h": 3, "1d": 4}

        for interval, result in self.results.items():
            w = weights.get(interval, 1)
            scores[result.direction] += w

        if scores["UP"] > scores["DOWN"] + scores["SIDEWAYS"]:
            return "BULLISH"
        elif scores["DOWN"] > scores["UP"] + scores["SIDEWAYS"]:
            return "BEARISH"
        return "NEUTRAL"
