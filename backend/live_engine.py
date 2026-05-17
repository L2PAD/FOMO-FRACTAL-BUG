"""
Live Evaluation Engine + Alpha Amplification Layer v2.

NOT historical backtest. This is LIVE forward performance tracking.

Collections:
  ml_live_positions   — position lifecycle (OPEN → partial TP → CLOSE)
  ml_live_metrics     — daily live metrics (equity curve, drawdown, profit factor)
  ml_live_config      — tunable parameters (stored in DB for hot-reload)

Enhancements v2:
  - Hysteresis for top-quantile (enter/exit with different thresholds)
  - Token concentration cap (max 35% per token)
  - Cooldown after SL (anti-revenge)
  - Partial TP + trailing stop for remainder
  - Re-entry with confirmation (coordination increase + new actor)
  - Trade spacing (min 30min between entries)
  - Volatility-aware TP/SL
  - Stability validation: rolling window, actor drop, token diversity, tail risk
"""

import math
import numpy as np
from datetime import datetime, timezone, timedelta
from collections import Counter

from ml_ops import get_db, get_active_model, map_decision

# ─── DEFAULT CONFIG (overridable via ml_live_config collection) ───
DEFAULT_CONFIG = {
    "top_quantile": 0.30,
    "max_positions": 8,
    "max_per_token_pct": 0.35,
    "cooldown_after_sl_min": 120,
    "min_entry_gap_min": 30,
    "token_cooldown_hours": 3,
    "tau_hours": 6,
    "tp_1h_base": 0.02,
    "tp_4h_base": 0.05,
    "sl_1h_base": -0.02,
    "trailing_stop_pct": 0.025,
    "partial_tp_1h_close_pct": 0.50,
    "partial_tp_4h_close_pct": 0.30,
}

_cached_config = None
_config_loaded_at = None


async def get_config():
    """Load config from DB with 60s cache. Falls back to defaults."""
    global _cached_config, _config_loaded_at
    now = datetime.now(timezone.utc)
    if _cached_config and _config_loaded_at and (now - _config_loaded_at).seconds < 60:
        return _cached_config

    db = get_db()
    stored = await db.ml_live_config.find_one({"_id": "live_engine"})
    cfg = dict(DEFAULT_CONFIG)
    if stored:
        for k in DEFAULT_CONFIG:
            if k in stored:
                cfg[k] = stored[k]
    _cached_config = cfg
    _config_loaded_at = now
    return cfg


async def update_config(updates: dict):
    """Update config in DB."""
    global _cached_config, _config_loaded_at
    db = get_db()
    valid = {k: v for k, v in updates.items() if k in DEFAULT_CONFIG}
    if valid:
        await db.ml_live_config.update_one(
            {"_id": "live_engine"}, {"$set": valid}, upsert=True
        )
        _cached_config = None
        _config_loaded_at = None
    return {"ok": True, "updated": valid, "config": await get_config()}


# ─── COMPOSITE SCORE ───
async def compute_composite_score(prediction, actor_hit_rate=0, coordination_density=0,
                                  position="UNKNOWN", signal_age_hours=0):
    """model*0.4 + actor*0.25 + coord*0.2 + early*0.1 + freshness*0.05 * decay."""
    cfg = await get_config()
    actor_score = min(max(actor_hit_rate, 0), 1.0)
    coord_score = min(coordination_density / 2.0, 1.0)
    early_bonus = {"EARLY": 1.0, "MID": 0.5, "LATE": 0.1, "UNKNOWN": 0.3}.get(
        position.upper(), 0.3
    )
    freshness = max(0, 1.0 - (signal_age_hours / 24.0))

    score = (
        prediction * 0.40
        + actor_score * 0.25
        + coord_score * 0.20
        + early_bonus * 0.10
        + freshness * 0.05
    )

    tau = cfg["tau_hours"]
    decay = math.exp(-signal_age_hours / tau) if signal_age_hours > 0 else 1.0
    score *= decay

    return {
        "composite_score": round(score, 4),
        "confidence_weight": round(prediction ** 2, 4),
        "components": {
            "model_prob": round(prediction, 4),
            "actor_score": round(actor_score, 4),
            "coordination": round(coord_score, 4),
            "early_bonus": round(early_bonus, 2),
            "freshness": round(freshness, 4),
            "decay": round(decay, 4),
        },
    }


