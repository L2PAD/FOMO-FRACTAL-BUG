"""
Signals Route — Decision Engine API for mobile app.
GET /api/mobile/signals — all signals
GET /api/mobile/signals/latest — debug: latest signals with event metadata
GET /api/mobile/signals/{asset} — single asset signal
GET /api/mobile/market-state — aggregated market state for Home
"""
import logging
from fastapi import APIRouter, Query, Request
from services.signals_service import generate_signal, generate_all_signals, get_market_state

logger = logging.getLogger(__name__)
router = APIRouter()

PRO_FIELDS = ["entryZone", "takeProfit", "stopLoss"]


def _get_user_plan(request: Request) -> str:
    """Extract user plan from auth context."""
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict):
        plan = user.get("plan", "free")
        if plan in ("active", "pro", "PRO"):
            return "PRO"
    return "FREE"


def _get_user_id(request: Request) -> str:
    """Extract user ID for intent scoring."""
    user = getattr(request.state, 'user', None)
    if user:
        return str(user.get('_id', ''))
    # Fallback: check header or cookie
    uid = request.headers.get('x-user-id', '')
    if not uid:
        uid = request.cookies.get('userId', 'anonymous')
    return uid


def _apply_partial_reveal(signal: dict, plan: str, user_id: str = None) -> dict:
    """For FREE users: strip exact levels, add dynamic teasers with A/B variants.
    Uses User Intent Score for personalized pressure escalation."""
    if plan == "PRO":
        signal["accessLevel"] = "PRO"
        return signal

    signal["accessLevel"] = "FREE"

    action = signal.get("action", "WAIT").upper()
    has_entry = bool(signal.get("entryZone"))
    has_target = bool(signal.get("takeProfit"))
    has_stop = bool(signal.get("stopLoss"))
    confidence = signal.get("confidence", 0)

    for f in PRO_FIELDS:
        signal.pop(f, None)

    direction = "LONG" if action == "BUY" else "SHORT" if action == "SELL" else None
    truth = signal.get("truth", {})
    win_rate = truth.get("winRate", 0)
    wins = truth.get("wins", 0)
    total = truth.get("totalTrades", 0)
    recent = truth.get("recent", [])
    last_pnl = recent[0] if recent else None

    # ── Dynamic stage (EARLY / CONFIRMED / LATE) ──
    if confidence >= 0.6:
        stage = "CONFIRMED"
    elif confidence >= 0.35:
        stage = "FORMING"
    else:
        stage = "EARLY"

    # ── Entry teaser by stage ──
    if stage == "CONFIRMED":
        entry_teaser = "Entry confirmed" if has_entry else "Entry zone forming"
    elif stage == "FORMING":
        entry_teaser = "Entry zone identified" if has_entry else "Entry forming"
    else:
        entry_teaser = "Early entry forming" if has_entry else "Setup detected"

    # ── Pressure line by stage ──
    # ── PRESSURE LEVEL (1-4 escalation) ──
    df = signal.get("decisionFramework", {})
    backend_stage = df.get("stage", "EARLY")
    aligned = df.get("alignedCount", 0)

    if backend_stage == "SIGNAL" or aligned >= 5:
        signal_pressure = 4
    elif backend_stage == "CONFIRMING" or aligned >= 3:
        signal_pressure = 3
    elif backend_stage == "FORMING" or aligned >= 2:
        signal_pressure = 2
    else:
        signal_pressure = 1

    # ── DYNAMIC PRESSURE via User Intent Score ──
    from services.intent_score_service import get_dynamic_pressure
    dp = get_dynamic_pressure(signal_pressure, user_id)
    pressure_level = dp["pressureLevel"]
    pressure = dp["pressureText"]

    # ── Potential range (from signal data) ──
    potential = f"+{min(abs(signal.get('score',0)*20), 8):.0f}–{min(abs(signal.get('score',0)*20)+3, 15):.0f}%" if action in ("BUY", "SELL") else None

    # ── Truth line A/B test (TEST #3) ──
    truth_variants = []
    if total >= 4 and wins >= 3:
        truth_variants = [
            f"Last similar setup: +{last_pnl:.1f}%" if last_pnl and last_pnl > 0 else f"{wins} of last {total} similar setups profitable",
            f"{wins} of last {total} similar setups were profitable",
            f"Similar setups avg: +{int(win_rate * 100)}% | Win rate: {int(wins/max(total,1)*100)}%",
            f"Top traders entered earlier. Avg profit: +{last_pnl:.1f}%" if last_pnl else f"Top traders already positioned",
        ]
    elif last_pnl is not None and last_pnl > 0:
        truth_variants = [
            f"Last similar setup: +{last_pnl:.1f}%",
            f"Similar setups tend to be profitable",
            f"Similar setups avg: +{last_pnl:.1f}%",
            f"Top traders entered earlier. Avg profit: +{last_pnl:.1f}%",
        ]
    else:
        truth_variants = [
            "System learning — first outcomes soon",
            "System learning — building track record",
            "Tracking performance — outcomes incoming",
            "System calibrating — early stage",
        ]

    import hashlib
    user_hash = int(hashlib.md5((user_id or "dev").encode()).hexdigest(), 16)
    truth_idx = user_hash % len(truth_variants)
    truth_line = truth_variants[truth_idx]
    truth_variant = chr(65 + truth_idx)

    # ── CTA A/B test (TEST #1) ──
    cta_variants = [
        "Unlock exact entry",           # A — abstract
        "See exact buy level",          # B — concrete
        "Enter before the move",        # C — action
        "Get entry, target & stop",     # D — specificity
    ]
    cta_idx = (user_hash >> 4) % len(cta_variants)
    cta = cta_variants[cta_idx]
    cta_variant = chr(65 + cta_idx)
    cta_sub = ["Unlock PRO to see levels", "One tap to see the number", "Window is narrowing", "Full execution plan inside"][cta_idx]

    # ── Early Paywall (TEST #2) — light paywall BEFORE drivers ──
    ew = signal.get("entryWindow", {})
    ep_variants = [
        None,  # A — control (no early paywall)
        {  # B — early + entry info
            "headline": "Entry identified",
            "subline": f"Expected move: +{min(abs(signal.get('score',0)*20), 8):.0f}–{min(abs(signal.get('score',0)*20)+3, 15):.0f}%",
            "cta": "See entry",
            "sub": "You're one step away from entry",
        },
        {  # C — early + urgency
            "headline": ew.get("label", "Entry forming"),
            "subline": ew.get("urgency", ""),
            "cta": "Enter now",
            "sub": "Window is narrowing",
        },
        {  # D — early + social
            "headline": "PRO users already inside",
            "subline": f"Expected move: +{min(abs(signal.get('score',0)*20), 8):.0f}–{min(abs(signal.get('score',0)*20)+3, 15):.0f}%",
            "cta": "See entry",
            "sub": pressure,
        },
    ]
    ep_idx = (user_hash >> 8) % len(ep_variants)
    early_paywall = ep_variants[ep_idx]
    ep_variant = chr(65 + ep_idx)

    # ── Micro-FOMO by stage ──
    df = signal.get("decisionFramework", {})
    backend_stage_label = df.get("stage", "EARLY")
    if backend_stage_label == "SIGNAL":
        micro_fomo = "Late entries get worse prices"
    elif backend_stage_label == "CONFIRMING":
        micro_fomo = "Confirmation building — best entries happen now"
    elif backend_stage_label == "FORMING":
        micro_fomo = "Price moves before the crowd enters"
    else:
        micro_fomo = "Early entries get better positioning"

    # ── Timing urgency ──
    signal_age = signal.get("signalAgeHours") or ew.get("ageHours")
    if signal_age is not None and signal_age < 3:
        timing = "Entry window is narrowing"
    elif signal_age is not None and signal_age < 12:
        timing = "High activity now — signal likely to update soon"
    else:
        timing = None

    # ── "Almost decided" line ──
    almost_line = "You already see the setup. You just can't act on it" if action in ("BUY", "SELL") else None

    signal["partialReveal"] = {
        "locked": True,
        "stage": stage,
        "pressureLevel": pressure_level,
        "intentScore": dp.get("intentScore", 0),
        "intentLevel": dp.get("intentLevel", "COLD"),
        "hasEntry": has_entry,
        "direction": signal.get("direction"),
        "potentialRange": potential,
        "pressureLine": pressure,
        "truthLine": truth_line,
        "microFomo": micro_fomo,
        "timing": timing,
        "almostLine": almost_line,
        "cta": cta,
        "ctaSub": cta_sub,
        "ctaVariant": cta_variant,
        "earlyPaywall": early_paywall,
        "experiments": {
            "cta": cta_variant,
            "earlyPaywall": ep_variant,
            "truth": truth_variant,
        },
    }

    return signal


