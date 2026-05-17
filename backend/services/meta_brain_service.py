"""
Meta Brain Service — Single Source of Truth.

Aggregates ALL modules into ONE unified snapshot.
Mobile + Web consume the SAME output.

Snapshot = Signal + Edge + Drivers + Mispricing + Context + Trade Setup
"""

import os
import logging
import time
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
from threading import Lock

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]
ie_db = client["intelligence_engine"]

# ─── CACHE ───
_cache: dict[str, dict] = {}
_cache_ts: dict[str, float] = {}
_lock = Lock()
CACHE_TTL = 30  # seconds


def build_snapshot(asset: str = "BTC") -> dict:
    """
    Build a unified brain snapshot for the given asset.
    This is THE SINGLE SOURCE OF TRUTH for Mobile + Web.
    """
    now = datetime.now(timezone.utc)

    # Check cache
    with _lock:
        if asset in _cache and (time.time() - _cache_ts.get(asset, 0)) < CACHE_TTL:
            return _cache[asset]

    # ─── 1. SIGNAL (Decision Engine) ───
    from services.signals_service import generate_signal, get_market_state
    sig = generate_signal(asset)
    market = get_market_state()

    # ─── 2. DRIVERS (deep data from each module) ───
    drivers = {}
    for d in sig.get("drivers", []):
        mod = d.get("module", d.get("name", "")).lower()
        drivers[mod] = {
            "name": d.get("name", mod),
            "direction": d.get("direction", "Neutral"),
            "confidence": d.get("confidence", 0),
            "weight": d.get("weight", 0),
            "value": d.get("value", ""),
            "reason": d.get("reason", ""),
        }

    # ─── 3. ENRICHED DRIVER DATA ───

    # Sentiment (real Fear & Greed + community)
    fg_event = db.sentiment_events.find_one(
        {"sourceType": "fear_greed"}, {"_id": 0},
        sort=[("timestamp", DESCENDING)]
    )
    fg_value = fg_event.get("raw", {}).get("value", 50) if fg_event else 50
    fg_class = fg_event.get("raw", {}).get("classification", "Neutral") if fg_event else "Neutral"

    if "sentiment" in drivers:
        drivers["sentiment"]["fearGreed"] = fg_value
        drivers["sentiment"]["fearGreedClass"] = fg_class
        drivers["sentiment"]["interpretation"] = (
            f"Extreme fear ({fg_value}) → contrarian buy zone" if fg_value <= 20
            else f"Extreme greed ({fg_value}) → distribution risk" if fg_value >= 80
            else f"Neutral ({fg_value})"
        )

    # OnChain (real Infura data)
    # ─── OnChain Guard (Task 4 · 2026-05-12) ───────────────────────────
    # Master switch. When ONCHAIN_ENABLED=false (default), skip enrichment
    # completely. No HTTP call, no retry, no log spam. The composer reads
    # the absence as honest "module not contributing" — Truthful Degradation
    # applied to data sources.
    if os.environ.get("ONCHAIN_ENABLED", "false").strip().lower() not in ("1", "true", "yes", "on"):
        # Honest degraded driver, surfaced once at debug level only.
        if "onchain" not in drivers:
            drivers["onchain"] = {
                "name": "On-Chain",
                "direction": "Neutral",
                "confidence": 0.0,
                "weight": 0.0,
                "degraded": True,
                "reason": "onchain_disabled",
            }
        else:
            drivers["onchain"]["degraded"] = True
            drivers["onchain"]["reason"] = "onchain_disabled"
    else:
        try:
            import httpx
            oc_resp = httpx.get("http://127.0.0.1:8001/api/onchain/summary", timeout=5).json()
            oc = oc_resp.get("data", {})
            if "onchain" not in drivers:
                drivers["onchain"] = {"name": "On-Chain", "direction": "Neutral", "confidence": 0.3, "weight": 0.1}
            drivers["onchain"]["blockHeight"] = oc.get("blockHeight", 0)
            drivers["onchain"]["gasPrice"] = oc.get("gasPrice", 0)
            drivers["onchain"]["stablecoinNetflow"] = oc.get("stablecoinNetflow24h", 0)
            inflow = oc.get("stablecoinNetflow24h", 0)
            if inflow and inflow > 10_000_000:
                drivers["onchain"]["interpretation"] = f"Stablecoin inflow +${inflow/1e6:.0f}M → buying pressure"
                drivers["onchain"]["direction"] = "Bullish"
            elif inflow and inflow < -10_000_000:
                drivers["onchain"]["interpretation"] = f"Stablecoin outflow ${inflow/1e6:.0f}M → selling pressure"
                drivers["onchain"]["direction"] = "Bearish"
            else:
                drivers["onchain"]["interpretation"] = "Neutral on-chain flows"
        except Exception as e:
            logger.warning(f"OnChain enrichment failed: {e}")

    # Fractal (real forecasts)
    try:
        fractal_rows = list(db.fractal_forecasts.find(
            {"scope": asset.upper()}, {"_id": 0}
        ).sort("createdAt", DESCENDING).limit(5))
        if fractal_rows and "fractal" in drivers:
            short = next((r for r in fractal_rows if "90" in str(r.get("horizon", ""))), None)
            if short:
                drivers["fractal"]["forecast"] = f"{short.get('horizon')}: {short.get('direction')} ({short.get('confidence', 0):.0%})"
                drivers["fractal"]["interpretation"] = f"Fractal {short.get('direction', 'NEUTRAL')} on 90D with {short.get('confidence', 0):.0%} confidence"
    except Exception as e:
        logger.warning(f"Fractal enrichment failed: {e}")

    # Prediction (Polymarket mispricing)
    mispricing_list = []
    try:
        from services.feed_service import get_feed
        feed = get_feed(asset)
        polymarkets = [f for f in feed if f.get("type") == "polymarket" and f.get("market")]
        for pm in polymarkets:
            m = pm["market"]
            if abs(m.get("edge", 0)) > 15:
                mispricing_list.append({
                    "title": pm["title"],
                    "marketProb": round(m.get("yesPrice", 0) * 100),
                    "modelProb": round(m.get("fairProb", 0)),
                    "edge": round(m.get("edge", 0)),
                    "impact": pm.get("affectsSignal", "neutral"),
                })
        # Enrich prediction driver
        if "prediction" in drivers and mispricing_list:
            top = mispricing_list[0]
            drivers["prediction"]["topMispricing"] = top
            drivers["prediction"]["interpretation"] = f"Market mispriced by {top['edge']:+d}% → {top['impact']}"
    except Exception as e:
        logger.warning(f"Prediction enrichment failed: {e}")

    # ─── 4. EDGE ───
    from services.edge_opportunities import generate_edge_opportunities
    edges = generate_edge_opportunities(asset)
    top_edge = edges[0] if edges else None
    edge_data = {
        "formation": top_edge["confidence"] / 100 if top_edge else 0,
        "stage": "pre_signal" if top_edge else "none",
        "opportunity": bool(top_edge),
        "timing": top_edge.get("timing", "—") if top_edge else "—",
        "title": top_edge.get("title", "") if top_edge else "",
        "count": len(edges),
    }

    # ─── 5. TRADE SETUP ───
    trade = {
        "entry": sig.get("entryZone"),
        "invalidation": sig.get("stopLoss"),
        "target": sig.get("takeProfit"),
        "confirmed": bool(sig.get("entryZone")),
    }

    # ─── 6. CONTEXT ───
    context = {
        "fearGreed": fg_value,
        "fearGreedClass": fg_class,
        "regime": market.get("market", "NEUTRAL"),
        "bias": market.get("bias", "Neutral"),
    }

    # ─── ASSEMBLE SNAPSHOT ───
    snapshot = {
        "ok": True,
        "asset": asset.upper(),
        "timestamp": now.isoformat(),

        # Final decision
        "signal": {
            "action": sig.get("action", "WAIT"),
            "confidence": sig.get("confidence", 0),
            "score": sig.get("score", 0),
            "direction": sig.get("direction", "neutral"),
            "horizon": sig.get("horizon", "swing"),
            "summary": sig.get("summary", ""),
            "alignment": sig.get("driverSummary", {}),
        },

        # Edge layer
        "edge": edge_data,

        # All drivers
        "drivers": drivers,

        # Mispricing feed
        "mispricing": mispricing_list[:5],

        # Market context
        "context": context,

        # Trade setup
        "trade": trade,

        # Price
        "price": sig.get("price", 0),

        # Updated at
        "updatedAt": sig.get("updatedAt", now.isoformat()),
    }

    # Cache
    with _lock:
        _cache[asset] = snapshot
        _cache_ts[asset] = time.time()

    return snapshot


