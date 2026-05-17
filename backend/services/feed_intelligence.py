"""
Feed Intelligence 4.0 — Execution-Grade Intelligence.

Every card = ready trade.
NOT insight. NOT analysis. ACTION + MONEY.

Card structure:
  HOOK → CROWD → REALITY →
  💰 TRADE SETUP (entry/target/invalidation/move/rr) →
  CONVICTION → URGENCY → CTA
"""

import os
import logging
import random
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]


# ═══════════════════════════════════════════
#  ARCHETYPE DETECTION
# ═══════════════════════════════════════════

def _detect_archetype(snapshot: dict, edge: float, mkt_prob: int) -> str:
    drivers = snapshot.get("drivers", {})
    fg = drivers.get("sentiment", {}).get("fearGreed", 50)
    netflow = drivers.get("onchain", {}).get("stablecoinNetflow", 0)
    social = drivers.get("social", {})
    social_hot = social.get("direction") == "Bullish" and social.get("confidence", 0) > 0.4

    if fg >= 70 and edge < -10:
        return "TRAP"
    if mkt_prob > 70 and edge < -15:
        return "TRAP"
    if netflow and netflow > 5_000_000 and fg <= 35:
        return "SMART_MONEY"
    if netflow and netflow < -5_000_000 and fg >= 65:
        return "SMART_MONEY"
    if social_hot and abs(edge) > 10:
        return "EARLY"
    if mkt_prob > 60 and edge < -10:
        return "CONTRARIAN"
    if mkt_prob < 40 and edge > 10:
        return "CONTRARIAN"
    if abs(edge) > 20:
        return "CONTRARIAN"
    if abs(edge) > 10:
        return "EARLY"
    return "EARLY"


# ═══════════════════════════════════════════
#  HEADLINES — Asset-anchored + conflict
# ═══════════════════════════════════════════

_HL = {
    "CONTRARIAN": [
        "{asset} crowd picked a side.\nThe wrong one.",
        "Nobody believes {asset} moves.\nThat's the opportunity.",
        "{prob}% are sure about {asset}.\nThey're wrong.",
    ],
    "EARLY": [
        "{asset} is flat.\nPositioning is not.",
        "{asset} looks quiet.\nSomething is shifting.",
        "Movement forming on {asset}.\nPrice still sleeping.",
    ],
    "TRAP": [
        "Everyone's in {asset}.\nThat's the trap.",
        "{asset} confidence peaking.\nSo is the risk.",
        "They're all long {asset}.\nSmart money is out.",
    ],
    "SMART_MONEY": [
        "{asset}: Crowd panics.\nMoney accumulates.",
        "{asset}: Retail sells.\nWhales are loading.",
        "{asset}: Fear is loud.\nMoney is quiet.",
    ],
}


def _headline(archetype: str, asset: str, mkt_prob: int) -> str:
    pool = _HL.get(archetype, _HL["EARLY"])
    h = random.choice(pool)
    return h.replace("{asset}", asset).replace("{prob}", str(mkt_prob))


# ═══════════════════════════════════════════
#  CROWD
# ═══════════════════════════════════════════

def _crowd(mkt_prob: int) -> str:
    if mkt_prob > 70:
        return f'"{mkt_prob}% bet on this"'
    if mkt_prob > 50:
        return f'"Majority expects it ({mkt_prob}%)"'
    if mkt_prob < 30:
        return f'"Only {mkt_prob}% believe this"'
    return f'"{mkt_prob}% — market is split"'


# ═══════════════════════════════════════════
#  REALITY PUNCHES
# ═══════════════════════════════════════════

def _reality(snapshot: dict) -> list[str]:
    punches = []
    drivers = snapshot.get("drivers", {})
    fg = drivers.get("sentiment", {}).get("fearGreed", 50)
    if fg <= 20:
        punches.append("Extreme fear. That's where bottoms form.")
    elif fg <= 30:
        punches.append("Fear rising. Crowd selling to future winners.")
    elif fg >= 80:
        punches.append("Euphoria. When all agree — market turns.")
    elif fg >= 70:
        punches.append("Greed rising. Last ones in lose most.")

    netflow = drivers.get("onchain", {}).get("stablecoinNetflow", 0)
    if netflow and netflow > 10_000_000:
        punches.append(f"${netflow/1e6:.0f}M in. Big players loading.")
    elif netflow and netflow > 5_000_000:
        punches.append("Fresh capital entering. Someone knows.")
    elif netflow and netflow < -10_000_000:
        punches.append(f"${abs(netflow)/1e6:.0f}M out. Money already left.")
    elif netflow and netflow < -5_000_000:
        punches.append("Capital draining. Crowd hasn't noticed.")

    social = drivers.get("social", {})
    if social.get("direction") == "Bullish" and social.get("confidence", 0) > 0.5:
        punches.append("Attention rising. Price hasn't moved.")
    elif social.get("confidence", 0) < 0.3:
        punches.append("Social silence. Moves start in silence.")

    if not punches:
        punches.append("Mixed signals. But the gap is real.")
    return punches[:3]