@router.get("/signals")
async def get_signals(
    request: Request,
    horizon: str = Query(default="swing"),
    assets: str = Query(default=""),
):
    """Get unified signals for all tracked assets."""
    plan = _get_user_plan(request)
    user_id = _get_user_id(request)
    asset_list = [a.strip().upper() for a in assets.split(",") if a.strip()] if assets else None
    signals = generate_all_signals(asset_list, horizon)
    signals = [_apply_partial_reveal(s, plan, user_id) for s in signals]
    return {"ok": True, "signals": signals, "count": len(signals)}


@router.get("/signals/latest")
async def get_latest_signals():
    """Debug endpoint: Get top signals with full event metadata."""
    signals = generate_all_signals(["BTC", "ETH", "SOL"], "swing")
    result = []
    for s in signals:
        result.append({
            "symbol": s["asset"],
            "verdict": s["action"],
            "confidence": s["confidence"],
            "direction": s["direction"],
            "eventTitle": s.get("eventTitle"),
            "stateLabel": s.get("stateLabel"),
            "isNew": s.get("isNew"),
            "confInterpretation": s.get("confInterpretation"),
            "scarcityText": s.get("scarcityText"),
            "timelineText": s.get("timelineText"),
            "lossText": s.get("lossText"),
            "weeklySignalCount": s.get("weeklySignalCount"),
            "signalAgeHours": s.get("signalAgeHours"),
            "driverSummary": s.get("driverSummary"),
            "truth": s.get("truth"),
            "source": "shadow",
        })
    return {"ok": True, "signals": result, "count": len(result)}


@router.get("/signals/{asset}")
async def get_signal(request: Request, asset: str, horizon: str = Query(default="swing")):
    """Get unified signal for a single asset."""
    plan = _get_user_plan(request)
    user_id = _get_user_id(request)
    signal = generate_signal(asset.upper(), horizon)
    signal = _apply_partial_reveal(signal, plan, user_id)
    return {"ok": True, "signal": signal}


@router.get("/market-state")
async def market_state():
    """Get aggregated market state for Home screen."""
    state = get_market_state()
    return {"ok": True, **state}
