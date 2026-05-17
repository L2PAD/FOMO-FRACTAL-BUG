"""
Fractal Forecast Pipeline (Multi-scope)
=========================================
Orchestrates three independent pipelines: BTC, SPX, DXY.

CRITICAL ORDER per scope:
  1. resolve (evaluate old pending forecasts)
  2. generate (create new snapshots)

Each scope is fully independent.
"""

from fractal_forecast.evaluator import resolve_forecasts
from fractal_forecast.btc_generator import generate_btc_forecasts
from fractal_forecast.spx_generator import generate_spx_forecasts
from fractal_forecast.dxy_generator import generate_dxy_forecasts
from fractal_forecast.common import ensure_indexes_for_scope

ALL_SCOPES = [
    # Production crypto universe (P1-D.2 expansion).
    # Newer tokens (ARB, OP) may degrade honestly if they lack
    # WINDOW_DAYS + 365 days of history — that is the expected behaviour.
    "BTC", "ETH", "SOL", "DOGE", "LINK", "AVAX",
    "ARB", "OP", "ADA", "BNB", "XRP",
    # Macro anchors (used for regime context, not asset forecasts).
    "SPX", "DXY",
]


def _generate_for_scope(scope: str) -> int:
    """Single dispatch table — every scope uses the native engine."""
    from fractal_forecast.btc_generator import generate_btc_forecasts
    from fractal_forecast.spx_generator import generate_spx_forecasts
    from fractal_forecast.dxy_generator import generate_dxy_forecasts
    # ETH/SOL share the same generator shape — emit through native engine.
    from datetime import datetime, timezone, timedelta
    from fractal_forecast.common import STANDARD_HORIZONS, get_forecast_col
    from fractal_forecast.native_engine import compute_native_forecast
    if scope == "BTC":
        return generate_btc_forecasts()
    if scope == "SPX":
        return generate_spx_forecasts()
    if scope == "DXY":
        return generate_dxy_forecasts()

    # Generic native generator for ETH / SOL (or any future asset).
    col = get_forecast_col(scope)
    now = datetime.now(timezone.utc)
    today_bucket = now.strftime("%Y-%m-%d")
    forecast = compute_native_forecast(scope, STANDARD_HORIZONS)
    if not forecast.get("ok"):
        print(f"[{scope} NativeGen] degraded — reason={forecast.get('reason')}, skipping")
        return 0
    current_price = float(forecast["currentPrice"])
    model_version = forecast["modelVersion"]
    regime = forecast.get("currentRegime") or {}
    generated = 0
    for horizon_key, horizon_days in STANDARD_HORIZONS.items():
        h = forecast["horizons"].get(horizon_key)
        if not h:
            continue
        doc = {
            "scope": scope,
            "createdAt": now,
            "createdBucket": today_bucket,
            "evaluateAt": now + timedelta(days=horizon_days),
            "horizon": horizon_key,
            "entryPrice": current_price,
            "targetPrice": h["targetPrice"],
            "expectedReturn": h["expectedReturn"],
            "direction": h["direction"],
            "confidence": h["confidence"],
            "modelVersion": model_version,
            "source": "fractal_native_v1",
            "signalId": f"fractal_native:{scope}:{horizon_key}:{today_bucket}",
            "entryPriceSource": "yfinance_close",
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
            print(f"[{scope} NativeGen] Insert error ({horizon_key}): {e}")
    print(f"[{scope} NativeGen] Generated {generated} forecasts ({today_bucket}) v={model_version} price={current_price:.2f}")
    return generated


GENERATORS = {s: (lambda s=s: _generate_for_scope(s)) for s in ALL_SCOPES}


def run_pipeline_for_scope(scope: str):
    """Run resolve → generate for a single scope."""
    print(f"[Pipeline] Start {scope}")
    resolved = resolve_forecasts(scope)
    gen_fn = GENERATORS.get(scope)
    generated = gen_fn() if gen_fn else 0
    print(f"[Pipeline] {scope} complete: resolved={resolved}, generated={generated}")
    return {"scope": scope, "resolved": resolved, "generated": generated}


def run_all_pipelines():
    """Run all three pipelines independently."""
    results = {}
    for scope in ALL_SCOPES:
        try:
            results[scope] = run_pipeline_for_scope(scope)
        except Exception as e:
            print(f"[Pipeline] {scope} FAILED: {e}")
            results[scope] = {"scope": scope, "resolved": 0, "generated": 0, "error": str(e)}
    return results


def init_fractal_forecasts():
    """Initialize all collections with indexes."""
    for scope in ALL_SCOPES:
        try:
            ensure_indexes_for_scope(scope)
        except Exception as e:
            print(f"[Pipeline] Index init error for {scope}: {e}")


# Backward compatibility
def run_fractal_forecast_pipeline(scope="BTC"):
    return run_pipeline_for_scope(scope)
