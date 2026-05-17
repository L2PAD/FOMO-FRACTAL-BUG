"""
Labs scoring — abnormality, confidence, risk, conviction per lab.
Strict pipeline: normalize → abnormality → aggregate → state → confidence → impact.
"""

from typing import Dict
from .config import SOURCE_CONFIDENCE, FRESHNESS_THRESHOLDS, MAX_CONVICTION_IMPACT


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def abnormality_from_norm(norm: float, unipolar: bool = False) -> float:
    """
    How abnormal is this indicator.
    unipolar: 0=normal, 1=extreme → abnormality = norm
    bipolar: 0.5=normal, extremes are abnormal → abnormality = |norm - 0.5| * 2
    """
    if unipolar:
        return clamp(norm)
    return clamp(abs(norm - 0.5) * 2)


def freshness_confidence(freshness_sec: int) -> float:
    if freshness_sec <= FRESHNESS_THRESHOLDS["fresh"]:
        return 1.0
    if freshness_sec <= FRESHNESS_THRESHOLDS["warm"]:
        return 0.7
    if freshness_sec <= FRESHNESS_THRESHOLDS["stale"]:
        return 0.4
    return 0.2


def coverage_confidence(present: int, expected: int) -> float:
    if expected == 0:
        return 0.0
    ratio = present / expected
    return clamp((ratio - 0.5) / 0.5)


def compute_confidence(present: int, expected: int, freshness_sec: int, source_type: str, abnormality: float = 0.0) -> float:
    covC = coverage_confidence(present, expected)
    freshC = freshness_confidence(freshness_sec)
    sourceC = SOURCE_CONFIDENCE.get(source_type, 0.75)
    base = clamp(covC * freshC * sourceC)
    # Scale by abnormality: high abnormality → lower confidence (uncertainty)
    return max(0.55, min(0.98, 0.55 + base * (1 - abnormality) * 0.45))


def compute_lab_score(lab_key: str, lab_config: dict, feature_map: Dict[str, dict]):
    """
    Compute per-lab metrics: abnormality, risk, conviction, present/expected.
    """
    indicators = lab_config["indicators"]
    lab_abn = 0.0
    risk = 0.0
    conviction = 0.0
    present = 0
    expected = len(indicators)
    metrics = []

    for key, cfg in indicators.items():
        if key not in feature_map:
            continue
        present += 1
        data = feature_map[key]
        norm = data["norm"]
        is_unipolar = data.get("unipolar", False)
        abn = abnormality_from_norm(norm, unipolar=is_unipolar)

        # For inverse indicators (higher norm = GOOD), flip for risk/conviction
        risk_norm = (1.0 - norm) if cfg.get("inverse") else norm
        conv_norm = (1.0 - norm) if cfg.get("inverse") else norm

        lab_abn += cfg["weight"] * abn
        risk += cfg["riskW"] * risk_norm
        conviction += cfg["convW"] * conv_norm

        metrics.append({
            "key": key,
            "raw": data.get("raw"),
            "norm": round(norm, 4),
            "abnormality": round(abn, 4),
            "source": data.get("source", "obs"),
        })

    lab_abn = clamp(lab_abn)
    risk = clamp(risk)
    conviction = max(-1.0, min(1.0, conviction))
    conviction = clamp(conviction * MAX_CONVICTION_IMPACT, -MAX_CONVICTION_IMPACT, MAX_CONVICTION_IMPACT)

    return {
        "abnormality": round(lab_abn, 4),
        "riskContribution": round(risk, 4),
        "convictionContribution": round(conviction, 4),
        "present": present,
        "expected": expected,
        "metrics": metrics,
    }


def classify_state(lab_key: str, lab_config: dict, feature_map: Dict[str, dict], abnormality: float) -> str:
    """Determine lab state from rules in config."""
    rules = lab_config.get("stateRules", [])
    for rule in rules:
        cond = rule["condition"]
        # Parse simple condition: "key > threshold" or "_abnormality > threshold"
        parts = cond.split()
        if len(parts) == 3:
            var, op, threshold = parts[0], parts[1], float(parts[2])
            if var == "_abnormality":
                val = abnormality
            elif var in feature_map:
                val = feature_map[var]["norm"]
            else:
                continue
            if op == ">" and val > threshold:
                return rule["state"]
            elif op == "<" and val < threshold:
                return rule["state"]
    return lab_config.get("defaultState", "NEUTRAL")