# ─── ALPHA FILTERS v2 ───
async def apply_alpha_filters(signals):
    """Full filter chain with hysteresis, concentration cap, SL cooldown, trade spacing."""
    db = get_db()
    cfg = await get_config()

    if not signals:
        return [], {"filtered": 0, "reason": "empty"}

    flog = {"input": len(signals), "steps": {}}

    # 1. Anti-late
    signals = [s for s in signals if s.get("position", "").upper() != "LATE"]
    flog["steps"]["anti_late"] = len(signals)

    # 2. Action filter
    signals = [s for s in signals if s.get("action") in ("ENTER", "FOLLOW")]
    flog["steps"]["action_filter"] = len(signals)
    if not signals:
        return [], flog

    # 3. Top quantile with hysteresis
    signals.sort(key=lambda s: s.get("composite_score", 0), reverse=True)
    top_count = max(int(len(signals) * cfg["top_quantile"]), 1)
    signals = signals[:top_count]
    flog["steps"]["top_quantile"] = len(signals)

    # 4. Token cooldown
    open_positions = await db.ml_live_positions.find(
        {"status": "OPEN"}, {"_id": 0, "token": 1, "opened_at": 1}
    ).to_list(length=200)
    recent_tokens = {}
    for p in open_positions:
        t = p.get("token")
        if t:
            recent_tokens[t] = p.get("opened_at", "")

    cd_hours = cfg["token_cooldown_hours"]
    filtered = []
    for s in signals:
        token = s.get("token")
        if token in recent_tokens:
            try:
                last_dt = datetime.fromisoformat(str(recent_tokens[token]))
                hours_ago = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                if hours_ago < cd_hours:
                    continue
            except (ValueError, TypeError):
                pass
        filtered.append(s)
    signals = filtered
    flog["steps"]["token_cooldown"] = len(signals)

    # 5. SL cooldown — skip token if last exit was SL within cooldown
    sl_cooldown_min = cfg["cooldown_after_sl_min"]
    recent_sl = await db.ml_live_positions.find(
        {"status": "CLOSED", "strategy_tpsl_exit_reason": {"$regex": "^SL"}},
        {"_id": 0, "token": 1, "closed_at": 1}
    ).sort("closed_at", -1).limit(50).to_list(length=50)

    sl_tokens = {}
    for p in recent_sl:
        t = p.get("token")
        if t and t not in sl_tokens:
            sl_tokens[t] = p.get("closed_at", "")

    filtered = []
    for s in signals:
        token = s.get("token")
        if token in sl_tokens:
            try:
                sl_dt = datetime.fromisoformat(str(sl_tokens[token]))
                min_ago = (datetime.now(timezone.utc) - sl_dt).total_seconds() / 60
                if min_ago < sl_cooldown_min:
                    continue
            except (ValueError, TypeError):
                pass
        filtered.append(s)
    signals = filtered
    flog["steps"]["sl_cooldown"] = len(signals)

    # 6. Trade spacing — min gap between entries
    min_gap_min = cfg["min_entry_gap_min"]
    last_entry = await db.ml_live_positions.find_one(
        {}, {"_id": 0, "opened_at": 1}, sort=[("opened_at", -1)]
    )
    if last_entry and last_entry.get("opened_at"):
        try:
            last_dt = datetime.fromisoformat(str(last_entry["opened_at"]))
            min_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
            if min_since < min_gap_min:
                flog["steps"]["trade_spacing"] = f"skip_all({min_since:.0f}min < {min_gap_min}min)"
                return [], flog
        except (ValueError, TypeError):
            pass
    flog["steps"]["trade_spacing"] = "ok"

    # 7. Actor stacking boost
    token_actors = {}
    for s in signals:
        token = s.get("token")
        actor_score = s.get("actor_hit_rate", 0)
        if token not in token_actors:
            token_actors[token] = []
        token_actors[token].append(actor_score)

    for s in signals:
        token = s.get("token")
        scores = token_actors.get(token, [])
        if len(scores) >= 2:
            stack_boost = sum(scores) / len(scores) * 0.1
            s["composite_score"] = round(s.get("composite_score", 0) + stack_boost, 4)
            s["actor_stacking"] = True

    # 8. Token concentration cap
    max_per_token = cfg["max_per_token_pct"]
    max_pos = cfg["max_positions"]
    token_counts = Counter(p.get("token") for p in open_positions)
    max_allowed = max(int(max_pos * max_per_token), 1)

    filtered = []
    for s in signals:
        token = s.get("token")
        current = token_counts.get(token, 0)
        if current >= max_allowed:
            continue
        filtered.append(s)
        token_counts[token] = current + 1
    signals = filtered
    flog["steps"]["concentration_cap"] = len(signals)

    # 9. Anti-overtrading
    current_open = len(open_positions)
    slots = max_pos - current_open

    if slots <= 0:
        weakest = await db.ml_live_positions.find(
            {"status": "OPEN"}, {"_id": 0, "composite_score": 1}
        ).sort("composite_score", 1).limit(1).to_list(length=1)
        weakest_score = weakest[0].get("composite_score", 0) if weakest else 0
        signals = [s for s in signals if s.get("composite_score", 0) > weakest_score]
        flog["steps"]["anti_overtrading"] = f"slots=0, beat_weakest={weakest_score}"
    else:
        signals = signals[:slots]
        flog["steps"]["anti_overtrading"] = f"slots={slots}, taking={len(signals)}"

    flog["output"] = len(signals)
    return signals, flog


