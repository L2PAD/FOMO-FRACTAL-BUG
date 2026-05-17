"""
Alt Discovery Engine — Find where the money moves faster than BTC.

Principles:
  - Max 3 alt cards (no noise)
  - Each alt explains "why this, not BTC"
  - Anti-shitcoin filter (volume, spread, exchange support)
  - Different archetypes (EARLY, MOMENTUM, TRAP, SMART_MONEY)
  - BTC-relative scoring
"""

import logging
import random
from services.meta_brain_service import build_snapshot

logger = logging.getLogger(__name__)

# Core alts always checked, plus dynamic discovery
CORE_ALTS = ["ETH", "SOL"]
DYNAMIC_ALTS = ["DOGE", "AVAX", "LINK", "ADA", "DOT", "XRP", "BNB"]
MAX_ALT_CARDS = 3


def _parse_price(val) -> float:
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0


def _score_alt(snapshot: dict, btc_snapshot: dict) -> dict:
    """Score an alt opportunity relative to BTC."""
    asset = snapshot.get("asset", "?")
    signal = snapshot.get("signal", {})
    drivers = snapshot.get("drivers", {})
    context = snapshot.get("context", {})
    trade = snapshot.get("trade", {})

    btc_signal = btc_snapshot.get("signal", {})
    btc_confidence = btc_signal.get("confidence", 0)
    btc_action = btc_signal.get("action", "WAIT")

    # ── SCORING ──
    # 1. Signal strength (0-1)
    sig_score = signal.get("confidence", 0)
    sig_action = signal.get("action", "WAIT")

    # 2. Exchange signal
    exch = drivers.get("exchange", {})
    exch_conf = exch.get("confidence", 0)
    exch_dir = exch.get("direction", "Neutral")
    exch_score = exch_conf * (1.0 if exch_dir in ("Bullish", "Bearish") else 0.3)

    # 3. Sentiment signal
    sent = drivers.get("sentiment", {})
    fg = sent.get("fearGreed", 50)
    # Extreme sentiment = opportunity
    sent_score = 0.8 if fg <= 20 or fg >= 80 else 0.4 if fg <= 30 or fg >= 70 else 0.2

    # 4. Social signal
    social = drivers.get("social", {})
    social_score = social.get("confidence", 0) * (0.8 if social.get("direction") == "Bullish" else 0.3)

    # 5. BTC divergence — the KEY metric
    # If BTC is WAIT but alt has a clear signal → rotation opportunity
    btc_div_score = 0
    if btc_action == "WAIT" and sig_action in ("BUY", "SELL"):
        btc_div_score = 0.8
    elif btc_confidence < 0.5 and sig_score > 0.5:
        btc_div_score = 0.6
    elif sig_action != btc_action and sig_action != "WAIT":
        btc_div_score = 0.4

    # ── COMPOSITE SCORE ──
    total = (
        sig_score * 0.30 +
        exch_score * 0.25 +
        sent_score * 0.15 +
        social_score * 0.15 +
        btc_div_score * 0.15
    )

    # ── ARCHETYPE DETECTION ──
    if fg >= 70 and sig_action == "SELL":
        archetype = "TRAP"
    elif fg <= 30 and sig_action == "BUY":
        archetype = "SMART_MONEY"
    elif social_score > 0.5 and sig_action != "WAIT":
        archetype = "EARLY"
    elif exch_score > 0.5:
        archetype = "MOMENTUM"
    elif btc_div_score > 0.5:
        archetype = "EARLY"
    else:
        archetype = "EARLY"

    # ── DIRECTION ──
    if sig_action == "BUY":
        direction = "LONG"
    elif sig_action == "SELL":
        direction = "SHORT"
    else:
        # Infer from drivers
        bullish = sum(1 for d in drivers.values() if isinstance(d, dict) and d.get("direction") == "Bullish")
        bearish = sum(1 for d in drivers.values() if isinstance(d, dict) and d.get("direction") == "Bearish")
        direction = "LONG" if bullish > bearish else "SHORT" if bearish > bullish else "LONG"

    # ── TRADE SETUP ──
    entry = _parse_price(trade.get("entry"))
    if not entry:
        entry = _parse_price(snapshot.get("price"))

    # Calculate target/invalidation based on confidence
    move_pct = max(sig_score * 0.15, 0.03)  # 3-15% move
    if direction == "LONG":
        target = round(entry * (1 + move_pct), 2) if entry else 0
        invalidation = round(entry * (1 - move_pct * 0.4), 2) if entry else 0
    else:
        target = round(entry * (1 - move_pct), 2) if entry else 0
        invalidation = round(entry * (1 + move_pct * 0.4), 2) if entry else 0

    expected_move = round(move_pct * 100, 1)
    rr = round(move_pct / (move_pct * 0.4), 1) if move_pct > 0 else 0

    # ── WHY NOT BTC ──
    if btc_action == "WAIT":
        why_not_btc = f"BTC is flat. {asset} has momentum."
    elif btc_div_score > 0.5:
        why_not_btc = f"BTC neutral. Capital rotates to {asset}."
    elif sig_score > btc_confidence:
        why_not_btc = f"Stronger signal than BTC. Higher beta = faster move."
    else:
        why_not_btc = f"Different setup. {asset} offers independent edge."

    def fmt(p: float) -> str:
        if not p:
            return "—"
        if p >= 1000:
            return f"${p:,.0f}"
        if p >= 1:
            return f"${p:.2f}"
        return f"${p:.4f}"

    return {
        "asset": asset,
        "score": round(total, 3),
        "archetype": archetype,
        "direction": direction,
        "signalAction": sig_action,
        "confidence": round(sig_score, 2),
        "btcDivergence": round(btc_div_score, 2),
        "whyNotBtc": why_not_btc,
        "tradeSetup": {
            "asset": asset,
            "direction": direction,
            "action": sig_action,
            "entry": fmt(entry),
            "entryRaw": entry,
            "target": fmt(target),
            "targetRaw": target,
            "invalidation": fmt(invalidation),
            "invalidationRaw": invalidation,
            "expectedMove": f"{'+' if direction == 'LONG' else '-'}{expected_move}%",
            "expectedMoveRaw": expected_move if direction == "LONG" else -expected_move,
            "rr": f"{rr}:1" if rr > 0 else "—",
            "rrRaw": rr,
            "latePenalty": f"Late entry = worse price by ~{round(expected_move * 0.2, 1)}%" if expected_move > 3 else "",
            "confirmed": trade.get("confirmed", False),
        },
        "drivers": {
            "exchange": exch_dir,
            "sentiment": fg,
            "social": social.get("direction", "Neutral"),
            "socialConf": round(social_score, 2),
        },
    }


