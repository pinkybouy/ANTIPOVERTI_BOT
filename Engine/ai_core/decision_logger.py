"""
Continuous Learning & Decision Logger (RAG Scaffold)
Logs every trading decision alongside market context into a ChromaDB
vector store. Enables Retrieval-Augmented Generation for self-evaluation.
"""
import logging
import time
import json
from dataclasses import dataclass, asdict
from typing import Optional, List

logger = logging.getLogger("ai_core.rag")

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("ChromaDB not installed. RAG features disabled.")


@dataclass
class DecisionRecord:
    """A single trading decision with full market context."""
    timestamp: float
    action: str                # "LONG", "SHORT", "FLAT"
    reason: str                # Why the decision was made
    # Market context at decision time
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0
    obi5: float = 0.0
    obi10: float = 0.0
    vol_delta: float = 0.0
    price_delta: float = 0.0
    macro_bias: str = ""       # From TrendAnalyzer
    news_sentiment: float = 0.0
    # Outcome (filled later by evaluation loop)
    outcome_pnl: Optional[float] = None
    outcome_correct: Optional[bool] = None


class DecisionLogger:
    """Stores decisions in ChromaDB for RAG-based self-evaluation."""

    def __init__(self, persist_dir: str = "./data/chroma_db"):
        self.persist_dir = persist_dir
        self._client = None
        self._collection = None
        self._init_db()

    def _init_db(self):
        if not CHROMA_AVAILABLE:
            return
        try:
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                name="decisions",
                metadata={"description": "HFT trading decisions with market context"}
            )
            logger.info(f"ChromaDB initialized at {self.persist_dir} "
                       f"({self._collection.count()} existing records)")
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")

    def log_decision(self, record: DecisionRecord):
        """Log a decision into the vector store."""
        if self._collection is None:
            return

        doc_text = (
            f"Action: {record.action} | Reason: {record.reason} | "
            f"OBI5: {record.obi5:.3f} | VolDelta: {record.vol_delta:.3f} | "
            f"Macro: {record.macro_bias} | News: {record.news_sentiment:.2f}"
        )

        self._collection.add(
            documents=[doc_text],
            metadatas=[asdict(record)],
            ids=[f"dec_{int(record.timestamp * 1000)}"],
        )
        logger.debug(f"Logged decision: {record.action}")

    def query_similar(self, context: str, n_results: int = 5) -> List[dict]:
        """Find similar past decisions for RAG evaluation."""
        if self._collection is None or self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[context],
            n_results=min(n_results, self._collection.count()),
        )
        return results.get("metadatas", [[]])[0]

    def evaluate_past_decisions(self, lookback_hours: int = 1) -> dict:
        """Self-evaluation: check recent decisions against outcomes."""
        if self._collection is None:
            return {"total": 0, "correct": 0, "accuracy": 0.0}

        cutoff = time.time() - (lookback_hours * 3600)
        # ChromaDB doesn't support time-range queries natively,
        # so we query all recent and filter in-memory
        all_records = self._collection.get(include=["metadatas"])
        recent = [
            m for m in all_records.get("metadatas", [])
            if m.get("timestamp", 0) > cutoff and m.get("outcome_correct") is not None
        ]

        total = len(recent)
        correct = sum(1 for r in recent if r.get("outcome_correct"))
        accuracy = correct / total if total > 0 else 0.0

        return {"total": total, "correct": correct, "accuracy": accuracy}