# ═══════════════════════════════════════════
#  TRADE SETUP — The money layer
# ═══════════════════════════════════════════

def _parse_price(val) -> float:
    """Parse price from various formats: '$71,102', 71102, '71102.5'"""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0


# ═══════════════════════════════════════════
#  TIMEFRAME — from signal horizon
# ═══════════════════════════════════════════

_HORIZON_MAP = {
    "scalp": {"tf": "15m", "hold": "Minutes", "label": "Scalp"},
    "intraday": {"tf": "4H", "hold": "Hours", "label": "Intraday"},
    "swing": {"tf": "1D", "hold": "2-5 days", "label": "Swing"},
    "position": {"tf": "1W", "hold": "1-4 weeks", "label": "Position"},
    "macro": {"tf": "1M", "hold": "Weeks-Months", "label": "Macro"},
}


def _get_timeframe(snapshot: dict, edge: float) -> dict:
    """Determine timeframe from signal horizon and edge magnitude."""
    signal = snapshot.get("signal", {})
    horizon = signal.get("horizon", "")

    if horizon and horizon in _HORIZON_MAP:
        return _HORIZON_MAP[horizon]

    # Fallback: infer from edge magnitude
    ae = abs(edge)
    if ae > 30:
        return _HORIZON_MAP["swing"]
    if ae > 15:
        return _HORIZON_MAP["intraday"]
    return _HORIZON_MAP["swing"]


def _build_trade_setup(snapshot: dict, edge: float, asset: str) -> dict:
    """Build actionable trade setup from MetaBrain snapshot."""
    trade = snapshot.get("trade", {})
    signal = snapshot.get("signal", {})
    timeframe = _get_timeframe(snapshot, edge)

    direction = "LONG" if edge > 0 else "SHORT"
    sig_action = signal.get("action", "WAIT")

    # Parse price — try snapshot.price, then trade.entry
    price = _parse_price(snapshot.get("price"))
    entry_raw = _parse_price(trade.get("entry"))
    inv_raw = _parse_price(trade.get("invalidation"))
    target_raw = _parse_price(trade.get("target"))

    # Use entry from trade setup, fallback to price
    entry = entry_raw if entry_raw > 0 else price
    if entry == 0:
        entry = price

    # Calculate target
    if target_raw > 0:
        target = target_raw
    elif entry > 0:
        move_pct = abs(edge) / 100 * 0.7
        if direction == "LONG":
            target = round(entry * (1 + move_pct), 1)
        else:
            target = round(entry * (1 - move_pct), 1)
    else:
        target = 0

    # Calculate invalidation
    if inv_raw > 0:
        invalidation = inv_raw
    elif entry > 0:
        risk_pct = abs(edge) / 100 * 0.3
        if direction == "LONG":
            invalidation = round(entry * (1 - risk_pct), 1)
        else:
            invalidation = round(entry * (1 + risk_pct), 1)
    else:
        invalidation = 0

    # Calculate expected move and R:R
    expected_move = 0
    rr = 0
    if entry and target:
        expected_move = round((target - entry) / entry * 100, 1)
    if entry and target and invalidation and abs(entry - invalidation) > 0:
        rr = round(abs(target - entry) / abs(entry - invalidation), 1)

    # "You vs Market" — advantage of entering now vs later
    late_penalty = round(abs(edge) * 0.15, 1) if abs(edge) > 10 else 0

    # Format prices
    def fmt(p: float) -> str:
        if not p:
            return "—"
        if p >= 1000:
            return f"${p:,.0f}"
        return f"${p:.2f}"

    return {
        "asset": asset,
        "direction": direction,
        "action": sig_action,
        "entry": fmt(entry),
        "entryRaw": entry,
        "target": fmt(target),
        "targetRaw": target,
        "invalidation": fmt(invalidation),
        "invalidationRaw": invalidation,
        "expectedMove": f"{'+' if expected_move > 0 else ''}{expected_move}%",
        "expectedMoveRaw": expected_move,
        "rr": f"{rr}:1" if rr > 0 else "—",
        "rrRaw": rr,
        "latePenalty": f"Late entry = worse price by ~{late_penalty}%" if late_penalty > 1 else "",
        "confirmed": trade.get("confirmed", False),
        "tf": timeframe["tf"],
        "hold": timeframe["hold"],
        "tfLabel": timeframe["label"],
    }


