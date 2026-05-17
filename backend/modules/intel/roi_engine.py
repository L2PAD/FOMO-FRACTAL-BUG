"""
FOMO ROI Engine
===============
Multi-level ROI calculation for investment analysis.

Accuracy Levels:
- Level A (Realized): actual exit data with TGE price + current price
- Level B (Mark-to-Market): entry price + current market price
- Level C (Proxy): time-based heuristics when no price data

Skill Score:
Weighted formula combining multiple performance metrics.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
import math


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class ROIEngine:
    """
    ROI calculation engine with multiple accuracy levels.
    """
    
    def __init__(self):
        # Cache for token prices
        self.price_cache = {}
        self.cache_ttl = 300  # 5 minutes
        
    async def get_token_price(self, symbol: str, db=None) -> Optional[float]:
        """Get current token price from cache or CoinGecko"""
        cache_key = symbol.upper()
        now = ts_now()
        
        # Check cache
        if cache_key in self.price_cache:
            cached = self.price_cache[cache_key]
            if now - cached["ts"] < self.cache_ttl * 1000:
                return cached["price"]
        
        # Try to get from database (market data)
        if db:
            try:
                token = await db.market_tokens.find_one({"symbol": cache_key})
                if token and token.get("price"):
                    self.price_cache[cache_key] = {"price": token["price"], "ts": now}
                    return token["price"]
            except Exception:
                pass
        
        return None
    
    def calculate_roi_level_a(
        self,
        entry_price: float,
        exit_price: float = None,
        tge_price: float = None,
        current_price: float = None
    ) -> Dict[str, Any]:
        """
        Level A: Realized ROI with actual prices.
        
        Uses actual entry/exit or TGE price data.
        Highest confidence level.
        """
        if not entry_price or entry_price <= 0:
            return self.calculate_roi_level_c(None)
        
        # Determine the comparison price
        compare_price = exit_price or current_price or tge_price
        
        if not compare_price:
            return self.calculate_roi_level_c(None)
        
        multiple = compare_price / entry_price
        pnl_pct = (multiple - 1) * 100
        
        return {
            "level": "A",
            "multiple": round(multiple, 2),
            "pnl_pct": round(pnl_pct, 1),
            "confidence": 0.95,
            "entry_price": entry_price,
            "compare_price": compare_price,
            "method": "realized" if exit_price else "mark_to_market"
        }
    
    def calculate_roi_level_b(
        self,
        entry_date: int,
        valuation_at_entry: float,
        current_fdv: float = None,
        tokens_allocated: float = None
    ) -> Dict[str, Any]:
        """
        Level B: Mark-to-Market using valuation.
        
        Uses entry valuation vs current FDV.
        Medium confidence level.
        """
        if not valuation_at_entry or valuation_at_entry <= 0:
            return self.calculate_roi_level_c(entry_date)
        
        # If we have current FDV
        if current_fdv and current_fdv > 0:
            multiple = current_fdv / valuation_at_entry
            pnl_pct = (multiple - 1) * 100
            
            return {
                "level": "B",
                "multiple": round(multiple, 2),
                "pnl_pct": round(pnl_pct, 1),
                "confidence": 0.75,
                "entry_valuation": valuation_at_entry,
                "current_fdv": current_fdv,
                "method": "valuation_comparison"
            }
        
        # Fall back to Level C
        return self.calculate_roi_level_c(entry_date)
    
    def calculate_roi_level_c(
        self,
        entry_date: int,
        category: str = None,
        round_type: str = None
    ) -> Dict[str, Any]:
        """
        Level C: Time-based proxy ROI.
        
        Uses heuristics based on:
        - Time since investment
        - Round type (seed typically higher multiples)
        - Market conditions (could factor in)
        
        Lowest confidence level.
        """
        if not entry_date:
            return {
                "level": "C",
                "multiple": 1.0,
                "pnl_pct": 0,
                "confidence": 0.2,
                "method": "no_data"
            }
        
        now = ts_now()
        days = (now - entry_date) / (1000 * 60 * 60 * 24)
        
        # Base multiple based on time
        if days > 1095:  # 3+ years
            base_multiple = 4.0
        elif days > 730:  # 2+ years
            base_multiple = 2.5
        elif days > 365:  # 1+ year
            base_multiple = 1.5
        elif days > 180:  # 6+ months
            base_multiple = 1.2
        else:
            base_multiple = 1.0
        
        # Adjust based on round type
        round_multiplier = 1.0
        if round_type:
            round_lower = round_type.lower()
            if "seed" in round_lower:
                round_multiplier = 1.5
            elif "private" in round_lower:
                round_multiplier = 1.3
            elif "strategic" in round_lower:
                round_multiplier = 1.2
        
        # Adjust based on category
        category_multiplier = 1.0
        if category:
            cat_lower = category.lower()
            if cat_lower in ["defi", "l2", "ai"]:
                category_multiplier = 1.2
            elif cat_lower in ["gaming", "nft"]:
                category_multiplier = 0.9
        
        multiple = base_multiple * round_multiplier * category_multiplier
        pnl_pct = (multiple - 1) * 100
        
        return {
            "level": "C",
            "multiple": round(multiple, 2),
            "pnl_pct": round(pnl_pct, 1),
            "confidence": 0.35,
            "method": "time_proxy",
            "factors": {
                "days_held": round(days),
                "round_multiplier": round_multiplier,
                "category_multiplier": category_multiplier
            }
        }
    
    def calculate_best_roi(
        self,
        entry_date: int = None,
        entry_price: float = None,
        current_price: float = None,
        entry_valuation: float = None,
        current_fdv: float = None,
        round_type: str = None,
        category: str = None
    ) -> Dict[str, Any]:
        """
        Calculate ROI using the best available method.
        
        Tries Level A first, then B, then C.
        """
        # Try Level A (actual prices)
        if entry_price and entry_price > 0 and current_price and current_price > 0:
            return self.calculate_roi_level_a(
                entry_price=entry_price,
                current_price=current_price
            )
        
        # Try Level B (valuations)
        if entry_valuation and entry_valuation > 0 and current_fdv and current_fdv > 0:
            return self.calculate_roi_level_b(
                entry_date=entry_date,
                valuation_at_entry=entry_valuation,
                current_fdv=current_fdv
            )
        
        # Fall back to Level C
        return self.calculate_roi_level_c(
            entry_date=entry_date,
            category=category,
            round_type=round_type
        )
    
    def calculate_skill_score(
        self,
        investments: List[Dict[str, Any]],
        weights: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Calculate Skill Score for an investor (fund or person).
        
        Formula:
        - 40% investment_success (weighted avg ROI)
        - 25% pick_rate (% of investments with positive returns)
        - 20% consistency (std dev of returns)
        - 15% timing (early stage premium)
        """
        if weights is None:
            weights = {
                "investment_success": 0.40,
                "pick_rate": 0.25,
                "consistency": 0.20,
                "timing": 0.15
            }
        
        if not investments:
            return {
                "total": 0,
                "grade": "N/A",
                "components": {},
                "confidence": 0
            }
        
        # Calculate ROIs
        rois = []
        positive_count = 0
        early_stage_count = 0
        
        for inv in investments:
            roi = self.calculate_best_roi(
                entry_date=inv.get("date") or inv.get("round_date"),
                entry_price=inv.get("entry_price"),
                current_price=inv.get("current_price"),
                entry_valuation=inv.get("valuation"),
                current_fdv=inv.get("current_fdv"),
                round_type=inv.get("round_type"),
                category=inv.get("category")
            )
            
            multiple = roi.get("multiple", 1.0)
            rois.append(multiple)
            
            if multiple > 1.0:
                positive_count += 1
            
            # Check if early stage
            if inv.get("round_type", "").lower() in ["seed", "private", "pre-seed"]:
                early_stage_count += 1
        
        n = len(rois)
        
        # Investment success (weighted avg multiple)
        avg_roi = sum(rois) / n if n > 0 else 1.0
        success_score = min(avg_roi / 5 * 100, 100)  # 5x = 100
        
        # Pick rate
        pick_rate = positive_count / n * 100 if n > 0 else 0
        
        # Consistency (lower std dev = higher score)
        if n > 1:
            mean = sum(rois) / n
            variance = sum((x - mean) ** 2 for x in rois) / n
            std_dev = math.sqrt(variance)
            consistency_score = max(0, 100 - std_dev * 20)
        else:
            consistency_score = 50
        
        # Timing (early stage premium)
        early_rate = early_stage_count / n * 100 if n > 0 else 0
        timing_score = early_rate
        
        # Total skill score
        total = (
            weights["investment_success"] * success_score +
            weights["pick_rate"] * pick_rate +
            weights["consistency"] * consistency_score +
            weights["timing"] * timing_score
        )
        
        # Grade
        if total >= 80:
            grade = "A"
        elif total >= 65:
            grade = "B"
        elif total >= 50:
            grade = "C"
        elif total >= 35:
            grade = "D"
        else:
            grade = "F"
        
        return {
            "total": round(total, 1),
            "grade": grade,
            "components": {
                "investment_success": round(success_score, 1),
                "pick_rate": round(pick_rate, 1),
                "consistency": round(consistency_score, 1),
                "timing": round(timing_score, 1)
            },
            "stats": {
                "investments_count": n,
                "avg_multiple": round(avg_roi, 2),
                "positive_count": positive_count,
                "early_stage_count": early_stage_count
            },
            "confidence": 0.35 if all(r == 1.0 for r in rois) else 0.6
        }


# Global instance
roi_engine = ROIEngine()
