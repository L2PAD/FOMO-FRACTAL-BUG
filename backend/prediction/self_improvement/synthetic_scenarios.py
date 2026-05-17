"""
Synthetic Scenario Engine — controlled simulation for Self-Improvement testing.

Generates realistic forecast_results that simulate real system errors:
  1. OVERCONFIDENCE: high confidence, low actual hit rate (~55%)
  2. UNDERCONFIDENCE: low confidence, high actual hit rate (~65%)
  3. LATE_SIGNAL: correct direction, low opportunity capture
  4. LIQUIDITY_TRAP: high edge, weak realized edge
  5. STRONG_STRUCTURE: structure edge present, high accuracy

Each scenario generates 35+ records (above MIN_SAMPLE=30).
Records are inserted into forecast_results with synthetic=True flag.
"""
import logging
import random
import uuid
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("self_improvement.synthetic")

SCENARIO_CONFIGS = {
    "overconfidence": {
        "count": 40,
        "description": "High confidence predictions with low actual hit rate (~55%)",
        "family_keys": ["crypto_price_gt_7d", "crypto_price_lt_7d"],
    },
    "underconfidence": {
        "count": 35,
        "description": "Low confidence predictions with high actual hit rate (~65%)",
        "family_keys": ["crypto_event_gt_7d", "crypto_event_lt_7d"],
    },
    "late_signal": {
        "count": 35,
        "description": "Correct direction but poor timing / low opportunity capture",
        "family_keys": ["crypto_price_gt_7d", "crypto_price_lt_7d"],
    },
    "liquidity_trap": {
        "count": 35,
        "description": "High edge on paper but weak realized edge due to liquidity",
        "family_keys": ["crypto_event_lt_24h", "crypto_event_lt_6h"],
    },
    "strong_structure": {
        "count": 40,
        "description": "Structure edge present and highly accurate",
        "family_keys": ["crypto_price_gt_7d"],
    },
}


def generate_scenarios(db, scenarios: list[str] = None) -> dict:
    """Generate synthetic forecast_results for specified scenarios."""
    if scenarios is None:
        scenarios = list(SCENARIO_CONFIGS.keys())

    now = datetime.now(timezone.utc)
    all_records = []
    stats = {}

    for scenario_name in scenarios:
        config = SCENARIO_CONFIGS.get(scenario_name)
        if not config:
            stats[scenario_name] = {"error": f"Unknown scenario: {scenario_name}"}
            continue

        records = _generate_scenario(scenario_name, config, now)
        all_records.extend(records)
        stats[scenario_name] = {"generated": len(records), "description": config["description"]}

    if all_records:
        # Clear previous synthetic data
        deleted = db.forecast_results.delete_many({"synthetic": True})
        logger.info(f"[Synthetic] Cleared {deleted.deleted_count} previous synthetic records")

        db.forecast_results.insert_many([dict(r) for r in all_records])
        logger.info(f"[Synthetic] Inserted {len(all_records)} synthetic forecast_results")

    return {
        "total_generated": len(all_records),
        "scenarios": stats,
        "cleared_previous": True,
    }


def clear_synthetic(db) -> dict:
    """Remove all synthetic forecast_results."""
    result = db.forecast_results.delete_many({"synthetic": True})
    return {"deleted": result.deleted_count}


def _generate_scenario(name: str, config: dict, now: datetime) -> list[dict]:
    """Generate records for a specific scenario."""
    count = config["count"]
    family_keys = config["family_keys"]

    if name == "overconfidence":
        return _gen_overconfidence(count, family_keys, now)
    elif name == "underconfidence":
        return _gen_underconfidence(count, family_keys, now)
    elif name == "late_signal":
        return _gen_late_signal(count, family_keys, now)
    elif name == "liquidity_trap":
        return _gen_liquidity_trap(count, family_keys, now)
    elif name == "strong_structure":
        return _gen_strong_structure(count, family_keys, now)
    return []


def _base_record(family_key: str, now: datetime, days_ago: int) -> dict:
    """Create a base forecast_result record."""
    resolved_at = (now - timedelta(days=days_ago, hours=random.randint(0, 23))).isoformat()
    created_at = (now - timedelta(days=days_ago + random.randint(1, 5))).isoformat()
    return {
        "forecast_id": f"syn_{uuid.uuid4().hex[:10]}",
        "event_id": f"evt_{uuid.uuid4().hex[:8]}",
        "market_id": f"mkt_{uuid.uuid4().hex[:8]}",
        "family_key": family_key,
        "created_at": created_at,
        "resolved_at": resolved_at,
        "synthetic": True,
    }