# ═══════════════════════════════════════════
#  CONVICTION — One line that locks decision
# ═══════════════════════════════════════════

def _conviction(archetype: str, snapshot: dict, edge: float) -> str:
    fg = snapshot.get("drivers", {}).get("sentiment", {}).get("fearGreed", 50)
    if archetype == "TRAP":
        return "Overcrowded trade. Exit door is narrow."
    if archetype == "SMART_MONEY":
        if fg <= 30:
            return "Crowd sells. Money buys. Same pattern."
        return "Money moves first. Crowd follows."
    if archetype == "CONTRARIAN":
        return f"Market is off by {abs(round(edge))}%. These gaps close."
    return "Not obvious yet. That's the point."


# ═══════════════════════════════════════════
#  DANGER
# ═══════════════════════════════════════════

_DANGER = {
    "TRAP": [
        "After this — you become the liquidity.",
        "Soon you'll be the exit for others.",
    ],
    "CONTRARIAN": [
        "In 48h this becomes consensus. By then — priced in.",
        "Later you'll chase what's already obvious.",
    ],
    "EARLY": [
        "This window doesn't reopen.",
        "Later you'll wish you saw this earlier.",
    ],
    "SMART_MONEY": [
        "Retail is always last to know.",
        "The money already decided. Have you?",
    ],
}


def _danger(archetype: str) -> str:
    return random.choice(_DANGER.get(archetype, _DANGER["EARLY"]))


# ═══════════════════════════════════════════
#  IDENTITY + URGENCY + MICRO-DYNAMIC + CTA + TRUTH
# ═══════════════════════════════════════════

_IDENTITY = [
    "You see this before others.",
    "Most will understand this later.",
    "You're early. That's the edge.",
]

_CTA = {
    "CONTRARIAN": ["Go against the crowd", "Fade the consensus", "Take the other side"],
    "EARLY": ["Enter before the move", "Get in early", "Position before it's obvious"],
    "TRAP": ["Exit while you can", "Don't be the exit liquidity", "Reduce before the drop"],
    "SMART_MONEY": ["Follow the money", "Align with smart money", "Do what they do"],
}

_TRUTH = {
    "CONTRARIAN": ["Markets reward the early. Not the obvious.", "The minority wins. Always."],
    "EARLY": ["The first ones in set the price.", "See first. Act first. Win first."],
    "TRAP": ["Euphoria is the most expensive emotion.", "Last ones in pay the most."],
    "SMART_MONEY": ["Money talks. Everything else is noise.", "Follow capital, not opinions."],
}


def _urgency(edge: float) -> str:
    ae = abs(edge)
    if ae > 30:
        return "Gap closing. After the move — too late."
    if ae > 20:
        return "Happening now. In 24h everyone sees it."
    if ae > 10:
        return "Window open. Early movers positioning."
    return ""


def _micro_dynamic(archetype: str, snapshot: dict, edge: float) -> str:
    fg = snapshot.get("drivers", {}).get("sentiment", {}).get("fearGreed", 50)
    social = snapshot.get("drivers", {}).get("social", {})
    if archetype == "TRAP" and fg >= 70:
        return "Confidence peaking..."
    if archetype == "SMART_MONEY" and fg <= 30:
        return "Capital accumulating..."
    if social.get("confidence", 0) > 0.4:
        return "Attention accelerating..."
    if abs(edge) > 25:
        return "Edge shrinking..."
    if abs(edge) > 15:
        return "Gap narrowing..."
    return ""


def _edge_verdict(edge: float) -> str:
    ae = abs(round(edge))
    if ae > 30:
        return f"Market error: {ae}%"
    if ae > 20:
        return f"Mispriced by {ae}%"
    if ae > 10:
        return f"{ae}% early edge"
    return f"{ae}% gap"


# ═══════════════════════════════════════════
#  BUILD COMPLETE INTELLIGENCE
# ═══════════════════════════════════════════

