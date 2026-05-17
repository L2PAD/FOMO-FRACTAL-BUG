"""
Structure Feature Extractor V2
==============================
Deterministic, transparent extractor that converts raw price data
into 7 numerical structure features.

Pipeline:
  prices_dict → swing detection → leg identification → BOS/CHOCH → features

Features produced:
  1. structure_bias_score      — trend direction bias [-0.7, 0.7]
  2. structure_trend_score     — trend strength [0, 1]
  3. structure_momentum_score  — short-term impulse [-1, 1]
  4. structure_reversal_risk   — CHOCH-based reversal probability [0, 1]
  5. structure_stability_score — structure clarity [0, 1]
  6. structure_exhaustion_score — late-trend decay [0, 1]
  7. structure_compression_score — range compression [0, 1]
"""

from forecast.structure.config import SWING_CONFIG


EMPTY_FEATURES = {
    "structure_bias_score": 0.0,
    "structure_trend_score": 0.0,
    "structure_momentum_score": 0.0,
    "structure_reversal_risk": 0.0,
    "structure_stability_score": 0.0,
    "structure_exhaustion_score": 0.0,
    "structure_compression_score": 0.0,
}


class StructureFeatureExtractor:
    """Extracts market structure features from price series."""

    def extract_from_prices(self, prices_dict: dict, profile: dict | None = None) -> dict:
        """
        Main entry point. Takes prices_dict {date_str: price}
        and returns 7 structure features.
        Optional profile overrides lookback and min_move_pct.
        """
        p = profile or {}
        lookback = p.get("lookback", SWING_CONFIG["lookback"])
        min_candles = p.get("min_candles", SWING_CONFIG["min_candles"])
        min_move_pct = p.get("min_move_pct", 0.0)

        if not prices_dict or len(prices_dict) < min_candles:
            return dict(EMPTY_FEATURES)

        sorted_dates = sorted(prices_dict.keys())
        prices = [prices_dict[d] for d in sorted_dates]

        swings = self._detect_swings(prices, lookback=lookback, min_move_pct=min_move_pct)
        if len(swings) < 3:
            return dict(EMPTY_FEATURES)

        legs = self._build_legs(swings)
        if not legs:
            return dict(EMPTY_FEATURES)

        trend = self._determine_trend(swings)
        bos_events = self._detect_bos(swings, trend)
        choch_events = self._detect_choch(swings, trend)

        total_legs = max(len(legs), 1)

        bias = self._trend_bias(trend)
        trend_strength = min(1.0, len(bos_events) / total_legs)
        momentum = self._structure_momentum(legs)
        reversal_risk = min(1.0, len(choch_events) / total_legs)
        stability = self._structure_stability(legs, choch_events)
        exhaustion = self._trend_exhaustion(legs)
        compression = self._compression_score(legs)

        return {
            "structure_bias_score": round(bias, 4),
            "structure_trend_score": round(trend_strength, 4),
            "structure_momentum_score": round(momentum, 4),
            "structure_reversal_risk": round(reversal_risk, 4),
            "structure_stability_score": round(stability, 4),
            "structure_exhaustion_score": round(exhaustion, 4),
            "structure_compression_score": round(compression, 4),
        }

    def extract_from_structure(self, structure_data: dict) -> dict:
        """
        Alternative entry point. Takes pre-computed structure payload
        (with trend, swings, legs, bos_events, choch_events).
        Falls back to empty if structure_data is missing.
        """
        if not structure_data:
            return dict(EMPTY_FEATURES)

        trend = structure_data.get("trend")
        legs = structure_data.get("legs", [])
        bos_events = structure_data.get("bos_events", [])
        choch_events = structure_data.get("choch_events", [])

        total_legs = max(len(legs), 1)

        bias = self._trend_bias(trend)
        trend_strength = min(1.0, len(bos_events) / total_legs)
        momentum = self._structure_momentum(legs)
        reversal_risk = min(1.0, len(choch_events) / total_legs)
        stability = self._structure_stability(legs, choch_events)
        exhaustion = self._trend_exhaustion(legs)
        compression = self._compression_score(legs)

        return {
            "structure_bias_score": round(bias, 4),
            "structure_trend_score": round(trend_strength, 4),
            "structure_momentum_score": round(momentum, 4),
            "structure_reversal_risk": round(reversal_risk, 4),
            "structure_stability_score": round(stability, 4),
            "structure_exhaustion_score": round(exhaustion, 4),
            "structure_compression_score": round(compression, 4),
        }

    # ═══════════════════════════════════════════════════════
    # Swing Detection
    # ═══════════════════════════════════════════════════════

    def _detect_swings(self, prices: list[float], lookback: int = 5, min_move_pct: float = 0.0) -> list[dict]:
        """
        Detect swing highs and lows from price series.
        A swing high: local max within lookback window.
        A swing low: local min within lookback window.
        min_move_pct: filter out swings where the move from prev swing
        is less than this percentage (0 = no filter).
        Returns list of {index, price, type: 'high'|'low'}.
        """
        swings = []

        for i in range(lookback, len(prices) - lookback):
            window_before = prices[i - lookback:i]
            window_after = prices[i + 1:i + 1 + lookback]

            is_high = all(prices[i] > p for p in window_before) and all(prices[i] > p for p in window_after)
            is_low = all(prices[i] < p for p in window_before) and all(prices[i] < p for p in window_after)

            if is_high:
                if not swings or swings[-1]["type"] != "high":
                    swings.append({"index": i, "price": prices[i], "type": "high"})
                elif prices[i] > swings[-1]["price"]:
                    swings[-1] = {"index": i, "price": prices[i], "type": "high"}

            if is_low:
                if not swings or swings[-1]["type"] != "low":
                    swings.append({"index": i, "price": prices[i], "type": "low"})
                elif prices[i] < swings[-1]["price"]:
                    swings[-1] = {"index": i, "price": prices[i], "type": "low"}

        # Filter by min_move_pct
        if min_move_pct > 0 and len(swings) > 1:
            filtered = [swings[0]]
            for s in swings[1:]:
                prev = filtered[-1]
                move_pct = abs(s["price"] - prev["price"]) / prev["price"] * 100
                if move_pct >= min_move_pct:
                    filtered.append(s)
                elif s["type"] == prev["type"]:
                    # Same type: keep the more extreme one
                    if (s["type"] == "high" and s["price"] > prev["price"]) or \
                       (s["type"] == "low" and s["price"] < prev["price"]):
                        filtered[-1] = s
            swings = filtered

        return swings

    # ═══════════════════════════════════════════════════════
    # Leg Construction
    # ═══════════════════════════════════════════════════════

    def _build_legs(self, swings: list[dict]) -> list[dict]:
        """
        Build legs from consecutive swings.
        A leg = movement from one swing to the next.
        """
        legs = []
        for i in range(1, len(swings)):
            prev = swings[i - 1]
            curr = swings[i]
            size = curr["price"] - prev["price"]
            direction = "up" if size > 0 else "down"
            legs.append({
                "direction": direction,
                "size": size,
                "abs_size": abs(size),
                "from_price": prev["price"],
                "to_price": curr["price"],
                "from_type": prev["type"],
                "to_type": curr["type"],
            })
        return legs

    # ═══════════════════════════════════════════════════════
    # Trend Determination
    # ═══════════════════════════════════════════════════════

    def _determine_trend(self, swings: list[dict]) -> str:
        """
        Determine trend from swing pattern.
        Uptrend: HH + HL (higher highs + higher lows)
        Downtrend: LL + LH (lower lows + lower highs)
        Range: mixed signals
        """
        if len(swings) < 4:
            return "range"

        swing_highs = [s for s in swings if s["type"] == "high"]
        swing_lows = [s for s in swings if s["type"] == "low"]

        hh_count = 0
        lh_count = 0
        for i in range(1, len(swing_highs)):
            if swing_highs[i]["price"] > swing_highs[i - 1]["price"]:
                hh_count += 1
            else:
                lh_count += 1

        hl_count = 0
        ll_count = 0
        for i in range(1, len(swing_lows)):
            if swing_lows[i]["price"] > swing_lows[i - 1]["price"]:
                hl_count += 1
            else:
                ll_count += 1

        bull_score = hh_count + hl_count
        bear_score = ll_count + lh_count
        total = max(bull_score + bear_score, 1)

        if bull_score / total >= 0.6:
            return "uptrend"
        if bear_score / total >= 0.6:
            return "downtrend"
        return "range"

    # ═══════════════════════════════════════════════════════
    # BOS / CHOCH Detection
    # ═══════════════════════════════════════════════════════

    def _detect_bos(self, swings: list[dict], trend: str) -> list[dict]:
        """
        Break of Structure (BOS):
        In uptrend: new swing high breaks previous swing high
        In downtrend: new swing low breaks previous swing low
        """
        bos_events = []
        swing_highs = [s for s in swings if s["type"] == "high"]
        swing_lows = [s for s in swings if s["type"] == "low"]

        if trend == "uptrend":
            for i in range(1, len(swing_highs)):
                if swing_highs[i]["price"] > swing_highs[i - 1]["price"]:
                    bos_events.append({
                        "type": "bos_bull",
                        "price": swing_highs[i]["price"],
                        "prev_price": swing_highs[i - 1]["price"],
                    })
        elif trend == "downtrend":
            for i in range(1, len(swing_lows)):
                if swing_lows[i]["price"] < swing_lows[i - 1]["price"]:
                    bos_events.append({
                        "type": "bos_bear",
                        "price": swing_lows[i]["price"],
                        "prev_price": swing_lows[i - 1]["price"],
                    })

        return bos_events

    def _detect_choch(self, swings: list[dict], trend: str) -> list[dict]:
        """
        Change of Character (CHOCH):
        In uptrend: swing low breaks previous swing low (bearish CHOCH)
        In downtrend: swing high breaks previous swing high (bullish CHOCH)
        """
        choch_events = []
        swing_highs = [s for s in swings if s["type"] == "high"]
        swing_lows = [s for s in swings if s["type"] == "low"]

        if trend == "uptrend":
            for i in range(1, len(swing_lows)):
                if swing_lows[i]["price"] < swing_lows[i - 1]["price"]:
                    choch_events.append({
                        "type": "choch_bear",
                        "price": swing_lows[i]["price"],
                        "prev_price": swing_lows[i - 1]["price"],
                    })
        elif trend == "downtrend":
            for i in range(1, len(swing_highs)):
                if swing_highs[i]["price"] > swing_highs[i - 1]["price"]:
                    choch_events.append({
                        "type": "choch_bull",
                        "price": swing_highs[i]["price"],
                        "prev_price": swing_highs[i - 1]["price"],
                    })

        return choch_events

    # ═══════════════════════════════════════════════════════
    # Feature Calculators
    # ═══════════════════════════════════════════════════════

    def _trend_bias(self, trend: str) -> float:
        if trend == "uptrend":
            return 0.7
        if trend == "downtrend":
            return -0.7
        return 0.0

    def _structure_momentum(self, legs: list[dict]) -> float:
        """Last 3 legs weighted momentum."""
        if not legs:
            return 0.0

        last_legs = legs[-3:]
        score = 0.0
        for i, leg in enumerate(last_legs):
            direction = 1.0 if leg["direction"] == "up" else -1.0
            weight = (i + 1) / len(last_legs)
            score += direction * weight

        return max(-1.0, min(1.0, score))

    def _structure_stability(self, legs: list[dict], choch_events: list) -> float:
        """High stability = few CHOCH relative to legs."""
        if not legs:
            return 0.0
        chop = len(choch_events) / len(legs)
        return max(0.0, min(1.0, 1.0 - chop))

    def _trend_exhaustion(self, legs: list[dict]) -> float:
        """
        If leg sizes are shrinking → exhaustion is rising.
        Compares last leg size to first of the last 3 legs.
        """
        if len(legs) < 3:
            return 0.0

        last_sizes = [leg["abs_size"] for leg in legs[-3:]]
        if last_sizes[0] == 0:
            return 0.0

        decay = last_sizes[-1] / last_sizes[0]
        return max(0.0, min(1.0, 1.0 - decay))

    def _compression_score(self, legs: list[dict]) -> float:
        """
        Small uniform legs → compression → breakout potential.
        High variance in leg sizes → no compression.
        """
        if len(legs) < 5:
            return 0.0

        sizes = [leg["abs_size"] for leg in legs[-5:]]
        avg = sum(sizes) / len(sizes)
        if avg == 0:
            return 0.0

        normalized_sizes = [s / avg for s in sizes]
        variance = sum((x - 1.0) ** 2 for x in normalized_sizes) / len(normalized_sizes)

        return max(0.0, min(1.0, 1.0 - variance))