def _gen_overconfidence(count: int, families: list, now: datetime) -> list[dict]:
    """Generate overconfidence scenario: high conf but only ~55% accuracy."""
    records = []
    for i in range(count):
        r = _base_record(random.choice(families), now, days_ago=random.randint(1, 25))
        correct = random.random() < 0.55  # only 55% hit rate
        r.update({
            "confidence": "high",
            "confidence_score": round(random.uniform(0.70, 0.85), 3),
            "action": random.choice(["BUY_YES", "BUY_NO"]),
            "binary_correct": correct,
            "correctness": "CORRECT" if correct else "WRONG",
            "edge": round(random.uniform(0.05, 0.15), 4),
            "realized_edge": round(random.uniform(-0.03, 0.08), 4) if correct else round(random.uniform(-0.10, -0.01), 4),
            "brier_score": round(random.uniform(0.15, 0.35), 4),
            "structure_edge_used": random.random() > 0.5,
        })
        records.append(r)
    return records


def _gen_underconfidence(count: int, families: list, now: datetime) -> list[dict]:
    """Generate underconfidence: low conf but ~65% accuracy."""
    records = []
    for i in range(count):
        r = _base_record(random.choice(families), now, days_ago=random.randint(1, 25))
        correct = random.random() < 0.65
        r.update({
            "confidence": "low",
            "confidence_score": round(random.uniform(0.30, 0.45), 3),
            "action": random.choice(["BUY_YES", "BUY_NO", "WATCH"]),
            "binary_correct": correct,
            "correctness": "CORRECT" if correct else "WRONG",
            "edge": round(random.uniform(0.02, 0.08), 4),
            "realized_edge": round(random.uniform(0.01, 0.06), 4) if correct else round(random.uniform(-0.05, 0.01), 4),
            "brier_score": round(random.uniform(0.20, 0.40), 4),
            "structure_edge_used": False,
        })
        records.append(r)
    return records


def _gen_late_signal(count: int, families: list, now: datetime) -> list[dict]:
    """Generate late signal: correct direction but poor timing."""
    records = []
    for i in range(count):
        r = _base_record(random.choice(families), now, days_ago=random.randint(1, 25))
        correct = random.random() < 0.70  # good direction
        opp_captured = random.random() < 0.30 if correct else False  # but poor capture
        r.update({
            "confidence": "medium",
            "confidence_score": round(random.uniform(0.50, 0.65), 3),
            "action": random.choice(["BUY_YES", "BUY_NO"]),
            "binary_correct": correct,
            "correctness": "CORRECT" if correct else "WRONG",
            "edge": round(random.uniform(0.04, 0.12), 4),
            "realized_edge": round(random.uniform(-0.02, 0.04), 4),
            "brier_score": round(random.uniform(0.18, 0.32), 4),
            "opportunity_captured": opp_captured,
            "entry_quality": round(random.uniform(0.02, 0.08), 4),
            "structure_edge_used": True,
        })
        records.append(r)
    return records


def _gen_liquidity_trap(count: int, families: list, now: datetime) -> list[dict]:
    """Generate liquidity trap: high edge, weak realized edge (short expiry noise)."""
    records = []
    for i in range(count):
        r = _base_record(random.choice(families), now, days_ago=random.randint(1, 25))
        correct = random.random() < 0.45  # poor accuracy on short expiry
        r.update({
            "confidence": "medium",
            "confidence_score": round(random.uniform(0.50, 0.65), 3),
            "action": random.choice(["BUY_YES", "BUY_NO"]),
            "binary_correct": correct,
            "correctness": "CORRECT" if correct else "WRONG",
            "edge": round(random.uniform(0.08, 0.20), 4),  # high paper edge
            "realized_edge": round(random.uniform(-0.08, 0.02), 4),  # weak real edge
            "brier_score": round(random.uniform(0.25, 0.45), 4),
            "structure_edge_used": True,
        })
        records.append(r)
    return records


def _gen_strong_structure(count: int, families: list, now: datetime) -> list[dict]:
    """Generate strong structure: structure edge present, high accuracy."""
    records = []
    for i in range(count):
        r = _base_record(random.choice(families), now, days_ago=random.randint(1, 25))
        correct = random.random() < 0.72  # high accuracy
        r.update({
            "confidence": "high",
            "confidence_score": round(random.uniform(0.65, 0.80), 3),
            "action": random.choice(["BUY_YES", "BUY_NO"]),
            "binary_correct": correct,
            "correctness": "CORRECT" if correct else "WRONG",
            "edge": round(random.uniform(0.06, 0.14), 4),
            "realized_edge": round(random.uniform(0.02, 0.10), 4) if correct else round(random.uniform(-0.04, 0.01), 4),
            "brier_score": round(random.uniform(0.12, 0.28), 4),
            "structure_edge_used": True,
        })
        records.append(r)
    return records