def build_feed_intelligence(asset: str = "BTC") -> dict:
    from services.meta_brain_service import build_snapshot
    from services.feed_service import get_feed
    from services.alt_engine import discover_alt_opportunities, build_rotation_block
    from services.portfolio_builder import build_portfolio

    snapshot = build_snapshot(asset)
    raw_feed = get_feed(asset)
    polymarkets = [f for f in raw_feed if f.get("type") == "polymarket" and f.get("market")]

    mispricing_cards = []
    undervalued_cards = []
    developing_cards = []

    for pm in polymarkets:
        m = pm["market"]
        edge = m.get("edge", 0)
        mkt_prob = round(m.get("yesPrice", 0) * 100)
        mdl_prob = round(m.get("fairProb", 0))
        abs_edge = abs(edge)

        archetype = _detect_archetype(snapshot, edge, mkt_prob)
        trade_setup = _build_trade_setup(snapshot, edge, asset)
        timeframe = _get_timeframe(snapshot, edge)

        card = {
            "id": pm["id"],
            "asset": pm.get("asset", asset),
            "title": pm.get("title", ""),
            "marketProb": mkt_prob,
            "modelProb": mdl_prob,
            "edge": round(edge),
            "impact": pm.get("affectsSignal", "neutral"),
            "volume": m.get("volume", 0),

            "archetype": archetype,
            "headline": _headline(archetype, asset, mkt_prob),
            "crowd": _crowd(mkt_prob),
            "reality": _reality(snapshot),
            "tradeSetup": trade_setup,
            "timeframe": timeframe,
            "conviction": _conviction(archetype, snapshot, edge),
            "danger": _danger(archetype),
            "identity": random.choice(_IDENTITY),
            "microDynamic": _micro_dynamic(archetype, snapshot, edge),
            "cta": random.choice(_CTA.get(archetype, _CTA["EARLY"])),
            "urgency": _urgency(edge),
            "urgencyLevel": "high" if abs_edge > 25 else "medium" if abs_edge > 10 else "low",
            "edgeVerdict": _edge_verdict(edge),
            "truth": random.choice(_TRUTH.get(archetype, _TRUTH["EARLY"])),
            "timestamp": pm.get("timestamp", ""),
        }

        if abs_edge > 25:
            card["type"] = "mispricing"
            mispricing_cards.append(card)
        elif abs_edge > 10:
            card["type"] = "undervalued"
            undervalued_cards.append(card)
        else:
            card["type"] = "developing"
            developing_cards.append(card)

    mispricing_cards.sort(key=lambda c: -abs(c["edge"]))
    undervalued_cards.sort(key=lambda c: -abs(c["edge"]))

    # ── DEDUP: Keep only strongest card per archetype ──
    def dedup_cards(cards, limit):
        seen_archetypes = set()
        result = []
        for c in cards:
            arch = c.get("archetype", "EARLY")
            if arch not in seen_archetypes:
                result.append(c)
                seen_archetypes.add(arch)
            if len(result) >= limit:
                break
        return result

    mispricing_cards = dedup_cards(mispricing_cards, 1)
    undervalued_cards = dedup_cards(undervalued_cards, 2)

    blindspots = _build_blindspots(snapshot, asset)

    supports = sum(1 for pm in polymarkets if pm.get("affectsSignal") == "supports")
    weakens = sum(1 for pm in polymarkets if pm.get("affectsSignal") == "weakens")

    # ── ALT ENGINE ──
    alt_opportunities = []
    rotation = None
    try:
        alt_scores = discover_alt_opportunities(snapshot)
        rotation = build_rotation_block(snapshot, alt_scores)

        # Build alt narrative cards
        for alt in alt_scores:
            alt_arch = alt["archetype"]
            alt_asset = alt["asset"]
            # Build reality from ALT's own snapshot data (real data, not BTC)
            try:
                alt_snap = build_snapshot(alt_asset)
                alt_reality = _reality(alt_snap)
            except Exception:
                alt_reality = ["Signal detected. Check details."]

            alt_headline = _headline(alt_arch, alt_asset, 50)

            alt_card = {
                "id": f"alt_{alt_asset}",
                "asset": alt_asset,
                "type": "alt",
                "archetype": alt_arch,
                "headline": alt_headline,
                "crowd": f'"BTC dominates attention"',
                "reality": alt_reality,
                "tradeSetup": alt["tradeSetup"],
                "conviction": alt["whyNotBtc"],
                "danger": _danger(alt_arch),
                "identity": random.choice(_IDENTITY),
                "microDynamic": "Attention accelerating..." if alt["drivers"]["socialConf"] > 0.3 else "Capital shifting...",
                "cta": random.choice(_CTA.get(alt_arch, _CTA["EARLY"])),
                "urgency": "",
                "urgencyLevel": "medium" if alt["score"] > 0.3 else "low",
                "edgeVerdict": f"Score: {alt['score']:.0%}",
                "truth": random.choice(_TRUTH.get(alt_arch, _TRUTH["EARLY"])),
                "score": alt["score"],
                "edge": 10 if alt["tradeSetup"]["direction"] == "LONG" else -10,
                "btcDivergence": alt["btcDivergence"],
                "whyNotBtc": alt["whyNotBtc"],
            }
            alt_opportunities.append(alt_card)
    except Exception as e:
        logger.warning(f"Alt engine failed: {e}")

    # ── PORTFOLIO ──
    portfolio = None
    try:
        btc_hero = mispricing_cards[0] if mispricing_cards else (undervalued_cards[0] if undervalued_cards else None)
        if btc_hero and alt_opportunities:
            portfolio = build_portfolio(btc_hero, alt_opportunities)
    except Exception as e:
        logger.warning(f"Portfolio build failed: {e}")

    total = len(mispricing_cards) + len(undervalued_cards) + len(blindspots) + len(developing_cards) + len(alt_opportunities)

    return {
        "ok": True,
        "asset": asset,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signalImpact": {
            "supports": supports,
            "weakens": weakens,
            "net": supports - weakens,
            "verdict": "bullish" if supports > weakens else "bearish" if weakens > supports else "neutral",
        },
        "mispricing": mispricing_cards[:3],
        "undervalued": undervalued_cards[:4],
        "blindspots": blindspots[:3],
        "developing": developing_cards[:3],
        "altOpportunities": alt_opportunities[:3],
        "rotation": rotation,
        "portfolio": portfolio,
        "totalCards": total,
    }


