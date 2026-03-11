from typing import Tuple
from engine_subscriber import EngineSnapshot
from .base_strategy import BaseStrategy

class DefaultStrategy(BaseStrategy):
    """
    The original default logic that weights Micro (40%), Macro (40%) and News (20%).
    """

    def evaluate(self, snapshot: EngineSnapshot, macro_bias: str, news_score: float) -> Tuple[str, float]:
        
        # OBI (micro) score from -1 to 1
        micro_score = snapshot.obi5

        # Translate Macro String to Score
        if macro_bias == "BULLISH":
            macro_score = 0.5
        elif macro_bias == "BEARISH":
            macro_score = -0.5
        else:
            macro_score = 0.0

        # Weighted blend: 40% micro, 40% macro, 20% news
        combined = 0.4 * micro_score + 0.4 * macro_score + 0.2 * news_score

        # Determine bias
        if combined > 0.2:
            current_bias = "BULLISH"
        elif combined < -0.2:
            current_bias = "BEARISH"
        else:
            current_bias = "NEUTRAL"

        # Confidence is the magnitude of the score
        bias_confidence = min(abs(combined), 1.0)

        return current_bias, bias_confidence