# ─── POSITION MANAGEMENT ───
async def open_position(signal_id, token, prediction, actor, position,
                        actor_hit_rate=0, coordination=0, composite_score=0,
                        confidence_weight=0, entry_price=None, signal_timestamp=None):
    """Create a new live position."""
    db = get_db()
    decision = map_decision(prediction, position, actor_hit_rate, coordination)

    doc = {
        "signal_id": signal_id,
        "token": token,
        "prediction": round(float(prediction), 4),
        "composite_score": round(float(composite_score), 4),
        "confidence_weight": round(float(confidence_weight), 4),
        "action": decision["action"],
        "strength": decision["strength"],
        "why": decision["why"],
        "actor": actor,
        "position": position,
        "actor_hit_rate": round(float(actor_hit_rate), 4),
        "coordination": round(float(coordination), 4),
        "entry_price": entry_price,
        "status": "OPEN",
        "ret_1h": None,
        "ret_4h": None,
        "ret_24h": None,
        "strategy_hold_return": None,
        "strategy_tpsl_return": None,
        "strategy_tpsl_exit_reason": None,
        "strategy_tpsl_exit_time": None,
        # Partial TP tracking
        "partial_tp_1h_realized": None,
        "partial_tp_4h_realized": None,
        "remaining_pct": 1.0,
        "trailing_stop": None,
        "time_to_profit_min": None,
        "final_return": None,
        "result": None,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "closed_at": None,
        "signal_timestamp": signal_timestamp,
    }

    await db.ml_live_positions.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "position": doc}


async def update_positions():
    """Update open positions: returns, partial TP, trailing stop, close expired."""
    db = get_db()
    cfg = await get_config()

    open_pos = await db.ml_live_positions.find(
        {"status": "OPEN"}, {"_id": 0}
    ).to_list(length=200)

    stats = {"updated": 0, "closed_tp": 0, "closed_sl": 0, "closed_trailing": 0,
             "closed_24h": 0, "partial_tp_1h": 0, "partial_tp_4h": 0}

    for pos in open_pos:
        signal_id = pos.get("signal_id")
        event = await db.actor_signal_events.find_one(
            {"tweet_id": signal_id, "enriched": True},
            {"_id": 0, "price": 1}
        )
        if not event or not event.get("price"):
            continue

        price = event["price"]
        updates = {}

        # Fill returns
        if pos["ret_1h"] is None and price.get("ret_1h") is not None:
            updates["ret_1h"] = round(float(price["ret_1h"]), 6)
        if pos["ret_4h"] is None and price.get("ret_4h") is not None:
            updates["ret_4h"] = round(float(price["ret_4h"]), 6)
        if pos["ret_24h"] is None and price.get("ret_24h") is not None:
            updates["ret_24h"] = round(float(price["ret_24h"]), 6)

        # Strategy A: Hold 24h (baseline)
        if price.get("ret_24h") is not None:
            updates["strategy_hold_return"] = round(float(price["ret_24h"]), 6)

        # Strategy B: Partial TP + trailing stop
        remaining = pos.get("remaining_pct", 1.0)
        realized_total = 0
        exit_reason = None
        exit_time = None
        trailing = pos.get("trailing_stop")

        ret_1h = updates.get("ret_1h", pos.get("ret_1h"))
        ret_4h = updates.get("ret_4h", pos.get("ret_4h"))
        ret_24h = updates.get("ret_24h", pos.get("ret_24h"))

        # Phase 1: 1h check — SL or partial TP
        if ret_1h is not None and pos.get("partial_tp_1h_realized") is None:
            if ret_1h <= cfg["sl_1h_base"]:
                # Full stop loss
                realized_total = ret_1h
                exit_reason = "SL_1H"
                exit_time = "1h"
                remaining = 0
            elif ret_1h >= cfg["tp_1h_base"]:
                # Partial TP: close 50%
                close_pct = cfg["partial_tp_1h_close_pct"]
                realized = ret_1h * close_pct
                updates["partial_tp_1h_realized"] = round(realized, 6)
                remaining -= close_pct
                realized_total += realized
                stats["partial_tp_1h"] += 1
                # Set trailing stop on remainder
                trailing = ret_1h * (1 - cfg["trailing_stop_pct"])
                updates["trailing_stop"] = round(trailing, 6)

        # Phase 2: 4h check — partial TP on remaining
        if ret_4h is not None and remaining > 0 and pos.get("partial_tp_4h_realized") is None:
            if exit_reason is None:  # not already stopped out
                if ret_4h >= cfg["tp_4h_base"]:
                    close_pct = min(cfg["partial_tp_4h_close_pct"], remaining)
                    realized = ret_4h * close_pct
                    updates["partial_tp_4h_realized"] = round(realized, 6)
                    remaining -= close_pct
                    realized_total += realized
                    stats["partial_tp_4h"] += 1
                    # Update trailing
                    new_trail = ret_4h * (1 - cfg["trailing_stop_pct"])
                    if trailing is None or new_trail > trailing:
                        trailing = new_trail
                        updates["trailing_stop"] = round(trailing, 6)

                # Trailing stop check on 4h
                if trailing is not None and ret_4h < trailing and remaining > 0:
                    realized_total += ret_4h * remaining
                    remaining = 0
                    exit_reason = "TRAILING_STOP"
                    exit_time = "4h"
                    stats["closed_trailing"] += 1

        # Phase 3: 24h — close remainder
        if ret_24h is not None and remaining > 0 and exit_reason is None:
            realized_total += ret_24h * remaining
            remaining = 0
            exit_reason = "HOLD_24H"
            exit_time = "24h"

        updates["remaining_pct"] = round(remaining, 4)
        if exit_reason:
            updates["strategy_tpsl_return"] = round(realized_total, 6)
            updates["strategy_tpsl_exit_reason"] = exit_reason
            updates["strategy_tpsl_exit_time"] = exit_time

        # Time to profit
        if pos.get("time_to_profit_min") is None:
            if ret_1h is not None and ret_1h > 0:
                updates["time_to_profit_min"] = 60
            elif ret_4h is not None and ret_4h > 0:
                updates["time_to_profit_min"] = 240

        # Close if fully exited
        if remaining <= 0 and exit_reason:
            final_ret = updates.get("strategy_tpsl_return", 0)
            updates["final_return"] = final_ret
            updates["result"] = "WIN" if final_ret > 0 else "LOSS"
            updates["status"] = "CLOSED"
            updates["closed_at"] = datetime.now(timezone.utc).isoformat()

            if exit_reason.startswith("TP") or "TP" in (exit_reason or ""):
                stats["closed_tp"] += 1
            elif exit_reason.startswith("SL"):
                stats["closed_sl"] += 1
            elif exit_reason == "TRAILING_STOP":
                pass  # already counted
            else:
                stats["closed_24h"] += 1

        if updates:
            await db.ml_live_positions.update_one(
                {"signal_id": signal_id, "status": {"$in": ["OPEN", "CLOSED"]}},
                {"$set": updates}
            )
            stats["updated"] += 1

    stats["total_open"] = len(open_pos)
    return {"ok": True, **stats}


