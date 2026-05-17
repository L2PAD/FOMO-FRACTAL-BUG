"""
Fractal Adapter for System Aggregator
=======================================
Fetches latest fractal signal for a given asset.
Converts fractal forecast into a directional bias signal.

BLOCK 1: Fractals -> Active Signal
- If abs(expected_return) < 0.03 -> signal = 0
- Else: signal = +1/-1 based on return sign
- confidence = min(0.8, abs(expected_return) * 2)
"""


def fetch_fractal_signal(db, asset: str) -> dict:
    """
    Fetch latest fractal signal for a given asset.

    Looks in {asset}_fractal_forecasts for the most recent pending forecast.
    Returns: {"signal": float, "confidence": float, "direction": str, "horizon": str}
    """
    if db is None:
        return {"signal": 0.0, "confidence": 0.0, "direction": "NEUTRAL", "horizon": "N/A"}

    try:
        scope = asset.upper()
        col_name = f"{scope.lower()}_fractal_forecasts"
        col = db[col_name]

        # Get latest forecast (prefer pending, fallback to resolved)
        doc = col.find_one(
            {"status": "pending"},
            {"_id": 0, "direction": 1, "expectedReturn": 1, "confidence": 1, "horizon": 1},
            sort=[("createdAt", -1)],
        )
        if not doc:
            doc = col.find_one(
                {},
                {"_id": 0, "direction": 1, "expectedReturn": 1, "confidence": 1, "horizon": 1},
                sort=[("createdAt", -1)],
            )
        if not doc:
            return {"signal": 0.0, "confidence": 0.0, "direction": "NEUTRAL", "horizon": "N/A"}

        expected_return = doc.get("expectedReturn", 0) or 0
        direction = doc.get("direction", "NEUTRAL")
        horizon = doc.get("horizon", "N/A")

        # BLOCK 1: Convert to active signal
        if abs(expected_return) < 0.03:
            fractal_signal = 0.0
        elif expected_return > 0:
            fractal_signal = 1.0
        else:
            fractal_signal = -1.0

        fractal_confidence = min(0.8, abs(expected_return) * 2)

        return {
            "signal": round(fractal_signal, 4),
            "confidence": round(fractal_confidence, 4),
            "direction": direction,
            "horizon": horizon,
            "expected_return": round(expected_return, 6),
        }

    except Exception:
        return {"signal": 0.0, "confidence": 0.0, "direction": "NEUTRAL", "horizon": "N/A"}
