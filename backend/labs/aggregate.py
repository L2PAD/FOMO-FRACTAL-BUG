"""
Labs universe aggregator — cross-asset analytics.
Provides stateDistribution, topEdges, labHeat for Research/Market consumers.
"""

from typing import List, Dict
from collections import Counter, defaultdict
from .scoring import clamp


def aggregate_universe(rows: List[dict]) -> dict:
    """
    rows[] item: {symbol, labs[], overallState{}}
    Returns universe-level analytics + totalRiskIndex.
    """
    state_counts = Counter()
    lab_sum = defaultdict(float)
    lab_cnt = defaultdict(int)
    scored = []

    # For total risk aggregation
    risk_sums = defaultdict(float)
    risk_cnt = 0

    for r in rows:
        st = r.get("overallState", {}).get("stateKey", "UNKNOWN")
        state_counts[st] += 1

        conf = r.get("overallState", {}).get("confidence", 0)
        intensity = max([x.get("abnormality", 0) * x.get("confidence", 0) for x in r.get("labs", [])] or [0])
        edge = clamp(conf * 0.6 + intensity * 0.4)
        scored.append((edge, r["symbol"], st, conf))

        labs_map = {x["lab"]: x for x in r.get("labs", [])}
        for x in r.get("labs", []):
            lab_sum[x["lab"]] += x.get("abnormality", 0)
            lab_cnt[x["lab"]] += 1

        # Accumulate risk per symbol
        risk_sums["liquidity"] += labs_map.get("liquidity", {}).get("riskContribution", 0)
        risk_sums["stress"] += labs_map.get("market_stress", {}).get("riskContribution", 0)
        risk_sums["manipulation"] += labs_map.get("manipulation", {}).get("riskContribution", 0)
        risk_sums["structure"] += labs_map.get("regime", {}).get("riskContribution", 0)
        risk_sums["conflict"] += labs_map.get("signal_conflict", {}).get("riskContribution", 0)
        risk_cnt += 1

    top = sorted(scored, key=lambda x: x[0], reverse=True)[:20]

    lab_heat = sorted(
        [{"lab": lab, "avgAbnormality": round(s / max(1, lab_cnt[lab]), 4)} for lab, s in lab_sum.items()],
        key=lambda x: x["avgAbnormality"], reverse=True
    )

    total = len(rows)
    distribution = {}
    for k, v in state_counts.items():
        distribution[k] = {"count": v, "pct": round(v / max(1, total) * 100, 1)}

    # Total Risk Index (weighted average across universe)
    n = max(1, risk_cnt)
    total_risk = (
        0.25 * (risk_sums["liquidity"] / n) +
        0.20 * (risk_sums["stress"] / n) +
        0.20 * (risk_sums["manipulation"] / n) +
        0.20 * (risk_sums["structure"] / n) +
        0.15 * (risk_sums["conflict"] / n)
    )

    return {
        "stateDistribution": distribution,
        "topEdges": [{"edge": round(e, 3), "symbol": sym, "state": st, "confidence": round(c, 3)} for e, sym, st, c in top],
        "labHeat": lab_heat,
        "universeSize": total,
        "totalRiskIndex": round(total_risk * 100),
    }


def compute_total_risk(labs: list) -> dict:
    """Compute total risk index for a single asset's labs."""
    labs_map = {x["lab"]: x for x in labs}
    liq = labs_map.get("liquidity", {}).get("riskContribution", 0)
    stress = labs_map.get("market_stress", {}).get("riskContribution", 0)
    manip = labs_map.get("manipulation", {}).get("riskContribution", 0)
    struct = labs_map.get("regime", {}).get("riskContribution", 0)
    conflict = labs_map.get("signal_conflict", {}).get("riskContribution", 0)

    total = 0.25 * liq + 0.20 * stress + 0.20 * manip + 0.20 * struct + 0.15 * conflict
    idx = round(total * 100)
    level = "Low" if idx < 30 else "Elevated" if idx > 60 else "Moderate"

    return {
        "totalRiskIndex": idx,
        "level": level,
        "breakdown": {
            "liquidity": round(liq * 100),
            "stress": round(stress * 100),
            "manipulation": round(manip * 100),
            "structure": round(struct * 100),
            "conflict": round(conflict * 100),
        },
    }