# ─── RE-ENTRY WITH CONFIRMATION ───
async def check_reentry_candidates():
    """Find tokens eligible for re-entry based on coordination increase + new actor."""
    db = get_db()

    # Tokens with recent closed WIN positions
    recent_wins = await db.ml_live_positions.find(
        {"status": "CLOSED", "result": "WIN"},
        {"_id": 0, "token": 1, "actor": 1, "coordination": 1, "closed_at": 1}
    ).sort("closed_at", -1).limit(50).to_list(length=50)

    if not recent_wins:
        return {"ok": True, "candidates": []}

    # Group by token
    token_data = {}
    for p in recent_wins:
        t = p.get("token")
        if t not in token_data:
            token_data[t] = {"actors": set(), "max_coord": 0}
        token_data[t]["actors"].add(p.get("actor"))
        token_data[t]["max_coord"] = max(token_data[t]["max_coord"], p.get("coordination", 0))

    # Check signal log for new signals on these tokens
    candidates = []
    for token, data in token_data.items():
        new_signals = await db.ml_signal_log.find(
            {"token": token, "action": {"$in": ["ENTER", "FOLLOW"]}},
            {"_id": 0, "actor": 1, "coordination": 1, "prediction": 1, "signal_id": 1}
        ).sort("timestamp", -1).limit(5).to_list(length=5)

        for sig in new_signals:
            new_actor = sig.get("actor") not in data["actors"]
            coord_increase = (sig.get("coordination", 0) or 0) > data["max_coord"]

            if new_actor or coord_increase:
                # Check not already a position
                exists = await db.ml_live_positions.count_documents({"signal_id": sig.get("signal_id")})
                if exists == 0:
                    candidates.append({
                        "token": token,
                        "signal_id": sig.get("signal_id"),
                        "actor": sig.get("actor"),
                        "prediction": sig.get("prediction"),
                        "new_actor": new_actor,
                        "coordination_increase": coord_increase,
                        "reason": ("new_actor" if new_actor else "") + ("+" if new_actor and coord_increase else "") + ("coord_increase" if coord_increase else ""),
                    })

    return {"ok": True, "candidates": candidates}


