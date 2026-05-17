"""
ML Overlay — API Routes
"""

import traceback
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/ml-overlay", tags=["ml-overlay"])


@router.get("/status")
async def overlay_status():
    """Get ML overlay system status with shadow eval summary and graduation."""
    import json
    import os
    from pymongo import MongoClient, DESCENDING
    from ml_overlay.model.registry import get_registry_status
    from ml_overlay.runtime.shadow_logger import get_shadow_count
    from ml_overlay.eval_shadow import get_shadow_eval_summary
    from ml_overlay.graduation import get_effective_alpha

    models = get_registry_status()
    shadow_count = get_shadow_count()
    eval_summary = get_shadow_eval_summary()

    # Graduation per horizon
    graduation = {}
    for h in ["7D", "30D"]:
        graduation[h] = get_effective_alpha(horizon=h)

    # Calibration from latest drift snapshot
    calibration = {}
    try:
        db = MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]
        for h in ["7D", "30D"]:
            snap = db["drift_snapshots"].find_one(
                {"horizon": h, "asset": "BTC"},
                {"_id": 0, "calibration": 1},
                sort=[("ts", DESCENDING)],
            )
            if snap and snap.get("calibration"):
                calibration[h] = snap["calibration"]
    except Exception:
        pass

    # Pruning info
    pruning = None
    features_path = os.path.join(os.path.dirname(__file__), "artifacts", "selected_features.json")
    if os.path.exists(features_path):
        with open(features_path) as f:
            sf = json.load(f)
            pruning = {}
            for h in ["7D", "30D"]:
                hd = sf.get("horizons", {}).get(h, {})
                if hd:
                    pruning[h] = {
                        "selected": hd.get("selected", []),
                        "prunedCount": len(hd.get("pruned", [])),
                    }

    return {
        "ok": True,
        "models": models,
        "shadowLogs": shadow_count,
        "evalSummary": eval_summary,
        "graduation": graduation,
        "calibration": calibration,
        "pruning": pruning,
    }


@router.post("/train")
async def trigger_train(
    horizon: str = Query("7D"),
    years: int = Query(7),
):
    """Train model with walk-forward validation."""
    try:
        from ml_overlay.data.price_provider import get_ohlcv
        from ml_overlay.data.dataset_builder import build_dataset
        from ml_overlay.model.train import train_model
        from ml_overlay.model.walk_forward import run_walk_forward
        from ml_overlay.model.registry import save_model

        ohlcv = get_ohlcv("BTC-USD", years=years)
        dataset = build_dataset(ohlcv, horizon)
        wf_results = run_walk_forward(dataset, horizon)

        train_end = dataset.index.max().strftime("%Y-%m-%d")
        final_model = train_model(dataset, train_end, horizon)
        model_id = save_model(final_model, wf_results)

        return {
            "ok": True,
            "modelId": model_id,
            "horizon": horizon,
            "dataRows": len(dataset),
            "trainRows": final_model["trainRows"],
            "walkForward": wf_results,
            "featureImportance": final_model["featureImportance"],
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )


@router.get("/predict")
async def predict_overlay(
    asset: str = Query("BTC"),
    horizon: str = Query("7D"),
):
    """Run ML overlay prediction with full gate pipeline."""
    try:
        from ml_overlay.data.price_provider import get_ohlcv
        from ml_overlay.features.compute_features import compute_features_single
        from ml_overlay.runtime.overlay_service import compute_overlay
        from ml_overlay.runtime.shadow_logger import log_shadow

        import os
        import hashlib
        from pymongo import MongoClient, DESCENDING
        from datetime import datetime, timezone

        client = MongoClient(os.environ.get("MONGO_URL"))
        db = client["intelligence_engine"]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Get rule forecast
        rule_doc = db["exchange_forecasts"].find_one(
            {"asset": asset, "horizon": horizon, "createdBucket": today},
            {"_id": 0},
        )
        if not rule_doc:
            return {"ok": False, "error": f"No rule forecast for {asset}/{horizon}/{today}"}

        entry_price = rule_doc.get("basePrice") or rule_doc.get("entryPrice", 0)
        rule_target = rule_doc.get("targetPrice", entry_price)
        conf_rule = rule_doc.get("confidence", 0.1)

        # Get previous ML correction for smoothing gate
        prev_shadow = db["ml_overlay_shadow"].find_one(
            {"asset": asset, "horizon": horizon, "createdBucket": {"$lt": today}},
            {"_id": 0, "mlCorrection": 1},
            sort=[("createdBucket", DESCENDING)],
        )
        r_ml_prev = prev_shadow.get("mlCorrection") if prev_shadow else None

        # Features
        ohlcv = get_ohlcv("BTC-USD", years=1)
        features = compute_features_single(ohlcv, today)
        if not features:
            return {"ok": False, "error": "Could not compute features"}

        # Run overlay with gates
        result = compute_overlay(
            horizon_key=horizon,
            entry_price=entry_price,
            rule_target_price=rule_target,
            features_dict=features,
            conf_rule=conf_rule,
            r_ml_prev=r_ml_prev,
        )

        # Shadow log
        feat_hash = hashlib.sha256(str(sorted(features.items())).encode()).hexdigest()[:16]
        log_shadow(asset, horizon, today, entry_price, rule_target, result, feat_hash)

        return {
            "ok": True,
            "asset": asset,
            "horizon": horizon,
            "date": today,
            "entryPrice": round(entry_price, 2),
            "ruleTarget": round(rule_target, 2),
            "ruleReturn": result["ruleReturn"],
            "mlCorrection": result["mlCorrection"],
            "mlCorrectionRaw": result["mlCorrectionRaw"],
            "mlCorrectionBeforeDrift": result.get("mlCorrectionBeforeDrift"),
            "finalTarget": result["finalTargetPrice"],
            "finalReturn": result["finalReturn"],
            "mode": result["mode"],
            "stage": result.get("stage"),
            "mlAlpha": result.get("mlAlpha"),
            "effectiveAlpha": result.get("effectiveAlpha"),
            "modelId": result["modelId"],
            "capped": result["capped"],
            "weight": result["weight"],
            "driftWeight": result.get("driftWeight"),
            "drift": result.get("drift"),
            "gates": result["gates"],
            "directionPreserved": result["directionPreserved"],
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )


@router.post("/eval-shadow")
async def eval_shadow():
    """Evaluate matured shadow predictions."""
    from ml_overlay.eval_shadow import evaluate_shadow_forecasts
    result = evaluate_shadow_forecasts()
    return {"ok": True, **result}


@router.get("/shadow-verdict")
async def shadow_verdict(
    horizon: str = Query("7D"),
    window: int = Query(30),
    asset: str = Query("BTC"),
):
    """Get rolling shadow verdict with GO/NO-GO criteria."""
    from ml_overlay.eval_shadow import compute_rolling_verdict
    verdict = compute_rolling_verdict(horizon, window, asset)
    return {"ok": True, **verdict}


@router.get("/graduation")
async def graduation_status(
    horizon: str = Query("7D"),
    asset: str = Query("BTC"),
):
    """Get current graduation stage and effective alpha."""
    from ml_overlay.graduation import get_effective_alpha, get_audit_history
    alpha = get_effective_alpha(horizon, asset)
    history = get_audit_history(horizon, asset, limit=10)
    return {"ok": True, **alpha, "auditHistory": history}


@router.post("/graduation/evaluate")
async def graduation_evaluate(
    horizon: str = Query("7D"),
    asset: str = Query("BTC"),
):
    """Manually trigger graduation evaluation."""
    from ml_overlay.graduation import evaluate_graduation
    result = evaluate_graduation(horizon, asset)
    return {"ok": True, **result}



@router.get("/importance")
async def feature_importance(horizon: str = Query("7D")):
    """Compute permutation importance."""
    try:
        from ml_overlay.data.price_provider import get_ohlcv
        from ml_overlay.data.dataset_builder import build_dataset
        from ml_overlay.importance import compute_stable_importance

        ohlcv = get_ohlcv("BTC-USD", years=7)
        dataset = build_dataset(ohlcv, horizon)
        result = compute_stable_importance(dataset, horizon)
        return {"ok": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )



@router.get("/pruning-report")
async def pruning_report():
    """Get the latest pruning analysis report."""
    import json
    import os
    report_path = os.path.join(os.path.dirname(__file__), "artifacts", "importance_report.json")
    features_path = os.path.join(os.path.dirname(__file__), "artifacts", "selected_features.json")
    summary_path = os.path.join(os.path.dirname(__file__), "artifacts", "pruning_summary.md")

    result = {"ok": True}

    if os.path.exists(report_path):
        with open(report_path) as f:
            result["report"] = json.load(f)

    if os.path.exists(features_path):
        with open(features_path) as f:
            result["selectedFeatures"] = json.load(f)

    if os.path.exists(summary_path):
        with open(summary_path) as f:
            result["summary"] = f.read()

    if "report" not in result:
        return JSONResponse(status_code=404, content={"ok": False, "error": "No pruning report found. Run pruning pipeline first."})

    return result