def _build_blindspots(snapshot: dict, asset: str) -> list:
    blindspots = []
    drivers = snapshot.get("drivers", {})
    fg = drivers.get("sentiment", {}).get("fearGreed", 50)
    sig_action = snapshot.get("signal", {}).get("action", "WAIT")
    trade_setup = _build_trade_setup(snapshot, 20 if sig_action == "BUY" else -20, asset)

    if fg <= 25 and sig_action == "BUY":
        blindspots.append({
            "id": "blindspot_fear_buy", "type": "blindspot", "asset": asset,
            "archetype": "SMART_MONEY",
            "headline": f"{asset} in extreme fear.\nSignal says: buy.",
            "crowd": '"Market expects decline"',
            "reality": ["Fear = bottom. Every time.", "Accumulation already started.", "This is how rallies begin."],
            "tradeSetup": trade_setup,
            "conviction": "Crowd sells. Money buys. Same pattern.",
            "danger": "Retail is always last to know.",
            "identity": "You see the setup. They see the fear.",
            "microDynamic": "Capital accumulating...",
            "cta": "Enter before the reversal",
            "urgency": "Fear doesn't last. Window closing.",
            "urgencyLevel": "medium",
            "edgeVerdict": "Sentiment divergence",
            "truth": "The crowd sells at the bottom. Every time.",
        })

    if fg >= 75 and sig_action == "SELL":
        blindspots.append({
            "id": "blindspot_greed_sell", "type": "blindspot", "asset": asset,
            "archetype": "TRAP",
            "headline": f"{asset} in euphoria.\nSignal says: exit.",
            "crowd": '"Market expects more growth"',
            "reality": ["Euphoria at peak. Last time — reversal.", "Distribution active. Big players exiting.", "Crowd is last to know."],
            "tradeSetup": trade_setup,
            "conviction": "When all are confident — smart money is out.",
            "danger": "Soon you'll be the exit for others.",
            "identity": "Most will realize this too late.",
            "microDynamic": "Confidence peaking...",
            "cta": "Reduce exposure now",
            "urgency": "Euphoria peaks are brief.",
            "urgencyLevel": "high",
            "edgeVerdict": "Sentiment top",
            "truth": "Euphoria is the most expensive emotion.",
        })

    social = drivers.get("social", {})
    if social.get("direction") == "Bullish" and social.get("confidence", 0) > 0.5:
        blindspots.append({
            "id": "blindspot_social", "type": "blindspot", "asset": asset,
            "archetype": "EARLY",
            "headline": f"{asset}: Attention spiking.\nPrice hasn't moved.",
            "crowd": '"Market hasn\'t priced this in"',
            "reality": ["Influencers already in.", "Engagement accelerating.", "Price still flat."],
            "tradeSetup": trade_setup,
            "conviction": "First attention. Then volume. Then move.",
            "danger": "This window doesn't reopen.",
            "identity": "You still have time. Barely.",
            "microDynamic": "Attention accelerating...",
            "cta": "Enter before price reacts",
            "urgency": "Attention-price gap closes fast.",
            "urgencyLevel": "medium",
            "edgeVerdict": "Social-price gap",
            "truth": "See first. Act first. Win first.",
        })

    return blindspots