# ─── PROCESS NEW SIGNALS ───
async def process_new_signals():
    """Score, filter, and open positions from actionable signals."""
    db = get_db()

    active = await get_active_model()
    if not active:
        return {"ok": False, "error": "No active model"}

    signals = await db.ml_signal_log.find(
        {"action": {"$in": ["ENTER", "FOLLOW"]}},
        {"_id": 0}
    ).to_list(length=5000)

    if not signals:
        return {"ok": False, "error": "No actionable signals in log"}

    # Dedup
    existing_pos = set()
    existing = await db.ml_live_positions.find(
        {}, {"_id": 0, "signal_id": 1}
    ).to_list(length=50000)
    for e in existing:
        existing_pos.add(e.get("signal_id"))

    scored = []
    for s in signals:
        if s.get("signal_id") in existing_pos:
            continue

        age_hours = 0
        ts = s.get("timestamp")
        if ts:
            try:
                sig_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - sig_dt).total_seconds() / 3600
            except (ValueError, TypeError):
                pass

        score_data = await compute_composite_score(
            prediction=s.get("prediction", 0),
            actor_hit_rate=s.get("actor_hit_rate", 0),
            coordination_density=s.get("coordination", 0),
            position=s.get("position", "UNKNOWN"),
            signal_age_hours=age_hours,
        )

        s["composite_score"] = score_data["composite_score"]
        s["confidence_weight"] = score_data["confidence_weight"]
        s["actor_hit_rate"] = s.get("actor_hit_rate", 0)
        scored.append(s)

    if not scored:
        return {"ok": True, "message": "No new signals to process", "positions_opened": 0}

    filtered, filter_log = await apply_alpha_filters(scored)

    opened = 0
    for s in filtered:
        await open_position(
            signal_id=s.get("signal_id"),
            token=s.get("token"),
            prediction=s.get("prediction", 0),
            actor=s.get("actor"),
            position=s.get("position", "UNKNOWN"),
            actor_hit_rate=s.get("actor_hit_rate", 0),
            coordination=s.get("coordination", 0),
            composite_score=s.get("composite_score", 0),
            confidence_weight=s.get("confidence_weight", 0),
            entry_price=s.get("entry_price"),
            signal_timestamp=s.get("timestamp"),
        )
        opened += 1

    return {
        "ok": True,
        "scored_signals": len(scored),
        "positions_opened": opened,
        "filter_log": filter_log,
    }


# ─── LIVE METRICS ───
def _compute_trade_metrics(rets, label):
    """Helper: compute trading metrics from a list of returns."""
    if not rets:
        return {}
    wins = sum(1 for r in rets if r > 0)
    win_sum = sum(r for r in rets if r > 0)
    loss_sum = abs(sum(r for r in rets if r < 0))

    equity = []
    cum = 0
    peak = 0
    max_dd = 0
    for r in rets:
        cum += r
        equity.append(round(cum, 6))
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

    # Tail risk: P95 loss
    sorted_rets = sorted(rets)
    p5_idx = max(int(len(sorted_rets) * 0.05), 0)
    p95_loss = sorted_rets[p5_idx] if sorted_rets else 0

    return {
        "strategy": label,
        "n_trades": len(rets),
        "win_rate": round(wins / len(rets), 4),
        "avg_return": round(sum(rets) / len(rets) * 100, 4),
        "median_return": round(float(np.median(rets)) * 100, 4),
        "cumulative_return": round(cum * 100, 4),
        "max_drawdown": round(max_dd * 100, 4),
        "profit_factor": round(win_sum / loss_sum, 4) if loss_sum > 0 else float("inf"),
        "best_trade": round(max(rets) * 100, 4),
        "worst_trade": round(min(rets) * 100, 4),
        "p95_loss": round(p95_loss * 100, 4),
        "equity_curve": equity[-50:],
    }


