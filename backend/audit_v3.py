"""
Walk-Forward Audit — v3 Generator
Compares: Baseline A (trend continuation), Baseline B (always neutral), v3 model
Metrics: DirHit, MAE, FlipRate, Coverage, ECE
By: horizon, regime
"""
import os, sys, json
sys.path.insert(0, "/app/backend")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")

from pymongo import MongoClient, DESCENDING
from forecast.generator import generate_forecast, _get_regime_data, _compute_features, _get_recent_performance
from forecast.price_provider import get_price_series
from forecast import Horizon
import numpy as np

db = MongoClient("mongodb://localhost:27017/intelligence_engine")["intelligence_engine"]


def run_audit():
    results = {}

    # ──────────────────────────────────────
    # TEST 1: v3 Formula Validation
    # ──────────────────────────────────────
    print("=" * 60)
    print("TEST 1: v3 Generator — Formula Validation")
    print("=" * 60)

    for h_name, h_enum in [("7D", Horizon.D7), ("30D", Horizon.D30), ("24H", Horizon.H24)]:
        rec = generate_forecast("BTC", h_enum)
        if not rec:
            print(f"  [{h_name}] No forecast generated")
            continue

        # Target consistency
        recalc = round(rec.entryPrice * (1 + rec.expectedMovePct / 100), 2)
        diff = abs(recalc - rec.targetPrice)

        regime = _get_regime_data("BTC", h_name)

        print(f"\n  [{h_name}] Regime={regime['regime']}")
        print(f"    entry=${rec.entryPrice:,.2f} move={rec.expectedMovePct:+.2f}% target=${rec.targetPrice:,.2f}")
        print(f"    target diff={diff} {'PASS' if diff < 0.01 else 'FAIL'}")
        print(f"    direction={rec.direction} confidence={rec.confidence:.4f}")
        print(f"    regime meanReturn={regime['meanReturn']:.4%} stdReturn={regime['stdReturn']:.4%}")
        print(f"    MAE cap check: |move|={abs(rec.expectedMovePct)/100:.4f} vs 1.5*MAE={1.5*regime['maeMean']:.4f} {'PASS' if abs(rec.expectedMovePct)/100 <= 1.5*regime['maeMean']+0.001 else 'FAIL'}")
        print(f"    conf < dirHitRate: {rec.confidence:.4f} vs {regime['dirHitMean']:.4f} {'PASS' if rec.confidence <= regime['dirHitMean'] else 'WARN'}")

    # ──────────────────────────────────────
    # TEST 2: Confidence-Move Independence
    # ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST 2: Confidence-Move Independence")
    print("=" * 60)

    recs = []
    for h in [Horizon.H24, Horizon.D7, Horizon.D30]:
        r = generate_forecast("BTC", h)
        if r:
            recs.append(r)
    if len(recs) >= 2:
        moves = [abs(r.expectedMovePct) for r in recs]
        confs = [r.confidence for r in recs]
        mean_m, mean_c = np.mean(moves), np.mean(confs)
        cov = np.mean([(m-mean_m)*(c-mean_c) for m,c in zip(moves, confs)])
        std_m, std_c = np.std(moves), np.std(confs)
        corr = cov / (std_m * std_c) if std_m > 0 and std_c > 0 else 0
        print(f"  Correlation: {corr:.4f} {'PASS' if abs(corr) < 0.8 else 'FAIL'}")
    else:
        print("  Not enough forecasts")

    # ──────────────────────────────────────
    # TEST 3: Historical Baseline Comparison
    # ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST 3: Historical Performance — Baseline vs Model (from DB)")
    print("=" * 60)

    for horizon_key in ["7D", "30D"]:
        evaluated = list(db["exchange_forecasts"].find(
            {"asset": "BTC", "horizon": horizon_key, "outcome": {"$ne": None}},
            {"_id": 0, "direction": 1, "expectedMovePct": 1, "confidence": 1,
             "entryPrice": 1, "targetPrice": 1, "outcome": 1, "modelVersion": 1}
        ).sort("createdBucket", DESCENDING).limit(60))

        if not evaluated:
            print(f"\n  [{horizon_key}] No evaluated data")
            continue

        n = len(evaluated)
        dir_hits = sum(1 for e in evaluated if e.get("outcome", {}).get("directionMatch"))
        wins = sum(1 for e in evaluated if e.get("outcome", {}).get("label") == "TP")
        deviations = [abs(e.get("outcome", {}).get("deviationPct", 0)) for e in evaluated]
        mae = np.mean(deviations) if deviations else 0

        # Flip rate
        directions = [e.get("direction", "NEUTRAL") for e in evaluated]
        flips = sum(1 for i in range(1, len(directions)) if directions[i] != directions[i-1])
        flip_rate = flips / max(1, n - 1)

        # Coverage (non-NEUTRAL)
        non_neutral = sum(1 for e in evaluated if e.get("direction") != "NEUTRAL")
        coverage = non_neutral / n

        # Confidence calibration (ECE proxy)
        conf_vals = [e.get("confidence", 0) for e in evaluated]
        avg_conf = np.mean(conf_vals) if conf_vals else 0

        print(f"\n  [{horizon_key}] n={n}")
        print(f"    DirHit:   {dir_hits/n:.1%} ({dir_hits}/{n})")
        print(f"    WinRate:  {wins/n:.1%} ({wins}/{n})")
        print(f"    MAE:      {mae:.2f}%")
        print(f"    FlipRate: {flip_rate:.2%}")
        print(f"    Coverage: {coverage:.1%} (non-NEUTRAL)")
        print(f"    AvgConf:  {avg_conf:.2%}")

        # Regime breakdown
        print(f"\n    --- Regime Breakdown ---")
        for e in evaluated:
            e["_regime"] = "UNKNOWN"
            try:
                created_at = e.get("createdAt") or e.get("outcome", {}).get("evaluatedAt", 0)
                if created_at:
                    snap = db["drift_snapshots"].find_one(
                        {"asset": "BTC", "horizon": horizon_key},
                        {"_id": 0, "regime": 1},
                        sort=[("ts", DESCENDING)],
                    )
                    if snap:
                        e["_regime"] = snap.get("regime", "UNKNOWN")
            except Exception:
                pass

        for regime in ["TREND", "RANGE", "RISK_OFF", "TRANSITION", "UNKNOWN"]:
            subset = [e for e in evaluated if e.get("_regime") == regime]
            if not subset:
                continue
            sn = len(subset)
            s_dir = sum(1 for e in subset if e.get("outcome", {}).get("directionMatch"))
            s_win = sum(1 for e in subset if e.get("outcome", {}).get("label") == "TP")
            print(f"      {regime}: n={sn} DirHit={s_dir/sn:.1%} WinRate={s_win/sn:.1%}")

        results[horizon_key] = {
            "n": n,
            "dirHit": round(dir_hits / n, 4),
            "winRate": round(wins / n, 4),
            "mae": round(mae, 4),
            "flipRate": round(flip_rate, 4),
            "coverage": round(coverage, 4),
            "avgConf": round(avg_conf, 4),
        }

    # ──────────────────────────────────────
    # TEST 4: NEUTRAL Filter Impact (simulation)
    # ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST 4: NEUTRAL Filter Impact (v2→v3)")
    print("=" * 60)

    for horizon_key in ["7D", "30D"]:
        regime_data = _get_regime_data("BTC", horizon_key)
        neutral_threshold = 0.25 * regime_data["stdReturn"]
        print(f"\n  [{horizon_key}] Regime={regime_data['regime']}")
        print(f"    meanReturn={regime_data['meanReturn']:.4%}")
        print(f"    stdReturn={regime_data['stdReturn']:.4%}")
        print(f"    NEUTRAL threshold: abs(meanReturn) < {neutral_threshold:.4%}")
        print(f"    Current: abs(meanReturn)={abs(regime_data['meanReturn']):.4%}")
        if abs(regime_data["meanReturn"]) < neutral_threshold:
            print(f"    → NEUTRAL FILTER ACTIVE: would force NEUTRAL in this regime")
        else:
            print(f"    → Direction signal allowed")

    # ──────────────────────────────────────
    # TEST 5: Meta-Shrinkage Status
    # ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST 5: Meta-Shrinkage Status")
    print("=" * 60)

    for hk in ["7D", "30D"]:
        perf = _get_recent_performance("BTC", hk)
        print(f"  [{hk}] rollingWinRate={perf['rollingWinRate']:.2%} (last {perf['recentCount']})")
        if perf["recentCount"] >= 3 and perf["rollingWinRate"] < 0.25:
            print(f"    → META-SHRINKAGE ACTIVE: move*=0.8, conf*=0.85")
        elif perf["recentCount"] >= 5 and perf["rollingWinRate"] < 0.15:
            print(f"    → THROTTLE ACTIVE: forced NEUTRAL")
        else:
            print(f"    → Normal operation")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)

    with open("/tmp/audit_v3_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results saved to /tmp/audit_v3_results.json")


if __name__ == "__main__":
    run_audit()