@router.post("/apply-pruning")
async def apply_pruning(horizon: str = Query("7D")):
    """
    Retrain the overlay model with pruned feature set and register as new model.
    Reads selected_features.json and trains with reduced feature set.
    """
    import json
    import os
    import numpy as np
    features_path = os.path.join(os.path.dirname(__file__), "artifacts", "selected_features.json")

    if not os.path.exists(features_path):
        return JSONResponse(status_code=404, content={"ok": False, "error": "No selected_features.json found"})

    with open(features_path) as f:
        sf = json.load(f)

    horizon_feats = sf.get("horizons", {}).get(horizon, {})
    selected = horizon_feats.get("selected", [])
    if not selected:
        return JSONResponse(status_code=400, content={"ok": False, "error": f"No selected features for {horizon}"})

    try:
        from ml_overlay.data.price_provider import get_ohlcv
        from ml_overlay.data.dataset_builder import build_dataset
        from ml_overlay.config import LGBM_PARAMS, HORIZONS
        from ml_overlay.model.registry import register_model
        import lightgbm as lgb
        import joblib
        import hashlib
        from datetime import datetime, timezone

        ohlcv = get_ohlcv("BTC-USD", years=7)
        dataset = build_dataset(ohlcv, horizon)

        # Train on all available data
        X_train = dataset[selected].values
        y_train = dataset["y"].values

        model = lgb.LGBMRegressor(**LGBM_PARAMS)
        model.fit(X_train, y_train)

        # Save artifact
        model_id = hashlib.md5(f"pruned_{horizon}_{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:16]
        artifact_name = f"overlay_{horizon}_pruned_{model_id}.joblib"
        artifact_path = os.path.join(os.path.dirname(__file__), "artifacts", artifact_name)
        joblib.dump(model, artifact_path)

        # Feature importance
        importance = dict(zip(selected, model.feature_importances_.tolist()))

        # Register
        meta = {
            "modelId": model_id,
            "modelName": f"overlay_{horizon}_pruned",
            "horizon": horizon,
            "trainEnd": dataset.index[-1].strftime("%Y-%m-%d"),
            "trainRows": len(dataset),
            "trainedAt": datetime.now(timezone.utc).isoformat(),
            "artifactPath": artifact_path,
            "featureImportance": importance,
            "features": selected,
            "pruned": True,
            "prunedFrom": len(sf.get("horizons", {}).get(horizon, {}).get("pruned", [])),
            "status": "ACTIVE",
        }

        register_model(meta)

        return {
            "ok": True,
            "horizon": horizon,
            "modelId": model_id,
            "features": selected,
            "featureCount": len(selected),
            "trainRows": len(dataset),
            "artifactPath": artifact_path,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )


# ══════════════════════════════════════════════════════════════════
# BLOCK 5.A — Data Readiness & Proto Overlay
# ══════════════════════════════════════════════════════════════════

@router.get("/readiness")
async def ml_readiness(
    horizon: int = Query(7, description="Forecast horizon in days"),
    asset: str = Query("BTC"),
):
    """
    Block 5.A.2 — ML Dataset Readiness Dashboard.
    Returns metrics + pass/fail vs thresholds + overall verdict.
    """
    try:
        from ml_overlay.readiness.readiness_engine import compute_readiness
        result = compute_readiness(horizon_days=horizon, asset=asset)
        return result
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )


@router.get("/dataset-status")
async def ml_dataset_status(
    asset: str = Query("BTC"),
):
    """
    Block 5.A.1 — ML Dataset Accumulation Status.
    Tracks how many v4.2.1+ forecasts with full audit exist,
    quality metrics, and readiness for ML training.
    """
    try:
        from ml_overlay.dataset_status import compute_dataset_status
        result = compute_dataset_status(asset=asset)
        return {"ok": True, "data": result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )


@router.get("/proto-overlay")
async def proto_overlay_check(
    asset: str = Query("BTC"),
):
    """
    Block 5.A.6 — Rule-based proto overlay risk assessment.
    Uses known weak zones (unstable_transition, high entropy, etc.)
    to compute risk score and execution multipliers.
    """
    try:
        import os
        from pymongo import MongoClient, DESCENDING
        from ml_overlay.proto_overlay import compute_proto_overlay_risk

        db = MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]
        symbol = f"{asset}USDT"

        # Get latest forecast audit for context
        forecast = db["exchange_forecasts"].find_one(
            {"asset": asset, "horizon": "7D"},
            {"_id": 0, "audit": 1, "scenarios": 1, "confidence": 1},
            sort=[("createdAt", DESCENDING)],
        )

        audit = (forecast or {}).get("audit") or {}
        regime_adj = audit.get("regimeAdjustments") or {}
        regime_v2 = audit.get("regimeV2") or {}
        scenarios = (forecast or {}).get("scenarios") or {}

        # Get latest tactical
        obs = db["exchange_observations"].find_one(
            {"symbol": symbol},
            {"_id": 0, "orderFlow": 1, "liquidations": 1},
            sort=[("timestamp", DESCENDING)],
        )

        tactical_bias = "neutral"
        if obs:
            from tactical.tactical_signal_builder import build_tactical_signals
            from tactical.tactical_fusion_engine import fuse_tactical_signals

            of = obs.get("orderFlow") or {}
            liq = obs.get("liquidations") or {}
            fund = db["exchange_funding_context"].find_one(
                {"symbol": symbol}, {"_id": 0}, sort=[("ts", DESCENDING)]
            ) or {}

            snap = {
                "imbalance": of.get("imbalance", 0.0),
                "dominance": of.get("dominance", 0.5),
                "aggressor_bias": of.get("aggressorBias", "NEUTRAL"),
                "long_liq_volume": liq.get("longVolume", 0) or 0,
                "short_liq_volume": liq.get("shortVolume", 0) or 0,
                "cascade_active": liq.get("cascadeActive", False),
                "cascade_direction": liq.get("cascadeDirection", ""),
                "cascade_phase": liq.get("cascadePhase") or "",
                "funding_score": fund.get("fundingScore", 0.0),
                "funding_trend": fund.get("fundingTrend", 0.0),
                "funding_label": fund.get("label", "NEUTRAL"),
                "absorption": of.get("absorption", False),
                "absorption_side": of.get("absorptionSide", ""),
            }
            signals = build_tactical_signals(snap)
            fusion = fuse_tactical_signals(signals)
            tactical_bias = fusion["bias"]

        ctx = {
            "entropy": regime_v2.get("regime_entropy", 0.5),
            "uncertainty": regime_adj.get("uncertainty", 0.5),
            "scenario_spread": scenarios.get("spread", 0.0),
            "tactical_bias": tactical_bias,
            "regime_flags": regime_adj.get("flags") or [],
        }

        result = compute_proto_overlay_risk(ctx)
        result["context"] = ctx
        return {"ok": True, **result}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )



# ══════════════════════════════════════════════════════════════════
# BLOCK 12.1 — Catastrophic Risk Classifier
# ══════════════════════════════════════════════════════════════════

@router.get("/catastrophic-risk")
async def catastrophic_risk(
    asset: str = Query("BTC"),
    horizon: str = Query("7D"),
):
    """
    Block 12.1: Predict catastrophic risk for latest forecast.

    Returns probability of forecast being catastrophically wrong
    (wrong direction + significant adverse move).
    """
    try:
        from ml_overlay.catastrophic_risk import predict_from_asset
        result = predict_from_asset(asset, horizon)
        return {"ok": True, **result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )


@router.get("/catastrophic-risk/dataset")
async def catastrophic_risk_dataset(
    horizon: str = Query(None),
):
    """Block 12.1: View dataset statistics for catastrophic risk model."""
    try:
        from ml_overlay.catastrophic_risk import build_dataset
        dataset = build_dataset(horizon=horizon)
        pos = sum(1 for r in dataset if r["label"] == 1)
        neg = len(dataset) - pos

        # Per-horizon breakdown
        per_horizon = {}
        for row in dataset:
            h = row["horizon"]
            if h not in per_horizon:
                per_horizon[h] = {"total": 0, "catastrophic": 0}
            per_horizon[h]["total"] += 1
            if row["label"] == 1:
                per_horizon[h]["catastrophic"] += 1

        for h, stats in per_horizon.items():
            stats["rate"] = round(stats["catastrophic"] / stats["total"], 4) if stats["total"] > 0 else 0

        return {
            "ok": True,
            "total": len(dataset),
            "catastrophic": pos,
            "normal": neg,
            "rate": round(pos / len(dataset), 4) if len(dataset) > 0 else 0,
            "perHorizon": per_horizon,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )


@router.post("/catastrophic-risk/train")
async def catastrophic_risk_train(
    horizon: str = Query(None),
):
    """Block 12.1: Train and evaluate catastrophic risk model."""
    try:
        from ml_overlay.catastrophic_risk import train_model
        result = train_model(horizon=horizon)
        # Remove the model object from response
        result_out = {k: v for k, v in result.items() if k != "model"}
        return {"ok": True, **result_out}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "trace": traceback.format_exc()},
        )