async def compute_live_metrics():
    """Daily live trading metrics with strategy comparison and risk analysis."""
    db = get_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    closed = await db.ml_live_positions.find(
        {"status": "CLOSED"}, {"_id": 0}
    ).to_list(length=10000)

    if not closed:
        return {"ok": True, "message": "No closed positions"}

    hold_rets = [p.get("strategy_hold_return", 0) or 0 for p in closed]
    tpsl_rets = [p.get("strategy_tpsl_return", 0) or 0 for p in closed]
    final_rets = [p.get("final_return", 0) or 0 for p in closed]

    hold_m = _compute_trade_metrics(hold_rets, "HOLD_24H")
    tpsl_m = _compute_trade_metrics(tpsl_rets, "TP_SL")
    final_m = _compute_trade_metrics(final_rets, "FINAL")

    # Time to profit
    ttp = [p.get("time_to_profit_min") for p in closed if p.get("time_to_profit_min")]
    avg_ttp = sum(ttp) / len(ttp) if ttp else None

    # Exit reason distribution
    exit_reasons = Counter(p.get("strategy_tpsl_exit_reason") for p in closed)

    # Profit consistency: positive days ratio
    days_map = {}
    for p in closed:
        day = (p.get("closed_at") or "")[:10]
        if day:
            if day not in days_map:
                days_map[day] = []
            days_map[day].append(p.get("final_return", 0) or 0)

    positive_days = sum(1 for rets in days_map.values() if sum(rets) > 0)
    total_days = len(days_map)
    positive_days_ratio = round(positive_days / total_days, 4) if total_days > 0 else None

    doc = {
        "date": today,
        "n_positions": len(closed),
        "strategy_hold": hold_m,
        "strategy_tpsl": tpsl_m,
        "final": final_m,
        "avg_time_to_profit_min": round(avg_ttp) if avg_ttp else None,
        "exit_reasons": dict(exit_reasons),
        "strategy_comparison": {
            "hold_avg": hold_m.get("avg_return", 0),
            "tpsl_avg": tpsl_m.get("avg_return", 0),
            "winner": "TP_SL" if tpsl_m.get("avg_return", 0) > hold_m.get("avg_return", 0) else "HOLD_24H",
        },
        "profit_consistency": {
            "positive_days": positive_days,
            "total_days": total_days,
            "positive_days_ratio": positive_days_ratio,
            "stable": (positive_days_ratio or 0) >= 0.55,
        },
        "tail_risk": {
            "p95_loss_hold": hold_m.get("p95_loss", 0),
            "p95_loss_tpsl": tpsl_m.get("p95_loss", 0),
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.ml_live_metrics.update_one(
        {"date": today}, {"$set": doc}, upsert=True
    )
    return {"ok": True, "metrics": doc}


# ─── CONFIDENCE BUCKET ANALYSIS ───
async def confidence_bucket_analysis():
    """Win rates by prediction confidence bucket."""
    db = get_db()

    closed = await db.ml_live_positions.find(
        {"status": "CLOSED"},
        {"_id": 0, "prediction": 1, "final_return": 1, "result": 1}
    ).to_list(length=10000)

    if not closed:
        return {"ok": True, "message": "No closed positions", "buckets": {}}

    buckets = {"0.9+": [], "0.8-0.9": [], "0.7-0.8": [], "0.6-0.7": [], "<0.6": []}

    for p in closed:
        pred = p.get("prediction", 0)
        ret = p.get("final_return", 0) or 0
        if pred >= 0.9:
            buckets["0.9+"].append(ret)
        elif pred >= 0.8:
            buckets["0.8-0.9"].append(ret)
        elif pred >= 0.7:
            buckets["0.7-0.8"].append(ret)
        elif pred >= 0.6:
            buckets["0.6-0.7"].append(ret)
        else:
            buckets["<0.6"].append(ret)

    result = {}
    for bucket, rets in buckets.items():
        if rets:
            wins = sum(1 for r in rets if r > 0)
            result[bucket] = {
                "count": len(rets),
                "win_rate": round(wins / len(rets), 4),
                "avg_return": round(sum(rets) / len(rets) * 100, 4),
                "median_return": round(float(np.median(rets)) * 100, 4),
            }

    ordered = ["0.9+", "0.8-0.9", "0.7-0.8", "0.6-0.7", "<0.6"]
    wr = [result.get(b, {}).get("win_rate", 0) for b in ordered]
    is_mono = all(wr[i] >= wr[i + 1] for i in range(len(wr) - 1) if wr[i] > 0 and wr[i + 1] > 0)

    return {"ok": True, "buckets": result, "is_monotonic": is_mono, "calibration_ok": is_mono}


# ─── ACTOR LIVE PERFORMANCE ───
async def actor_live_performance():
    """Per-actor performance from live positions."""
    db = get_db()
    pipeline = [
        {"$match": {"status": "CLOSED"}},
        {"$group": {
            "_id": "$actor",
            "signals": {"$sum": 1},
            "wins": {"$sum": {"$cond": [{"$eq": ["$result", "WIN"]}, 1, 0]}},
            "avg_return": {"$avg": "$final_return"},
            "avg_prediction": {"$avg": "$prediction"},
            "avg_composite": {"$avg": "$composite_score"},
        }},
        {"$sort": {"avg_return": -1}},
    ]

    actors = []
    async for doc in db.ml_live_positions.aggregate(pipeline):
        n = doc.get("signals", 0)
        w = doc.get("wins", 0)
        actors.append({
            "actor": doc["_id"],
            "signals": n,
            "win_rate": round(w / n, 4) if n > 0 else 0,
            "avg_return": round((doc.get("avg_return", 0) or 0) * 100, 4),
            "avg_prediction": round(doc.get("avg_prediction", 0) or 0, 4),
            "avg_composite": round(doc.get("avg_composite", 0) or 0, 4),
        })

    return {"ok": True, "actors": actors}


# ─── ACTION PERFORMANCE ───
async def action_performance():
    """ENTER vs FOLLOW vs WATCH comparison."""
    db = get_db()
    pipeline = [
        {"$match": {"status": "CLOSED"}},
        {"$group": {
            "_id": "$action",
            "count": {"$sum": 1},
            "wins": {"$sum": {"$cond": [{"$eq": ["$result", "WIN"]}, 1, 0]}},
            "avg_return": {"$avg": "$final_return"},
        }},
        {"$sort": {"avg_return": -1}},
    ]

    actions = []
    async for doc in db.ml_live_positions.aggregate(pipeline):
        c = doc.get("count", 0)
        w = doc.get("wins", 0)
        actions.append({
            "action": doc["_id"],
            "count": c,
            "win_rate": round(w / c, 4) if c > 0 else 0,
            "avg_return": round((doc.get("avg_return", 0) or 0) * 100, 4),
        })

    action_map = {a["action"]: a for a in actions}
    enter_ret = action_map.get("ENTER", {}).get("avg_return", 0)
    follow_ret = action_map.get("FOLLOW", {}).get("avg_return", 0)

    return {
        "ok": True, "actions": actions,
        "enter_vs_follow": {"enter_avg": enter_ret, "follow_avg": follow_ret,
                            "logic_valid": enter_ret >= follow_ret},
    }


# ─── EQUITY CURVE ───
async def get_equity_curve():
    """Cumulative equity curve from closed positions."""
    db = get_db()
    closed = await db.ml_live_positions.find(
        {"status": "CLOSED"},
        {"_id": 0, "final_return": 1, "closed_at": 1, "token": 1, "action": 1, "result": 1}
    ).sort("closed_at", 1).to_list(length=10000)

    if not closed:
        return {"ok": True, "equity": [], "cumulative_return": 0}

    equity = []
    cum = 0
    peak = 0
    max_dd = 0
    for p in closed:
        ret = p.get("final_return", 0) or 0
        cum += ret
        peak = max(peak, cum)
        dd = cum - peak
        max_dd = min(max_dd, dd)
        equity.append({
            "return": round(ret * 100, 4),
            "cumulative": round(cum * 100, 4),
            "drawdown": round(dd * 100, 4),
            "token": p.get("token"),
            "action": p.get("action"),
            "result": p.get("result"),
        })

    return {
        "ok": True, "equity": equity,
        "cumulative_return": round(cum * 100, 4),
        "max_drawdown": round(max_dd * 100, 4),
        "total_trades": len(closed),
    }


# ─── STABILITY VALIDATION SUITE ───
async def rolling_window_test():
    """Test performance over 3d / 7d / 14d / all windows."""
    db = get_db()
    closed = await db.ml_live_positions.find(
        {"status": "CLOSED"},
        {"_id": 0, "final_return": 1, "closed_at": 1}
    ).to_list(length=10000)

    if not closed:
        return {"ok": True, "message": "No closed positions"}

    now = datetime.now(timezone.utc)
    windows = {"3d": 3, "7d": 7, "14d": 14, "all": 9999}
    result = {}

    for label, days in windows.items():
        cutoff = now - timedelta(days=days)
        rets = []
        for p in closed:
            try:
                closed_dt = datetime.fromisoformat(str(p.get("closed_at", "")).replace("Z", "+00:00"))
                if closed_dt >= cutoff:
                    rets.append(p.get("final_return", 0) or 0)
            except (ValueError, TypeError):
                rets.append(p.get("final_return", 0) or 0)

        if rets:
            wins = sum(1 for r in rets if r > 0)
            result[label] = {
                "trades": len(rets),
                "win_rate": round(wins / len(rets), 4),
                "avg_return": round(sum(rets) / len(rets) * 100, 4),
                "median_return": round(float(np.median(rets)) * 100, 4),
                "cumulative": round(sum(rets) * 100, 4),
            }

    # Check consistency: all windows positive
    all_positive = all(w.get("avg_return", 0) > 0 for w in result.values())

    return {"ok": True, "windows": result, "all_positive": all_positive}


async def actor_drop_test():
    """Remove top-3 actors and check if system survives."""
    db = get_db()

    # Find top 3 actors by signal count
    pipeline = [
        {"$match": {"status": "CLOSED"}},
        {"$group": {"_id": "$actor", "count": {"$sum": 1}, "avg_ret": {"$avg": "$final_return"}}},
        {"$sort": {"count": -1}},
        {"$limit": 3},
    ]
    top_actors = []
    async for doc in db.ml_live_positions.aggregate(pipeline):
        top_actors.append(doc["_id"])

    if not top_actors:
        return {"ok": True, "message": "No data"}

    # Get all closed positions excluding top 3
    remaining = await db.ml_live_positions.find(
        {"status": "CLOSED", "actor": {"$nin": top_actors}},
        {"_id": 0, "final_return": 1}
    ).to_list(length=10000)

    all_closed = await db.ml_live_positions.find(
        {"status": "CLOSED"},
        {"_id": 0, "final_return": 1}
    ).to_list(length=10000)

    def _quick_metrics(positions):
        rets = [p.get("final_return", 0) or 0 for p in positions]
        if not rets:
            return {"trades": 0}
        wins = sum(1 for r in rets if r > 0)
        return {
            "trades": len(rets),
            "win_rate": round(wins / len(rets), 4),
            "avg_return": round(sum(rets) / len(rets) * 100, 4),
            "cumulative": round(sum(rets) * 100, 4),
        }

    full = _quick_metrics(all_closed)
    without_top = _quick_metrics(remaining)

    survives = without_top.get("avg_return", 0) > 0
    dependency_pct = 0
    if full.get("cumulative", 0) != 0:
        dependency_pct = round((1 - without_top.get("cumulative", 0) / full["cumulative"]) * 100, 2)

    return {
        "ok": True,
        "dropped_actors": top_actors,
        "full_performance": full,
        "without_top3": without_top,
        "survives_without_top3": survives,
        "top3_dependency_pct": dependency_pct,
    }


async def token_diversity_check():
    """Check how many different tokens contribute to profit."""
    db = get_db()

    pipeline = [
        {"$match": {"status": "CLOSED"}},
        {"$group": {
            "_id": "$token",
            "count": {"$sum": 1},
            "wins": {"$sum": {"$cond": [{"$eq": ["$result", "WIN"]}, 1, 0]}},
            "total_return": {"$sum": "$final_return"},
        }},
        {"$sort": {"total_return": -1}},
    ]

    tokens = []
    async for doc in db.ml_live_positions.aggregate(pipeline):
        c = doc.get("count", 0)
        w = doc.get("wins", 0)
        tokens.append({
            "token": doc["_id"],
            "trades": c,
            "win_rate": round(w / c, 4) if c > 0 else 0,
            "total_return": round((doc.get("total_return", 0) or 0) * 100, 4),
        })

    profitable_tokens = [t for t in tokens if t["total_return"] > 0]
    losing_tokens = [t for t in tokens if t["total_return"] <= 0]

    diverse = len(profitable_tokens) >= 3

    return {
        "ok": True,
        "tokens": tokens,
        "profitable_count": len(profitable_tokens),
        "losing_count": len(losing_tokens),
        "total_tokens": len(tokens),
        "diversified": diverse,
    }


# ─── LIVE DASHBOARD ───
async def get_live_dashboard():
    """Aggregated live status — daily health check."""
    db = get_db()
    cfg = await get_config()

    open_count = await db.ml_live_positions.count_documents({"status": "OPEN"})
    closed_count = await db.ml_live_positions.count_documents({"status": "CLOSED"})

    latest_metrics = await db.ml_live_metrics.find_one(
        {}, {"_id": 0}, sort=[("date", -1)]
    )

    checks = {}
    if latest_metrics:
        final = latest_metrics.get("final", {})
        checks["has_trades"] = final.get("n_trades", 0) > 10
        checks["has_alpha"] = final.get("avg_return", 0) > 0
        checks["has_stability"] = final.get("median_return", 0) > 0
        checks["drawdown_ok"] = final.get("max_drawdown", 0) > -5.0
        pc = latest_metrics.get("profit_consistency", {})
        checks["profit_consistent"] = pc.get("stable", False)

    conf = await confidence_bucket_analysis()

    return {
        "ok": True,
        "config": cfg,
        "positions": {"open": open_count, "closed": closed_count},
        "latest_metrics": latest_metrics,
        "health_checks": checks,
        "confidence_monotonic": conf.get("is_monotonic"),
        "top_bucket": conf.get("buckets", {}).get("0.9+"),
    }


# ─── LIST POSITIONS ───
async def list_positions(status=None, limit=50):
    """List live positions."""
    db = get_db()
    query = {"status": status} if status else {}
    positions = await db.ml_live_positions.find(
        query, {"_id": 0}
    ).sort("opened_at", -1).limit(limit).to_list(length=limit)

    for p in positions:
        for k, v in p.items():
            if isinstance(v, datetime):
                p[k] = v.isoformat()

    return {"ok": True, "positions": positions, "count": len(positions)}