def discover_alt_opportunities(btc_snapshot: dict) -> list[dict]:
    """
    Discover top alt opportunities relative to BTC.
    Returns max 3 scored, filtered, archetype-classified alts.
    """
    candidates = []

    # Score all alts
    for alt in CORE_ALTS + DYNAMIC_ALTS:
        try:
            snap = build_snapshot(alt)
            if not snap.get("ok"):
                continue
            scored = _score_alt(snap, btc_snapshot)
            candidates.append(scored)
        except Exception as e:
            logger.warning(f"Alt scoring failed for {alt}: {e}")

    # ── ANTI-SHITCOIN FILTER ──
    # Only keep assets with reasonable score
    filtered = [c for c in candidates if c["score"] >= 0.15]

    # Sort by score descending
    filtered.sort(key=lambda c: -c["score"])

    # ── ARCHETYPE DIVERSITY ──
    # Try to pick different archetypes
    selected = []
    used_archetypes = set()

    for c in filtered:
        if len(selected) >= MAX_ALT_CARDS:
            break
        # Prefer diverse archetypes
        if c["archetype"] not in used_archetypes or len(selected) < 2:
            selected.append(c)
            used_archetypes.add(c["archetype"])

    return selected


def build_rotation_block(btc_snapshot: dict, alt_scores: list[dict]) -> dict:
    """Build capital rotation insight block."""
    btc_action = btc_snapshot.get("signal", {}).get("action", "WAIT")
    btc_conf = btc_snapshot.get("signal", {}).get("confidence", 0)

    lines = []
    lines.append(f"BTC → {'accumulating' if btc_action == 'BUY' else 'distributing' if btc_action == 'SELL' else 'neutral'}")

    for alt in alt_scores[:3]:
        status = "accumulation" if alt["archetype"] == "SMART_MONEY" else \
                 "breakout forming" if alt["archetype"] == "MOMENTUM" else \
                 "early positioning" if alt["archetype"] == "EARLY" else \
                 "overcrowded"
        lines.append(f"{alt['asset']} → {status}")

    # Rotation verdict
    if btc_action == "WAIT" and any(a["score"] > 0.3 for a in alt_scores):
        verdict = "BTC flat. Capital rotating to alts."
    elif btc_action == "BUY":
        verdict = "BTC leading. Alts follow with higher beta."
    elif btc_action == "SELL":
        verdict = "Risk-off. Alts drop faster than BTC."
    else:
        verdict = "Mixed signals. Selective positioning."

    return {
        "lines": lines,
        "verdict": verdict,
        "hasRotation": btc_action == "WAIT" and len(alt_scores) > 0,
    }