def invalidate_cache(asset: str = None):
    """Clear cache for an asset or all."""
    with _lock:
        if asset:
            _cache.pop(asset, None)
            _cache_ts.pop(asset, None)
        else:
            _cache.clear()
            _cache_ts.clear()


# ═══════════════════════════════════════════════════════════════════
# HORIZON FORECASTS — MetaBrain-adjusted per-horizon outlook
# ═══════════════════════════════════════════════════════════════════
# These are NOT raw fractal forecasts. They are MetaBrain-synthesized:
# raw fractal per-horizon is ONE input; exchange/sentiment/onchain/prediction
# from the Brain snapshot contribute weighted bias adjustments that scale
# with horizon (short-term more sensitive to flow/sentiment, long-term more
# sensitive to fractal/regime).
# ═══════════════════════════════════════════════════════════════════
HORIZON_DAYS = {'7D': 7, '30D': 30, '90D': 90, '180D': 180, '365D': 365}
_HORIZON_LIST = ['7D', '30D', '90D', '180D', '365D']

# How much short-term Brain drivers (exchange/sentiment/onchain) influence
# each horizon. Longer horizon → fractal/MB-synthesis dominate.
_HORIZON_SHORT_WEIGHT = {'7D': 0.65, '30D': 0.5, '90D': 0.35, '180D': 0.2, '365D': 0.15}


