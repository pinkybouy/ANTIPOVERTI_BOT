"""
News-Price Correlation Engine (Skeleton)
Fetches RSS feeds and (optionally) X/Twitter posts.
Uses local LLM (vLLM) to interpret sentiment and correlate with price movements.
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import aiohttp
import feedparser

from config import RSS_FEEDS, VLLM_API_URL, LLM_MODEL

logger = logging.getLogger("ai_core.news")


@dataclass
class NewsItem:
    title: str
    summary: str
    source: str
    published: str
    sentiment: Optional[float] = None  # -1.0 to 1.0
    llm_analysis: Optional[str] = None


class NewsEngine:
    """Fetches news, analyzes sentiment via local LLM, correlates with price."""

    def __init__(self):
        self.latest_news: List[NewsItem] = []
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def fetch_rss_feeds(self) -> List[NewsItem]:
        """Download and parse all configured RSS feeds."""
        items = []
        for feed_url in RSS_FEEDS:
            try:
                session = await self._get_session()
                async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    text = await resp.text()
                feed = feedparser.parse(text)
                for entry in feed.entries[:5]:  # Latest 5 per feed
                    items.append(NewsItem(
                        title=entry.get("title", ""),
                        summary=entry.get("summary", "")[:500],
                        source=feed_url,
                        published=entry.get("published", ""),
                    ))
            except Exception as e:
                logger.warning(f"RSS fetch error ({feed_url}): {e}")
        return items

    async def analyze_sentiment_llm(self, news: NewsItem) -> NewsItem:
        """Send a news headline to local LLM for sentiment analysis."""
        try:
            session = await self._get_session()
            prompt = (
                f"You are a crypto market analyst. Analyze this headline for Bitcoin price impact.\n"
                f"Headline: \"{news.title}\"\n"
                f"Summary: \"{news.summary[:200]}\"\n\n"
                f"Respond with ONLY a JSON object: {{\"sentiment\": <float -1.0 to 1.0>, \"reason\": \"<brief>\"}}"
            )

            payload = {
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.1,
            }

            async with session.post(
                f"{VLLM_API_URL}/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    content = result["choices"][0]["message"]["content"]
                    news.llm_analysis = content

                    # Try to parse sentiment score
                    import json as json_lib
                    try:
                        parsed = json_lib.loads(content)
                        news.sentiment = float(parsed.get("sentiment", 0))
                    except (json_lib.JSONDecodeError, ValueError):
                        news.sentiment = 0.0
                else:
                    logger.warning(f"LLM returned status {resp.status}")

        except Exception as e:
            logger.warning(f"LLM analysis failed: {e} (Is vLLM running?)")
            news.sentiment = 0.0

        return news

    async def run(self, refresh_seconds: int = 300):
        """Continuously fetch and analyze news every N seconds."""
        while True:
            try:
                raw_news = await self.fetch_rss_feeds()
                analyzed = []
                for item in raw_news:
                    item = await self.analyze_sentiment_llm(item)
                    analyzed.append(item)

                self.latest_news = analyzed
                avg_sentiment = (
                    sum(n.sentiment for n in analyzed if n.sentiment is not None) / len(analyzed)
                    if analyzed else 0.0
                )
                logger.info(f"[News] Fetched {len(analyzed)} items | Avg sentiment: {avg_sentiment:.3f}")

            except Exception as e:
                logger.error(f"[News] Run error: {e}")

            await asyncio.sleep(refresh_seconds)

    def get_news_bias(self) -> float:
        """Return aggregated sentiment score. Range: -1.0 (bearish) to 1.0 (bullish)."""
        if not self.latest_news:
            return 0.0
        sentiments = [n.sentiment for n in self.latest_news if n.sentiment is not None]
        return sum(sentiments) / len(sentiments) if sentiments else 0.0
