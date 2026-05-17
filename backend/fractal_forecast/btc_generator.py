"""
BTC Fractal Forecast Generator (P1 · fractal_native_v1)
========================================================
Native Python generator — REPLACES the Node :8003 sidecar dependency.
Honest recurrence / cycle / macro-analog logic via fractal_forecast.native_engine.

NEVER reads `decision_history` as a primary source.  NEVER uses TA
heuristics.  source = "fractal_native_v1".
"""

from datetime import datetime, timezone, timedelta

from fractal_forecast.common import STANDARD_HORIZONS, get_forecast_col
from fractal_forecast.native_engine import compute_native_forecast


SCOPE = "BTC"

# Direction tag from engine → canonical direction stored on the doc.
# Stays at UP/DOWN/NEUTRAL for backward compatibility with the
# evaluator & runtime, which expect these tokens.
_DIR_MAP = {"UP": "UP", "DOWN": "DOWN", "NEUTRAL": "NEUTRAL"}


def generate_btc_forecasts() -> int:
    col = get_forecast_col(SCOPE)
    now = datetime.now(timezone.utc)
    today_bucket = now.strftime("%Y-%m-%d")

    forecast = compute_native_forecast(SCOPE, STANDARD_HORIZONS)
    if not forecast.get("ok"):
        print(f"[BTC NativeGen] degraded — reason={forecast.get('reason')}, skipping")
        return 0

    current_price = float(forecast["currentPrice"])
    model_version = forecast["modelVersion"]
    regime = forecast.get("currentRegime") or {}

    generated = 0
    for horizon_key, horizon_days in STANDARD_HORIZONS.items():
        h = forecast["horizons"].get(horizon_key)
        if not h:
            continue
        direction = _DIR_MAP.get(h["direction"], "NEUTRAL")
        doc = {
            "scope": SCOPE,
            "createdAt": now,
            "createdBucket": today_bucket,
            "evaluateAt": now + timedelta(days=horizon_days),
            "horizon": horizon_key,
            "entryPrice": current_price,
            "targetPrice": h["targetPrice"],
            "expectedReturn": h["expectedReturn"],
            "direction": direction,
            "confidence": h["confidence"],
            "modelVersion": model_version,
            "source": "fractal_native_v1",
            "signalId": f"fractal_native:{SCOPE}:{horizon_key}:{today_bucket}",
            "entryPriceSource": "yfinance_close",
            # P1 transparency — full audit trail of how the forecast
            # was produced (recurrence / analog / regime).  Honest by
            # construction: no number here is fabricated.
            "nativeMeta": {
                "analogCount":    h["analogCount"],
                "avgSimilarity":  h["avgSimilarity"],
                "agreeShare":     h["agreeShare"],
                "regime":         regime,
                "horizonDays":    h["horizonDays"],
            },
            "actualPrice": None,
            "errorPct": None,
            "hit": None,
            "directionCorrect": None,
            "status": "pending",
        }
        try:
            col.insert_one(doc)
            generated += 1
        except Exception as e:
            if "duplicate key" in str(e).lower() or "E11000" in str(e):
                continue
            print(f"[BTC NativeGen] Insert error ({horizon_key}): {e}")

    print(f"[BTC NativeGen] Generated {generated} forecasts ({today_bucket}) v={model_version} price=${current_price:.2f} regime={regime.get('spxBucket')} dxyTrend={regime.get('dxyTrend')}")
    return generated
