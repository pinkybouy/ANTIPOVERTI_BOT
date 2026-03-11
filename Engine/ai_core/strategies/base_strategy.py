from typing import Tuple
from engine_subscriber import EngineSnapshot

class BaseStrategy:
    """
    Abstract Base Class for all trading strategies in the Python AI Core.
    Every strategy must implement the evaluate() method.
    """
    
    def __init__(self):
        # Override to setup your models, scalers, etc
        pass

    def evaluate(self, snapshot: EngineSnapshot, macro_bias: str, news_score: float) -> Tuple[str, float]:
        """
        Evaluate market conditions and return a trading bias and confidence.
        
        Args:
            snapshot: Latest high-frequency data from Rust Engine (OBI, VolDelta, Spread)
            macro_bias: Multi-timeframe trend analysis result ("BULLISH", "BEARISH", "NEUTRAL") 
            news_score: NLP Sentiment analysis score (-1.0 to 1.0)
            
        Returns:
            Tuple containing:
            - Bias string ("BULLISH", "BEARISH", "NEUTRAL")
            - Confidence float (0.0 to 1.0)
        """
        raise NotImplementedError("Each strategy must implement the evaluate() method.")
