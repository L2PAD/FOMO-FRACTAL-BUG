"""
Forecast Generator v4
======================
Regime-anchored forecasting with:
- 7D: point target (meanReturn center, MAE cap, NEUTRAL filter, optimism guard)
- 30D: probabilistic band (medianReturn center, p25/p75 core, p10/p90 wide)
- Live regime hysteresis (3-day consistent signal before regime change)
"""

import hashlib
import math
import uuid
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

from forecast import ForecastRecord, Horizon, HORIZON_DAYS
from forecast.price_provider import get_current_price, get_price_series


def _get_db():
    from forecast.repo import _cfg
    c = _cfg()
    return MongoClient(c.mongo_url)[c.db_name]


def _compute_features(prices: dict[str, float], as_of_date: str) -> dict | None:
    sorted_dates = sorted(d for d in prices if d <= as_of_date)
    if len(sorted_dates) < 14:
        return None

    closes = [prices[d] for d in sorted_dates[-14:]]
    current = closes[-1]
    ret_1d = (closes[-1] - closes[-2]) / closes[-2]
    ret_7d = (closes[-1] - closes[-8]) / closes[-8] if len(closes) >= 8 else 0
    ret_14d = (closes[-1] - closes[0]) / closes[0]

    daily_returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    volatility = (sum(r**2 for r in daily_returns) / len(daily_returns)) ** 0.5

    momentum = ret_1d * 0.5 + ret_7d * 0.3 + ret_14d * 0.2

    features_hash = hashlib.sha256(
        f"{current:.2f}:{ret_1d:.6f}:{ret_7d:.6f}:{volatility:.6f}".encode()
    ).hexdigest()[:16]

    return {
        "price": current,
        "ret_1d": ret_1d,
        "ret_7d": ret_7d,
        "ret_14d": ret_14d,
        "volatility": volatility,
        "momentum": momentum,
        "features_hash": features_hash,
    }


def _compute_raw_regime(prices_dict: dict) -> str:
    """Compute raw regime signal from recent prices using absolute thresholds."""
    dates = sorted(prices_dict.keys())
    if len(dates) < 14:
        return "TRANSITION"

    n = min(30, len(dates))
    prices = [prices_dict[d] for d in dates[-n:]]
    returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]

    vol_30d = (sum(r ** 2 for r in returns) / len(returns)) ** 0.5 * math.sqrt(365) if returns else 0
    ma_period = len(prices)
    ma = sum(prices) / ma_period
    ma_5ago = sum(prices[:-5]) / max(1, ma_period - 5) if ma_period > 5 else ma
    slope = (ma - ma_5ago) / ma_5ago if ma_5ago > 0 else 0
    max_7d = max(prices[-7:]) if len(prices) >= 7 else prices[-1]
    drawdown = (prices[-1] - max_7d) / max_7d if max_7d > 0 else 0

    if drawdown < -0.10 and vol_30d > 0.50:
        return "RISK_OFF"
    if abs(slope) > 0.002 and vol_30d <= 0.85:
        return "TREND"
    if vol_30d <= 0.45 and abs(slope) <= 0.002 and drawdown > -0.10:
        return "RANGE"
    return "TRANSITION"


