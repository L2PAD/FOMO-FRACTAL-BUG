"""
Prediction Schemas — data contracts for the Prediction module.
"""
from typing import Optional


class PredictionMarket:
    """Normalized Polymarket market object."""
    def __init__(self, **kwargs):
        self.market_id: str = kwargs.get("market_id", "")
        self.question: str = kwargs.get("question", "")
        self.category: str = kwargs.get("category", "")
        self.yes_price: float = kwargs.get("yes_price", 0)
        self.no_price: float = kwargs.get("no_price", 0)
        self.volume: float = kwargs.get("volume", 0)
        self.liquidity: float = kwargs.get("liquidity", 0)
        self.spread: float = kwargs.get("spread", 0)
        self.end_date: Optional[str] = kwargs.get("end_date")
        self.event_type: str = kwargs.get("event_type", "unknown")
        self.asset: Optional[str] = kwargs.get("asset")
        self.threshold: Optional[float] = kwargs.get("threshold")
        self.comparator: str = kwargs.get("comparator", "above")
        self.raw_rules: Optional[str] = kwargs.get("raw_rules")

    def to_dict(self) -> dict:
        return {
            "market_id": self.market_id,
            "question": self.question,
            "category": self.category,
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "volume": self.volume,
            "liquidity": self.liquidity,
            "spread": self.spread,
            "end_date": self.end_date,
            "event_type": self.event_type,
            "asset": self.asset,
            "threshold": self.threshold,
            "comparator": self.comparator,
        }