def _dir_num(direction: str) -> float:
    """'Bullish'→1, 'Bearish'→-1, else 0."""
    d = (direction or '').strip()
    if d == 'Bullish':
        return 1.0
    if d == 'Bearish':
        return -1.0
    return 0.0


def build_horizon_forecasts(asset: str = 'BTC') -> dict:
    """
    MetaBrain-adjusted per-horizon forecasts.

    This is the SINGLE SOURCE OF TRUTH for the BTC Prediction screen's
    per-horizon bias / confidence / expectedReturn / target. Every horizon's
    direction is a MetaBrain synthesis, not a raw fractal number.

    RULES:
    - MetaBrain driver is NOT used as an input (no recursion: MB inside MB).
    - Prediction-markets driver is capped per horizon (context, not leader).
    - Output carries both confidence (module agreement) AND conviction
      (absolute signal strength even when conflicted).
    """
    asset = (asset or 'BTC').upper()
    snapshot = build_snapshot(asset)

    drivers = snapshot.get('drivers', {}) or {}
    signal = snapshot.get('signal', {}) or {}
    context = snapshot.get('context', {}) or {}
    current_price = float(snapshot.get('price', 0) or 0)

    # MetaBrain global score from the unified signal (observation only,
    # NOT fed back into horizon synthesis).
    mb_confidence = float(signal.get('confidence', 0) or 0)  # 0..1
    mb_dir_num = 1.0 if signal.get('direction') == 'bullish' else (-1.0 if signal.get('direction') == 'bearish' else 0.0)

    # Prediction-markets cap per horizon (never a leader — context layer only).
    _PRED_CAP = {'7D': 0.05, '30D': 0.10, '90D': 0.15, '180D': 0.20, '365D': 0.20}

    # Short-term bias = flow-layer drivers (exchange / sentiment / onchain)
    st_score, st_weight = 0.0, 0.0
    st_dirs = []
    for mod in ('exchange', 'sentiment', 'onchain'):
        d = drivers.get(mod, {})
        if not d:
            continue
        dn = _dir_num(d.get('direction', 'Neutral'))
        c = float(d.get('confidence', 0) or 0)
        w = float(d.get('weight', 0) or 0)
        if w > 0:
            st_score += dn * c * w
            st_weight += w
            st_dirs.append(dn)
    st_bias = (st_score / st_weight) if st_weight > 0 else 0.0  # -1..1

    # Long-term structural bias — fractal + prediction-markets (CAPPED).
    # DELIBERATELY EXCLUDES 'metabrain' driver to avoid MB-in-MB recursion.
    lt_score, lt_weight = 0.0, 0.0
    lt_dirs = []
    # Fractal participates fully
    fd = drivers.get('fractal', {}) or {}
    if fd:
        dn = _dir_num(fd.get('direction', 'Neutral'))
        c = float(fd.get('confidence', 0) or 0)
        w = float(fd.get('weight', 0) or 0)
        if w > 0:
            lt_score += dn * c * w
            lt_weight += w
            lt_dirs.append(dn)

    # Raw per-horizon fractal forecasts (target hints, not brain)
    try:
        raw_forecasts = {}
        for f in db.btc_fractal_forecasts.find(
            {'resolved': {'$ne': True}}, {'_id': 0}
        ).sort([('createdAt', DESCENDING)]):
            h = f.get('horizon', '')
            if h and h not in raw_forecasts:
                raw_forecasts[h] = f
    except Exception as e:
        logger.warning(f'horizon raw fetch failed: {e}')
        raw_forecasts = {}

    # Prediction-markets (capped, applied per-horizon below)
    pd = drivers.get('prediction', {}) or {}
    pd_dn = _dir_num(pd.get('direction', 'Neutral')) if pd else 0.0
    pd_conf = float(pd.get('confidence', 0) or 0) if pd else 0.0

    horizons = {}
    for h in _HORIZON_LIST:
        raw = raw_forecasts.get(h, {})
        raw_dir_str = (raw.get('direction', 'NEUTRAL') or 'NEUTRAL').upper()
        raw_conf = float(raw.get('confidence', 0) or 0)
        raw_ret = float(raw.get('expectedReturn', 0) or 0)
        raw_dir_num = 1.0 if raw_dir_str in ('UP', 'BULLISH') else (-1.0 if raw_dir_str in ('DOWN', 'BEARISH') else 0.0)

        # Blended weights
        sw = _HORIZON_SHORT_WEIGHT[h]
        lw = 1.0 - sw
        pred_cap = _PRED_CAP[h]

        # Structural bias for this horizon = fractal aggregate + prediction-markets (capped)
        lt_bias_h = (lt_score / lt_weight) if lt_weight > 0 else 0.0
        # Apply prediction-markets as a capped context layer on structure
        struct_bias = lt_bias_h * (1 - pred_cap) + pd_dn * pd_conf * pred_cap

        # Raw fractal per-horizon forecast contributes within structure too
        raw_contribution = raw_dir_num * raw_conf * 0.4
        struct_bias = struct_bias * 0.6 + raw_contribution * 0.4

        # Final blended bias: flow + structure
        mb_bias = st_bias * sw + struct_bias * lw

        # ─── CONFIDENCE = module AGREEMENT (consensus) ────────────────
        # High when drivers point the same way; low when they conflict.
        all_dirs = st_dirs + lt_dirs
        if pd_conf > 0:
            all_dirs.append(pd_dn)
        if raw_conf > 0.1:
            all_dirs.append(raw_dir_num)
        if all_dirs:
            bullish_cnt = sum(1 for x in all_dirs if x > 0)
            bearish_cnt = sum(1 for x in all_dirs if x < 0)
            total = len(all_dirs)
            agreement = max(bullish_cnt, bearish_cnt) / total if total else 0  # 0..1
        else:
            agreement = 0

        confidence_val = max(0.15, min(0.95, agreement * 0.85 + abs(mb_bias) * 0.2))

        # ─── CONVICTION = signal STRENGTH (independent of conflict) ───
        # Sum of absolute contributions regardless of sign; captures energy.
        conviction_raw = 0.0
        conviction_weight = 0.0
        for mod in ('exchange', 'sentiment', 'onchain', 'fractal'):
            dd = drivers.get(mod, {})
            if not dd:
                continue
            cc = float(dd.get('confidence', 0) or 0)
            ww = float(dd.get('weight', 0) or 0)
            conviction_raw += cc * ww
            conviction_weight += ww
        if raw_conf > 0:
            conviction_raw += raw_conf * 0.3
            conviction_weight += 0.3
        conviction_val = (conviction_raw / conviction_weight) if conviction_weight > 0 else 0.3
        conviction_val = max(0.10, min(0.95, conviction_val))

        # Final direction with hysteresis
        if mb_bias > 0.18:
            final_dir = 'BULLISH'
        elif mb_bias < -0.18:
            final_dir = 'BEARISH'
        else:
            final_dir = 'NEUTRAL'

        # Expected return: horizon-scaled magnitude
        if final_dir == 'NEUTRAL':
            final_ret = 0.0
        else:
            sign = 1.0 if final_dir == 'BULLISH' else -1.0
            h_magnitude = {'7D': 0.03, '30D': 0.08, '90D': 0.15, '180D': 0.22, '365D': 0.35}[h]
            final_ret = sign * max(abs(raw_ret), h_magnitude * confidence_val * abs(mb_bias))

        # Target price
        raw_target = float(raw.get('targetPrice', 0) or 0)
        target_price = 0.0
        if raw_target > 0 and current_price > 0:
            raw_implies_up = raw_target > current_price
            final_up = final_dir == 'BULLISH'
            if final_dir != 'NEUTRAL' and raw_implies_up == final_up:
                target_price = raw_target
        if target_price <= 0 and current_price > 0:
            target_price = round(current_price * (1 + final_ret), 2)

        # ─── CONFLICT DETECTION — agreement-based (authoritative) ───────
        # A conflict exists when modules don't agree, regardless of which
        # side "won" the count. This is the key signal: low agreement itself
        # IS a conflict, even if no module is actively bearish.
        conflict_from_split = len(bullish_drivers := [
            d.get('name', k) for k, d in drivers.items()
            if k != 'metabrain' and _dir_num(d.get('direction', 'Neutral')) > 0
        ]) >= 1 and len([
            d.get('name', k) for k, d in drivers.items()
            if k != 'metabrain' and _dir_num(d.get('direction', 'Neutral')) < 0
        ]) >= 1
        bearish_drivers = [d.get('name', k) for k, d in drivers.items()
                           if k != 'metabrain' and _dir_num(d.get('direction', 'Neutral')) < 0]
        conflict_from_agreement = agreement < 0.4
        has_conflict = conflict_from_split or conflict_from_agreement

        # ─── MARKET STATE ENGINE (3rd-layer classifier) ─────────────────
        # Synthesizes agreement + conviction + direction into a discrete
        # market regime understandable by the user in one word.
        if conviction_val >= 0.6 and agreement >= 0.7:
            market_state = 'ALIGNED'
            state_color = 'green' if final_dir == 'BULLISH' else ('red' if final_dir == 'BEARISH' else 'gray')
            state_text = f'Model aligned — {final_dir.lower()} pressure building'
        elif conviction_val >= 0.5 and agreement < 0.4:
            market_state = 'TENSION'
            state_color = 'gold'
            state_text = 'Unclear direction, but pressure building — reversal zone likely'
        elif agreement < 0.4 and conviction_val < 0.5:
            market_state = 'CONFLICT'
            state_color = 'gold'
            state_text = 'Modules disagree — market is indecisive'
        elif agreement >= 0.7 and conviction_val < 0.35:
            market_state = 'CALM'
            state_color = 'gray'
            state_text = 'Low volatility — system watching'
        elif conviction_val >= 0.55 and final_dir != 'NEUTRAL':
            market_state = 'BREAKOUT_FORMING'
            state_color = 'green' if final_dir == 'BULLISH' else 'red'
            state_text = f'{final_dir.title()} breakout forming — early signal'
        else:
            market_state = 'SCANNING'
            state_color = 'gray'
            state_text = 'System scanning — awaiting convergence'

        # Conviction / agreement labels (human language)
        def _label(v: float, lo: float, hi: float) -> str:
            if v < lo:
                return 'LOW'
            if v >= hi:
                return 'HIGH'
            return 'MEDIUM'
        conviction_label = _label(conviction_val, 0.30, 0.60)
        agreement_label = _label(agreement, 0.40, 0.70)

        # ─── ACTION VERB (state → actionable instruction) ───────────────
        action_verbs = {
            'ALIGNED': ('ACT', 'Entry window open — model and market aligned'),
            'TENSION': ('GET READY', 'Pressure building — prepare for breakout'),
            'CONFLICT': ('PREPARE', 'Market on the edge — reversal zone forming'),
            'BREAKOUT_FORMING': ('ACT EARLY', 'Early signal — directional move starting'),
            'CALM': ('WATCH', 'Low volatility — no edge yet'),
            'SCANNING': ('WAIT', 'System still gathering data'),
        }
        action_verb, action_hint = action_verbs.get(market_state, ('WATCH', 'Monitor next updates'))

        horizons[h] = {
            'horizon': h,
            'days': HORIZON_DAYS[h],
            'direction': final_dir,
            'confidence': round(confidence_val, 3),
            'conviction': round(conviction_val, 3),
            'agreement': round(agreement, 3),
            'convictionLabel': conviction_label,
            'agreementLabel': agreement_label,
            'expectedReturn': round(final_ret, 4),
            'targetPrice': round(target_price, 2) if target_price else 0.0,
            'entryPrice': float(raw.get('entryPrice', current_price) or current_price),
            'source': 'METABRAIN',
            'marketState': market_state,            # NEW — state engine
            'marketStateText': state_text,          # NEW — narrative
            'marketStateColor': state_color,        # NEW — ui hint
            'actionVerb': action_verb,              # NEW — ACT / GET READY / PREPARE / WAIT / WATCH
            'actionHint': action_hint,              # NEW — single-sentence instruction
            'metabrain': {
                'rawDirection': raw_dir_str,
                'rawConfidence': round(raw_conf, 3),
                'shortTermBias': round(st_bias, 3),
                'longTermBias': round(lt_bias_h, 3),
                'structuralBias': round(struct_bias, 3),
                'blendedBias': round(mb_bias, 3),
                'shortWeight': sw,
                'predictionMarketsCap': pred_cap,
                'globalConfidence': round(mb_confidence, 3),
                'regime': context.get('regime', 'NEUTRAL'),
                'excludesMetabrainDriver': True,
                'hasConflict': has_conflict,
                'conflictFromSplit': conflict_from_split,
                'conflictFromAgreement': conflict_from_agreement,
                'bullishDrivers': bullish_drivers,
                'bearishDrivers': bearish_drivers,
                'marketState': market_state,
                'stateText': state_text,
            },
        }

    return {
        'asset': asset,
        'source': 'METABRAIN',
        'currentPrice': current_price,
        'globalSignal': {
            'action': signal.get('action', 'WAIT'),
            'direction': signal.get('direction', 'neutral'),
            'confidence': mb_confidence,
            'score': float(signal.get('score', 0) or 0),
            'summary': signal.get('summary', ''),
            'alignment': signal.get('alignment', {}),
        },
        'regime': context.get('regime', 'NEUTRAL'),
        'horizons': horizons,
        'drivers': drivers,
        'edge': snapshot.get('edge', {}),
        'updatedAt': snapshot.get('updatedAt'),
    }