def _apply_live_hysteresis(asset: str, horizon_key: str, raw_regime: str) -> tuple:
    """
    Record daily regime signal and apply 3-day hysteresis.
    Returns (confirmed_regime, regime_confidence).
    """
    db = _get_db()
    bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    db["regime_signals"].update_one(
        {"asset": asset, "horizon": horizon_key, "date": bucket},
        {"$set": {"raw_regime": raw_regime, "ts": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )

    signals = list(db["regime_signals"].find(
        {"asset": asset, "horizon": horizon_key},
        {"_id": 0, "raw_regime": 1, "date": 1},
    ).sort("date", DESCENDING).limit(5))

    if len(signals) < 3:
        return raw_regime, 0.5

    last_3 = [s["raw_regime"] for s in signals[:3]]
    if len(set(last_3)) == 1:
        confirmed = last_3[0]
        last_5 = [s["raw_regime"] for s in signals[:5]]
        conf = 0.9 if len(set(last_5)) == 1 else 0.75
        return confirmed, conf

    # Not consistent → keep previous confirmed regime
    prev = db["drift_snapshots"].find_one(
        {"asset": asset, "horizon": horizon_key},
        {"_id": 0, "regime": 1, "regimeConfidence": 1},
        sort=[("ts", DESCENDING)],
    )
    if prev:
        return prev.get("regime", "TRANSITION"), prev.get("regimeConfidence", 0.5)
    return "TRANSITION", 0.5


def _get_regime_data(asset: str, horizon_key: str, prices_dict: dict = None) -> dict:
    try:
        db = _get_db()

        # Live hysteresis-based regime detection
        if prices_dict:
            raw = _compute_raw_regime(prices_dict)
            regime, regime_conf = _apply_live_hysteresis(asset, horizon_key, raw)
        else:
            snap = db["drift_snapshots"].find_one(
                {"asset": asset, "horizon": horizon_key},
                {"_id": 0, "regime": 1, "regimeConfidence": 1},
                sort=[("ts", DESCENDING)],
            )
            regime = snap.get("regime", "TRANSITION") if snap else "TRANSITION"
            regime_conf = snap.get("regimeConfidence", 0.5) if snap else 0.5

        baseline_doc = db["drift_regime_baselines"].find_one(
            {"regime": regime, "horizon": horizon_key},
            {"_id": 0, "baseline": 1},
        )
        baseline = baseline_doc.get("baseline", {}) if baseline_doc else {}

        return {
            "regime": regime,
            "regimeConfidence": regime_conf,
            "maeMean": baseline.get("mae_mean", 0.05),
            "dirHitMean": baseline.get("dir_hit_mean", 0.5),
            "meanReturn": baseline.get("mean_return", 0.0),
            "stdReturn": baseline.get("std_return", 0.05),
            "medianReturn": baseline.get("median_return", 0.0),
            "p25Return": baseline.get("p25_return", -0.05),
            "p75Return": baseline.get("p75_return", 0.05),
            "sampleSize": baseline.get("n", 0),
        }
    except Exception:
        return {
            "regime": "TRANSITION",
            "regimeConfidence": 0.5,
            "maeMean": 0.05,
            "dirHitMean": 0.5,
            "meanReturn": 0.0,
            "stdReturn": 0.05,
            "medianReturn": 0.0,
            "p25Return": -0.05,
            "p75Return": 0.05,
            "sampleSize": 0,
        }


def _get_recent_performance(asset: str, horizon_key: str) -> dict:
    """Get rolling performance for meta-shrinkage."""
    try:
        db = _get_db()
        recent = list(db["exchange_forecasts"].find(
            {"asset": asset, "horizon": horizon_key, "outcome": {"$ne": None}},
            {"_id": 0, "outcome": 1},
        ).sort("createdBucket", DESCENDING).limit(5))
        if not recent:
            return {"rollingWinRate": 0.5, "recentCount": 0}
        wins = sum(1 for r in recent if r.get("outcome", {}).get("label") == "TP")
        return {"rollingWinRate": wins / len(recent), "recentCount": len(recent)}
    except Exception:
        return {"rollingWinRate": 0.5, "recentCount": 0}


def generate_forecast(asset: str, horizon: Horizon, model_version: str = "v4.0.0", run_id: str = "") -> ForecastRecord | None:
    """
    v4 Forecast Generator:
    - 7D/24H: Point target (v3 logic + optimism guards)
    - 30D: Band architecture (probabilistic range, not point)
    """
    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)
    bucket = now.strftime("%Y-%m-%d")
    horizon_days = HORIZON_DAYS[horizon]
    horizon_key = horizon.value

    start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    prices = get_price_series(asset, start, end)

    features = _compute_features(prices, bucket)
    if not features:
        return None

    price = features["price"]

    # Deterministic seed
    seed_str = f"{bucket}:{horizon.value}:{asset}:{model_version}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
    perturbation = ((seed % 1000) / 1000 - 0.5) * 0.02

    # ── Regime data (with live hysteresis) ──
    regime_data = _get_regime_data(asset, horizon_key, prices)
    regime = regime_data["regime"]
    mean_return = regime_data["meanReturn"]
    std_return = regime_data["stdReturn"]
    mae_mean = regime_data["maeMean"]
    median_return = regime_data["medianReturn"]
    p25_return = regime_data["p25Return"]
    p75_return = regime_data["p75Return"]

    # Regime shrinkage
    regime_shrinkage = 1.0
    if regime == "TRANSITION":
        regime_shrinkage = 0.6
    elif regime == "RISK_OFF":
        regime_shrinkage = 0.7

    # Meta-shrinkage from recent performance
    perf = _get_recent_performance(asset, horizon_key)

    # Common finalization helper
    evaluate_after = now_ms + horizon_days * 86_400_000
    forecast_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, seed_str))

    if horizon_key == "30D":
        # ═══════════════════════════════════════════════════
        # 30D BAND ARCHITECTURE (v4)
        # Distribution range, not point target
        # ═══════════════════════════════════════════════════

        # Band = raw regime percentiles (no shrinkage — honest range)
        band_core_low = round(price * (1 + p25_return), 2)
        band_core_high = round(price * (1 + p75_return), 2)

        # Estimate p10/p90 from IQR extension
        iqr = p75_return - p25_return
        p10_est = p25_return - 0.75 * iqr
        p90_est = p75_return + 0.75 * iqr
        band_wide_low = round(price * (1 + p10_est), 2)
        band_wide_high = round(price * (1 + p90_est), 2)

        # Median target with shrinkage (conservative center)
        shrinkage = 0.75 * regime_shrinkage
        median_target = round(price * (1 + median_return * shrinkage), 2)

        # Direction = bias from median
        neutral_threshold = 0.25 * std_return
        if median_return > neutral_threshold:
            direction = "LONG"
        elif median_return < -neutral_threshold:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"

        # TRANSITION with weak signal → NEUTRAL
        if regime == "TRANSITION" and abs(median_return) < 0.5 * std_return:
            direction = "NEUTRAL"

        # Confidence = signal strength (NOT dirHitRate for 30D)
        signal_strength = abs(median_return) / max(std_return, 0.001)
        confidence = min(0.85, max(0.10, signal_strength * 0.7))
        confidence *= min(1.0, regime_data["regimeConfidence"])

        # Meta-shrinkage penalty on confidence
        if perf["recentCount"] >= 3 and perf["rollingWinRate"] < 0.25:
            confidence *= 0.85

        confidence = round(max(0.10, min(0.85, confidence)), 4)
        confidence_raw = round(signal_strength, 4)

        # Performance throttle
        if perf["recentCount"] >= 5 and perf["rollingWinRate"] < 0.15:
            direction = "NEUTRAL"

        target_price = median_target
        move_pct = round(((median_target - price) / price) * 100, 2)

        immutable_hash = hashlib.sha256(
            f"{forecast_id}:{target_price}:{direction}:{confidence}".encode()
        ).hexdigest()[:16]

        return ForecastRecord(
            id=forecast_id,
            asset=asset,
            symbol=f"{asset}USDT",
            horizon=horizon,
            horizonDays=horizon_days,
            runId=run_id,
            createdAt=now_ms,
            createdBucket=bucket,
            evaluateAfter=evaluate_after,
            entryPrice=round(price, 2),
            targetPrice=target_price,
            expectedMovePct=move_pct,
            direction=direction,
            confidence=confidence,
            confidenceRaw=confidence_raw,
            modelVersion=model_version,
            featuresHash=features["features_hash"],
            immutableHash=immutable_hash,
            dataWindowEnd=now_ms,
            source="scheduler",
            forecastType="band",
            medianTarget=median_target,
            bandCoreLow=band_core_low,
            bandCoreHigh=band_core_high,
            bandWideLow=band_wide_low,
            bandWideHigh=band_wide_high,
        )

    else:
        # ═══════════════════════════════════════════════════
        # 7D / 24H POINT TARGET (v3 + optimism guards)
        # ═══════════════════════════════════════════════════

        momentum = features["momentum"]
        bull_score = 0.5 + momentum * 8 + perturbation
        bull_score = max(0.05, min(0.95, bull_score))

        # NEUTRAL filter
        neutral_threshold = 0.25 * std_return
        regime_direction_clear = abs(mean_return) > neutral_threshold

        if bull_score > 0.58 and regime_direction_clear:
            direction = "LONG"
        elif bull_score < 0.42 and regime_direction_clear:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"

        # TRANSITION penalty
        if regime == "TRANSITION" and abs(bull_score - 0.5) < 0.12:
            direction = "NEUTRAL"

        # Expected Move (regime-anchored)
        base_shrinkage = 0.75
        total_shrinkage = base_shrinkage * regime_shrinkage

        if direction == "LONG":
            move_raw = abs(mean_return) * total_shrinkage
        elif direction == "SHORT":
            move_raw = -abs(mean_return) * total_shrinkage
        else:
            move_raw = mean_return * total_shrinkage * 0.3

        # Volatility adjustment
        vol_ratio = min(2.0, max(0.5, features["volatility"] / max(0.005, std_return * 0.15)))
        move_adjusted = move_raw * vol_ratio

        # CAP at 1.5 * MAE (safety)
        move_cap = 1.5 * mae_mean
        move_adjusted = max(-move_cap, min(move_cap, move_adjusted))

        # Optimism guard: cap at estimated p90 of regime returns
        p90_guard = p75_return + 0.75 * (p75_return - p25_return)
        if move_adjusted > 0 and move_adjusted > p90_guard:
            move_adjusted = p90_guard
        elif move_adjusted < 0 and abs(move_adjusted) > abs(p90_guard):
            move_adjusted = -abs(p90_guard)

        # Confidence
        dir_hit_rate = regime_data["dirHitMean"]
        regime_confidence = regime_data["regimeConfidence"]
        shrinkage_conf = 0.85
        vol_percentile = min(1.0, features["volatility"] / 0.04)
        vol_penalty = 1.0 - vol_percentile * 0.3

        confidence = dir_hit_rate * regime_confidence * shrinkage_conf * vol_penalty
        # Clamp confidence to not exceed historical hit rate
        confidence = min(confidence, dir_hit_rate * 0.9)
        confidence = round(max(0.10, min(0.85, confidence)), 4)
        confidence_raw = round(dir_hit_rate * regime_confidence, 4)

        # Partial confidence scaling
        move_final = move_adjusted * (0.5 + 0.5 * confidence)

        # Meta-shrinkage
        if perf["recentCount"] >= 3 and perf["rollingWinRate"] < 0.25:
            move_final *= 0.8
            confidence = round(confidence * 0.85, 4)

        # Performance throttle
        if perf["recentCount"] >= 5 and perf["rollingWinRate"] < 0.15:
            direction = "NEUTRAL"
            move_final = mean_return * 0.1

        move_pct = round(move_final * 100, 2)
        target_price = round(price * (1 + move_pct / 100), 2)

        immutable_hash = hashlib.sha256(
            f"{forecast_id}:{target_price}:{direction}:{confidence}".encode()
        ).hexdigest()[:16]

        return ForecastRecord(
            id=forecast_id,
            asset=asset,
            symbol=f"{asset}USDT",
            horizon=horizon,
            horizonDays=horizon_days,
            runId=run_id,
            createdAt=now_ms,
            createdBucket=bucket,
            evaluateAfter=evaluate_after,
            entryPrice=round(price, 2),
            targetPrice=target_price,
            expectedMovePct=move_pct,
            direction=direction,
            confidence=confidence,
            confidenceRaw=confidence_raw,
            modelVersion=model_version,
            featuresHash=features["features_hash"],
            immutableHash=immutable_hash,
            dataWindowEnd=now_ms,
            source="scheduler",
        )
