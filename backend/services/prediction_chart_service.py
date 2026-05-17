"""
BTC Prediction Presentation Service
=====================================
THIN ADAPTER. Not a brain. Not an aggregator.

SINGLE SOURCE OF TRUTH:
  services.meta_brain_service.build_snapshot(asset)          ← Unified brain
  services.meta_brain_service.build_horizon_forecasts(asset) ← MB per-horizon

Raw collections (fractal_canonical_ohlcv, btc_fractal_forecasts,
exchange_observations, fractal_state) are used ONLY for:
  - Historical OHLCV chart geometry (it's a visualization input, not a brain)
  - Historical forecast accuracy / truth layer (it's an audit trail)

Bias / confidence / direction / scenarios / regime / summary / drivers
are ALWAYS sourced from MetaBrain.

Output:
  GET /api/mobile/prediction-chart?symbol=BTC&horizon=30D
"""
import os
import math
import logging
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'fomo_mobile')
_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]

HORIZONS = ['7D', '30D', '90D', '180D', '365D']
HORIZON_DAYS = {'7D': 7, '30D': 30, '90D': 90, '180D': 180, '365D': 365}
HISTORY_DAYS = {'7D': 30, '30D': 90, '90D': 180, '180D': 365, '365D': 730}
REFRESH_HOURS = {'7D': 3, '30D': 6, '90D': 12, '180D': 24, '365D': 24}


# ───────────────────────────────────────────────────────────
# Historical price series (OHLCV visualization input — not brain)
# ───────────────────────────────────────────────────────────
def _get_price_series(days_back: int = 90) -> list:
    """Historical BTC price series from OHLCV candles."""
    candles = list(_db.fractal_canonical_ohlcv.find(
        {'meta.symbol': 'BTC', 'ohlcv.c': {'$gt': 0}},
        {'_id': 0, 'ts': 1, 'ohlcv.c': 1}
    ).sort([('ts', -1)]).limit(days_back))
    series = []
    for c in reversed(candles):
        ts = c.get('ts')
        if ts:
            series.append({
                't': ts.strftime('%Y-%m-%d') if isinstance(ts, datetime) else str(ts)[:10],
                'v': round(c['ohlcv']['c'], 2),
            })
    return series


# ───────────────────────────────────────────────────────────
# Projection geometry — driven by MetaBrain horizon forecast
# ───────────────────────────────────────────────────────────
def _build_projection_from_mb(current_price: float, mb_horizon: dict, horizon_days: int) -> dict:
    """
    Build projected price path and uncertainty bands from a MetaBrain
    horizon forecast (NOT from raw fractal). `mb_horizon` comes from
    meta_brain_service.build_horizon_forecasts.
    """
    direction = (mb_horizon.get('direction', 'NEUTRAL') or 'NEUTRAL').upper()
    expected_return = float(mb_horizon.get('expectedReturn', 0) or 0)
    confidence = float(mb_horizon.get('confidence', 0.3) or 0.3)
    target = float(mb_horizon.get('targetPrice', 0) or 0)

    if target <= 0 and current_price > 0:
        target = current_price * (1 + expected_return)

    projected, upper_band, lower_band = [], [], []
    today = datetime.now(timezone.utc)
    delta_price = target - current_price
    base_uncertainty = abs(current_price) * 0.02  # 2% base

    for i in range(horizon_days + 1):
        day = today + timedelta(days=i)
        t_str = day.strftime('%Y-%m-%d')
        progress = i / max(horizon_days, 1)
        s_curve = 3 * progress**2 - 2 * progress**3  # smooth S
        projected_price = current_price + delta_price * s_curve
        # Uncertainty widens with time, narrows with confidence
        uncertainty = base_uncertainty * math.sqrt(i + 1) * (1.3 - confidence * 0.5)
        projected.append({'t': t_str, 'v': round(projected_price, 2)})
        upper_band.append({'t': t_str, 'v': round(projected_price + uncertainty, 2)})
        lower_band.append({'t': t_str, 'v': round(projected_price - uncertainty, 2)})

    return {
        'projected': projected,
        'upperBand': upper_band,
        'lowerBand': lower_band,
        'target': round(target, 2),
    }


# ───────────────────────────────────────────────────────────
# Scenarios — framed by MetaBrain bias (base / bull / risk)
# ───────────────────────────────────────────────────────────
def _build_scenarios_from_mb(current_price: float, mb_horizon: dict, horizon_key: str) -> dict:
    direction = (mb_horizon.get('direction', 'NEUTRAL') or 'NEUTRAL').upper()
    expected_return = float(mb_horizon.get('expectedReturn', 0) or 0)
    target = float(mb_horizon.get('targetPrice', 0) or current_price * (1 + expected_return))
    days = HORIZON_DAYS.get(horizon_key, 30)

    bull_target = round(current_price * (1 + abs(expected_return) * 1.5), 0) if current_price else 0
    risk_target = round(current_price * (1 - abs(expected_return) * 0.7), 0) if current_price else 0

    # For NEUTRAL regime expected_return is 0, so bull/risk targets would collapse
    # to the current price. Use a horizon-scaled default volatility band so the
    # scenarios are still informative.
    if direction not in ('UP', 'BULLISH', 'DOWN', 'BEARISH') and current_price:
        vol_pct = {'7D': 0.04, '30D': 0.10, '90D': 0.18, '180D': 0.28, '365D': 0.40}.get(horizon_key, 0.10)
        bull_target = round(current_price * (1 + vol_pct), 0)
        risk_target = round(current_price * (1 - vol_pct), 0)

    if direction in ('UP', 'BULLISH'):
        return {
            'base': {
                'label': 'Base case',
                'description': f'MetaBrain path → ${target:,.0f} in {days} days',
                'target': round(target, 0), 'probability': 0.55,
            },
            'bull': {
                'label': 'Bull case',
                'description': f'Momentum breakout extends to ${bull_target:,.0f}',
                'target': bull_target, 'probability': 0.25,
            },
            'risk': {
                'label': 'Risk case',
                'description': f'Structure fails; retracement toward ${risk_target:,.0f}',
                'target': risk_target, 'probability': 0.20,
            },
        }
    if direction in ('DOWN', 'BEARISH'):
        return {
            'base': {
                'label': 'Base case',
                'description': f'MetaBrain path → ${target:,.0f} in {days} days',
                'target': round(target, 0), 'probability': 0.55,
            },
            'bull': {
                'label': 'Recovery case',
                'description': f'Reversal from oversold pushes back toward ${bull_target:,.0f}',
                'target': bull_target, 'probability': 0.20,
            },
            'risk': {
                'label': 'Risk case',
                'description': f'Sustained distribution extends to ${risk_target:,.0f}',
                'target': risk_target, 'probability': 0.25,
            },
        }
    return {
        'base': {
            'label': 'Base case',
            'description': f'Consolidation near ${current_price:,.0f} for {days} days',
            'target': round(current_price, 0), 'probability': 0.60,
        },
        'bull': {
            'label': 'Bull case',
            'description': f'Breakout from range toward ${bull_target:,.0f}',
            'target': bull_target, 'probability': 0.20,
        },
        'risk': {
            'label': 'Risk case',
            'description': f'Range breakdown toward ${risk_target:,.0f}',
            'target': risk_target, 'probability': 0.20,
        },
    }


# ───────────────────────────────────────────────────────────
# Interpretation — narrated from MetaBrain drivers (NOT from fractal alone)
# ───────────────────────────────────────────────────────────
def _interpretation_from_mb(drivers: dict, regime: str, mb_horizon: dict) -> list:
    bullets = []
    direction = (mb_horizon.get('direction', 'NEUTRAL') or 'NEUTRAL').upper()
    mb_conf = float(mb_horizon.get('confidence', 0) or 0)
    mb_meta = mb_horizon.get('metabrain', {}) or {}

    # 1) The blended verdict (explain what MB sees)
    if direction in ('UP', 'BULLISH'):
        bullets.append(f'MetaBrain sees upward path — bias={mb_meta.get("blendedBias", 0):+.2f}, conf={int(mb_conf*100)}%')
    elif direction in ('DOWN', 'BEARISH'):
        bullets.append(f'MetaBrain sees downward path — bias={mb_meta.get("blendedBias", 0):+.2f}, conf={int(mb_conf*100)}%')
    else:
        bullets.append(f'MetaBrain sees no dominant direction — bias near zero, conf={int(mb_conf*100)}%')

    # 2) Short-term vs long-term split (the MB-specific insight)
    st = mb_meta.get('shortTermBias', 0)
    lt = mb_meta.get('longTermBias', 0)
    if abs(st - lt) > 0.3:
        if st > lt:
            bullets.append(f'Short-term flow stronger than structure (flow {st:+.2f} vs structure {lt:+.2f})')
        else:
            bullets.append(f'Structural bias stronger than current flow (structure {lt:+.2f} vs flow {st:+.2f})')

    # 3) Named driver contributions
    for mod in ('exchange', 'sentiment', 'onchain', 'fractal'):
        d = drivers.get(mod, {})
        if not d:
            continue
        name = d.get('name', mod.title())
        interp = d.get('interpretation') or d.get('reason') or d.get('value')
        if interp:
            bullets.append(f'{name}: {interp}')

    # 4) Regime context
    if regime == 'TREND':
        bullets.append('Regime TREND — directional moves more likely')
    elif regime == 'RANGE':
        bullets.append('Regime RANGE — mean reversion expected')

    return bullets[:7]


# ───────────────────────────────────────────────────────────
# Historical forecast accuracy (audit trail — not brain)
# ───────────────────────────────────────────────────────────
def _get_truth_layer() -> dict:
    resolved = list(_db.btc_fractal_forecasts.find(
        {'resolved': True},
        {'_id': 0, 'direction': 1, 'resolvedPnl': 1, 'outcome': 1}
    ).sort([('resolvedAt', -1)]).limit(20))
    if not resolved:
        return {'available': False}
    total = len(resolved)
    wins = sum(1 for r in resolved if (r.get('resolvedPnl', 0) or 0) > 0 or r.get('outcome') == 'win')
    win_rate = round(wins / total * 100) if total > 0 else 0
    last = resolved[0] if resolved else {}
    last_pnl = last.get('resolvedPnl', 0) or 0
    streak = 0
    for r in resolved:
        if (r.get('resolvedPnl', 0) or 0) > 0:
            streak += 1
        else:
            break
    return {
        'available': True,
        'totalForecasts': total,
        'winRate': win_rate,
        'lastOutcome': f"{'+' if last_pnl > 0 else ''}{last_pnl:.1f}%" if last_pnl else 'pending',
        'streak': streak,
    }


# ───────────────────────────────────────────────────────────
# NEXT MOVE LEVELS — actionable break points from recent OHLCV
# ───────────────────────────────────────────────────────────
def _get_next_move_levels(current_price: float, direction: str, state: str) -> dict:
    """Compute break-above / break-below levels from recent BTC swings."""
    try:
        candles = list(_db.fractal_canonical_ohlcv.find(
            {'meta.symbol': 'BTC'},
            {'_id': 0, 'ohlcv.h': 1, 'ohlcv.l': 1, 'ohlcv.c': 1, 'ts': 1}
        ).sort([('ts', -1)]).limit(30))
        if len(candles) < 7 or current_price <= 0:
            return {}
        recent_highs = [c['ohlcv'].get('h', 0) for c in candles[:14] if c['ohlcv'].get('h')]
        recent_lows = [c['ohlcv'].get('l', 0) for c in candles[:14] if c['ohlcv'].get('l')]
        recent_highs = [h for h in recent_highs if h > current_price]
        recent_lows = [l for l in recent_lows if l < current_price]
        resistance = min(recent_highs) if recent_highs else round(current_price * 1.03, 0)
        support = max(recent_lows) if recent_lows else round(current_price * 0.97, 0)

        break_above_scenario = 'bullish continuation'
        break_below_scenario = 'bearish move'
        if state == 'TENSION':
            break_above_scenario = 'breakout confirmed — upside trigger'
            break_below_scenario = 'breakdown confirmed — downside trigger'
        elif state == 'CONFLICT':
            break_above_scenario = 'resolution to bullish side'
            break_below_scenario = 'resolution to bearish side'

        return {
            'breakAbove': {
                'price': round(resistance, 0),
                'distancePct': round((resistance - current_price) / current_price * 100, 2),
                'scenario': break_above_scenario,
            },
            'breakBelow': {
                'price': round(support, 0),
                'distancePct': round((support - current_price) / current_price * 100, 2),
                'scenario': break_below_scenario,
            },
        }
    except Exception as e:
        logger.warning(f'next move levels failed: {e}')
        return {}


# ───────────────────────────────────────────────────────────
# STATE HISTORY STATS — past performance of this state
# ───────────────────────────────────────────────────────────
def _get_state_history_stats(state: str, symbol: str = 'BTC') -> dict:
    """
    Returns: for the current state, how many times it occurred and what was
    the typical BTC move that followed over the next 7 days.
    """
    if not state or state in ('SCANNING', 'CALM'):
        return {'available': False}
    try:
        events = list(_db.state_history.find(
            {'symbol': symbol, 'state': state, 'outcomeResolved': True},
            {'_id': 0, 'outcomeReturn': 1, 'enteredAt': 1, 'outcomeDirection': 1}
        ).sort([('enteredAt', -1)]).limit(20))
        if len(events) < 2:
            return {'available': False, 'occurrences': len(events)}
        moves = [e.get('outcomeReturn', 0) for e in events if e.get('outcomeReturn') is not None]
        moves_signed = [round(m * 100, 2) for m in moves]  # in %
        if not moves_signed:
            return {'available': False}
        avg_move = round(sum(abs(m) for m in moves_signed) / len(moves_signed), 2)
        max_move = max(moves_signed)
        min_move = min(moves_signed)
        bullish_count = sum(1 for e in events if e.get('outcomeDirection') == 'up')
        bearish_count = sum(1 for e in events if e.get('outcomeDirection') == 'down')
        return {
            'available': True,
            'state': state,
            'occurrences': len(events),
            'recentMoves': moves_signed[:5],
            'avgAbsMove': avg_move,
            'maxMove': max_move,
            'minMove': min_move,
            'bullishFollowup': bullish_count,
            'bearishFollowup': bearish_count,
            'narrative': f'Last {len(events)} times this state appeared → avg move ±{avg_move}%',
        }
    except Exception as e:
        logger.warning(f'state history stats failed: {e}')
        return {'available': False}


# ───────────────────────────────────────────────────────────
# DRIVER NARRATIVES — convert direction+confidence into real sentences
# ───────────────────────────────────────────────────────────
_DRIVER_NARRATIVES = {
    ('exchange', 'Bullish'): 'buying pressure rising',
    ('exchange', 'Bearish'): 'selling pressure rising',
    ('exchange', 'Neutral'): 'flow balanced · no edge',
    ('sentiment', 'Bullish'): 'social greed extending',
    ('sentiment', 'Bearish'): 'fear increasing',
    ('sentiment', 'Neutral'): 'neutral mood · no conviction',
    ('onchain', 'Bullish'): 'on-chain accumulation',
    ('onchain', 'Bearish'): 'on-chain distribution',
    ('onchain', 'Neutral'): 'chain quiet · no signal',
    ('fractal', 'Bullish'): 'reversal structure forming',
    ('fractal', 'Bearish'): 'breakdown structure forming',
    ('fractal', 'Neutral'): 'structure still ranging',
    ('metabrain', 'Bullish'): 'cross-module synthesis positive',
    ('metabrain', 'Bearish'): 'cross-module synthesis negative',
    ('metabrain', 'Neutral'): 'modules not yet converging',
    ('prediction', 'Bullish'): 'markets betting up',
    ('prediction', 'Bearish'): 'markets betting down',
    ('prediction', 'Neutral'): 'prediction markets mixed',
}


def _enrich_drivers_with_narrative(drivers: dict) -> dict:
    """Augment each driver with a human-readable narrative."""
    out = {}
    for mod, d in drivers.items():
        direction = d.get('direction', 'Neutral')
        base_narr = d.get('interpretation') or d.get('reason') or ''
        narrative = _DRIVER_NARRATIVES.get((mod, direction), base_narr or f'{mod} monitoring')
        out[mod] = {
            **d,
            'narrative': narrative,
        }
    return out


def _track_state_transition(symbol: str, new_state: str, current_price: float):
    """
    Track market state transitions in `state_history` collection.
    Each time the state changes we:
      - insert a new record with entry price
      - resolve the previous record (compute outcomeReturn, direction)
        if >= 24h elapsed.
    This feeds _get_state_history_stats() for "last time this state
    appeared, market moved X%".
    """
    try:
        latest = _db.state_history.find_one(
            {'symbol': symbol}, sort=[('enteredAt', -1)]
        )
        now = datetime.now(timezone.utc)

        # Resolve any unresolved older record after 24h.
        if latest and not latest.get('outcomeResolved'):
            entered = latest.get('enteredAt')
            if entered:
                # Ensure timezone-aware comparison
                if entered.tzinfo is None:
                    entered = entered.replace(tzinfo=timezone.utc)
                age_hours = (now - entered).total_seconds() / 3600
                if age_hours >= 24:
                    entry_p = latest.get('entryPrice', 0) or 0
                    if entry_p > 0 and current_price > 0:
                        ret = (current_price - entry_p) / entry_p
                        _db.state_history.update_one(
                            {'_id': latest['_id']},
                            {'$set': {
                                'outcomeResolved': True,
                                'outcomeReturn': round(ret, 4),
                                'outcomeDirection': 'up' if ret > 0.005 else ('down' if ret < -0.005 else 'flat'),
                                'resolvedAt': now,
                                'resolvedPrice': current_price,
                            }}
                        )

        # Insert new record on state change (or first time)
        if not latest or latest.get('state') != new_state:
            _db.state_history.insert_one({
                'symbol': symbol,
                'state': new_state,
                'entryPrice': round(current_price, 2),
                'enteredAt': now,
                'outcomeResolved': False,
            })
    except Exception as e:
        logger.warning(f'state transition tracking failed: {e}')


# ───────────────────────────────────────────────────────────
# MAIN ADAPTER — assembles UI payload from MetaBrain output
# ───────────────────────────────────────────────────────────
def build_prediction_payload(symbol: str = 'BTC', horizon: str = '30D', access_level: str = 'FREE') -> dict:
    """UI payload — pure adapter over MetaBrain. Source-of-truth = METABRAIN."""
    if horizon not in HORIZONS:
        horizon = '30D'

    # SINGLE SOURCE OF TRUTH ─────────────────────────────────
    from services.meta_brain_service import build_horizon_forecasts, build_snapshot
    snapshot = build_snapshot(symbol)
    mb = build_horizon_forecasts(symbol)

    current_price = float(mb.get('currentPrice') or snapshot.get('price') or 0)
    if current_price <= 0:
        return {'ok': False, 'error': 'No price data available', 'source': 'METABRAIN'}

    mb_horizons = mb.get('horizons', {}) or {}
    active_mb = mb_horizons.get(horizon, {}) or {}

    # Historical series (visualization input)
    history_days = HISTORY_DAYS.get(horizon, 90)
    price_series = _get_price_series(history_days)

    # Per-horizon timeframes — all driven by MetaBrain
    timeframes = []
    for h in HORIZONS:
        mbh = mb_horizons.get(h, {}) or {}
        tf_data = {
            'key': h,
            'days': HORIZON_DAYS[h],
            'direction': mbh.get('direction', 'NEUTRAL'),
            'confidence': round(float(mbh.get('confidence', 0) or 0), 2),
            'conviction': round(float(mbh.get('conviction', 0) or 0), 2),
            'agreement': round(float(mbh.get('agreement', 0) or 0), 2),
            'convictionLabel': mbh.get('convictionLabel', 'LOW'),
            'agreementLabel': mbh.get('agreementLabel', 'LOW'),
            'marketState': mbh.get('marketState', 'SCANNING'),
            'expectedReturn': round(float(mbh.get('expectedReturn', 0) or 0) * 100, 1),
            'source': 'METABRAIN',
        }
        if h == horizon:
            projection = _build_projection_from_mb(current_price, mbh, HORIZON_DAYS[h])
            tf_data['projectedSeries'] = projection['projected']
            tf_data['upperBand'] = projection['upperBand']
            tf_data['lowerBand'] = projection['lowerBand']
            tf_data['target'] = projection['target']
        timeframes.append(tf_data)

    # Summary fields from ACTIVE horizon MB forecast
    active_dir = (active_mb.get('direction', 'NEUTRAL') or 'NEUTRAL').upper()
    active_conf = round(float(active_mb.get('confidence', 0.3) or 0.3), 2)
    active_conv = round(float(active_mb.get('conviction', 0.3) or 0.3), 2)
    active_ret = float(active_mb.get('expectedReturn', 0) or 0)
    active_meta = active_mb.get('metabrain', {}) or {}

    if active_dir in ('UP', 'BULLISH'):
        bias, bias_emoji = 'Bullish', '↑'
    elif active_dir in ('DOWN', 'BEARISH'):
        bias, bias_emoji = 'Bearish', '↓'
    else:
        bias, bias_emoji = 'Neutral', '→'

    move_low = abs(active_ret * 100 * 0.6)
    move_high = abs(active_ret * 100 * 1.4)
    if bias == 'Bearish':
        expected_move = f"-{move_low:.0f}–{move_high:.0f}%"
    elif bias == 'Bullish':
        expected_move = f"+{move_low:.0f}–{move_high:.0f}%"
    else:
        expected_move = f"±{move_high:.0f}%"

    regime = mb.get('regime') or (snapshot.get('context') or {}).get('regime') or 'NEUTRAL'

    # Summary text — uses MetaBrain signal.summary when present
    signal_summary = (snapshot.get('signal') or {}).get('summary', '')
    if bias == 'Bullish':
        summary_text = signal_summary or 'MetaBrain sees recovery path from current structure'
    elif bias == 'Bearish':
        summary_text = signal_summary or 'MetaBrain sees downward pressure building from current levels'
    else:
        summary_text = signal_summary or 'MetaBrain sees no dominant edge — consolidation likely'

    # Drivers, scenarios, interpretation — MetaBrain-sourced
    drivers_raw = mb.get('drivers', {}) or {}
    drivers = _enrich_drivers_with_narrative(drivers_raw)
    scenarios = _build_scenarios_from_mb(current_price, active_mb, horizon)
    interpretation = _interpretation_from_mb(drivers, regime, active_mb)

    # State engine actionable data (NEW)
    active_state = active_mb.get('marketState', 'SCANNING')
    next_move_levels = _get_next_move_levels(current_price, active_dir, active_state)
    state_history = _get_state_history_stats(active_state, symbol.upper())

    # Track state transitions for future history stats
    _track_state_transition(symbol.upper(), active_state, current_price)

    # Signal connection — from MetaBrain snapshot signal (not locally computed)
    global_signal = mb.get('globalSignal', {}) or {}
    action = global_signal.get('action', 'WAIT')
    g_conf = float(global_signal.get('confidence', 0) or 0)
    if action in ('BUY', 'SELL') and g_conf >= 0.5:
        stage = 'SIGNAL'
    elif g_conf >= 0.4:
        stage = 'CONFIRMING'
    elif g_conf >= 0.25:
        stage = 'FORMING'
    else:
        stage = 'EARLY'
    entry_window_active = action in ('BUY', 'SELL') and g_conf >= 0.4

    # 24h change from snapshot if available, fallback to observations
    daily_change = 0.0
    try:
        obs = _db.exchange_observations.find_one(
            {'$or': [{'asset': symbol.upper()}, {'symbol': f'{symbol.upper()}USDT'}]},
            {'_id': 0, 'change24h': 1},
            sort=[('timestamp', -1)]
        )
        if obs:
            daily_change = float(obs.get('change24h', 0) or 0)
    except Exception:
        pass

    # Truth layer
    truth = _get_truth_layer()

    # Build response
    payload = {
        'ok': True,
        'source': 'METABRAIN',   # ← source-of-truth marker
        'symbol': symbol,
        'currentPrice': round(current_price, 2),
        'dailyChange': round(daily_change, 2),
        'updatedAt': datetime.now(timezone.utc).isoformat(),
        'nextUpdateHours': REFRESH_HOURS.get(horizon, 6),

        'activeHorizon': horizon,

        'summary': {
            'bias': bias,
            'biasEmoji': bias_emoji,
            'confidence': round(active_conf * 100),
            'conviction': round(active_conv * 100),
            'confidenceLabel': active_mb.get('agreementLabel', 'LOW'),
            'convictionLabel': active_mb.get('convictionLabel', 'LOW'),
            'expectedMove': expected_move,
            'summaryText': summary_text,
            'hasConflict': bool(active_meta.get('hasConflict', False)),
            'conflictFromSplit': bool(active_meta.get('conflictFromSplit', False)),
            'conflictFromAgreement': bool(active_meta.get('conflictFromAgreement', False)),
            'bullishDrivers': active_meta.get('bullishDrivers', []),
            'bearishDrivers': active_meta.get('bearishDrivers', []),
            'marketState': active_mb.get('marketState', 'SCANNING'),
            'marketStateText': active_mb.get('marketStateText', ''),
            'marketStateColor': active_mb.get('marketStateColor', 'gray'),
            'actionVerb': active_mb.get('actionVerb', 'WATCH'),
            'actionHint': active_mb.get('actionHint', ''),
        },

        'nextMoveLevels': next_move_levels,   # NEW — actionable break points
        'stateHistory': state_history,        # NEW — "last time this state" stats

        'priceSeries': price_series,
        'timeframes': timeframes,

        'scenarios': scenarios,
        'interpretation': interpretation,
        'regime': regime,

        'truth': truth,

        'signalConnection': {
            'stage': stage,
            'entryWindowActive': entry_window_active,
        },

        # MetaBrain transparency block — shows why this prediction exists
        'metabrain': {
            'globalAction': action,
            'globalDirection': global_signal.get('direction', 'neutral'),
            'globalConfidence': round(g_conf * 100),
            'regime': regime,
            'drivers': {
                mod: {
                    'direction': d.get('direction', 'Neutral'),
                    'confidence': round(float(d.get('confidence', 0) or 0) * 100),
                    'weight': float(d.get('weight', 0) or 0),
                    'interpretation': d.get('interpretation') or d.get('reason') or d.get('value', ''),
                    'narrative': d.get('narrative', ''),   # NEW — sentence-form
                }
                for mod, d in drivers.items()
            },
            'activeHorizonMeta': active_mb.get('metabrain', {}),
        },

        'accessLevel': access_level,
    }

    # PRO gating (same as before)
    if access_level != 'PRO':
        payload['scenarios'] = {
            'base': scenarios.get('base', {}),
            'bull': {'label': 'Bull case', 'locked': True},
            'risk': {'label': 'Risk case', 'locked': True},
        }
        payload['truth'] = {'available': False, 'locked': True}
        for tf in payload['timeframes']:
            if tf['key'] != horizon:
                tf['locked'] = True

    return payload


# ───────────────────────────────────────────────────────────
# Compact payload — for MiniApp / Home preview / Telegram teaser
# Also sourced from MetaBrain.
# ───────────────────────────────────────────────────────────
def build_compact_payload(symbol: str = 'BTC') -> dict:
    """Compact MetaBrain-sourced prediction for MiniApp / Home preview / Telegram teaser."""
    from services.meta_brain_service import build_horizon_forecasts
    mb = build_horizon_forecasts(symbol)
    current_price = float(mb.get('currentPrice', 0) or 0)
    mb_horizons = mb.get('horizons', {}) or {}
    active = mb_horizons.get('30D', {}) or {}

    direction = (active.get('direction', 'NEUTRAL') or 'NEUTRAL').upper()
    confidence = round(float(active.get('confidence', 0.3) or 0.3) * 100)
    expected_return = float(active.get('expectedReturn', 0) or 0)

    if direction in ('UP', 'BULLISH'):
        bias, bias_emoji, color = 'Bullish', '↑', 'green'
        move = f"+{abs(expected_return * 100):.0f}%"
    elif direction in ('DOWN', 'BEARISH'):
        bias, bias_emoji, color = 'Bearish', '↓', 'red'
        move = f"-{abs(expected_return * 100):.0f}%"
    else:
        bias, bias_emoji, color = 'Neutral', '→', 'gray'
        move = f"±{abs(expected_return * 100):.0f}%"

    webapp_url = os.environ.get('MINIAPP_URL', '')
    deeplink = f"{webapp_url}?tab=prediction&symbol={symbol}" if webapp_url else ''
    app_scheme = f"fomoapp://prediction?symbol={symbol}"

    teaser_text = (
        f"<b>🎯 {symbol} MetaBrain · 30D</b>\n\n"
        f"{bias_emoji} <b>{bias}</b> · {confidence}% confidence\n"
        f"Expected move: <b>{move}</b>\n"
        f"Current: ${current_price:,.0f}\n\n"
        f"→ Open full prediction in app"
    )

    return {
        'ok': True,
        'source': 'METABRAIN',
        'symbol': symbol,
        'currentPrice': round(current_price, 2),
        'horizon': '30D',
        'bias': bias,
        'biasEmoji': bias_emoji,
        'biasColor': color,
        'confidence': confidence,
        'expectedMove': move,
        'summaryText': f'30D MetaBrain: {bias.lower()} bias, {move} expected',
        'teaser': teaser_text,
        'deeplink': deeplink,
        'appScheme': app_scheme,
        'updatedAt': datetime.now(timezone.utc).isoformat(),
    }


def detect_direction_shift(symbol: str = 'BTC') -> dict:
    """
    Backward-compatible wrapper. Prefer detect_significant_change().
    """
    return detect_significant_change(symbol)


def detect_significant_change(symbol: str = 'BTC') -> dict:
    """
    Detect ANY significant MetaBrain prediction change worth notifying users:
      1) direction shift (Bullish ↔ Bearish ↔ Neutral)
      2) confidence spike (|Δ| >= 15 points)
      3) conviction spike (|Δ| >= 15 points) — captures intensity gains
         even when direction is stable
      4) entry window opening (entry_window_active flips False → True)

    State is persisted in `prediction_shift_state` collection. Returns
    flags describing every reason a broadcast should fire.
    """
    from services.meta_brain_service import build_horizon_forecasts, build_snapshot
    mb = build_horizon_forecasts(symbol)
    snapshot = build_snapshot(symbol)
    mb_horizons = mb.get('horizons', {}) or {}
    active = mb_horizons.get('30D', {}) or {}

    new_direction = (active.get('direction', 'NEUTRAL') or 'NEUTRAL').upper()
    new_conf = round(float(active.get('confidence', 0) or 0) * 100)
    new_conv = round(float(active.get('conviction', 0) or 0) * 100)
    new_state = active.get('marketState', 'SCANNING')

    if new_direction in ('UP', 'BULLISH'):
        new_bias = 'Bullish'
    elif new_direction in ('DOWN', 'BEARISH'):
        new_bias = 'Bearish'
    else:
        new_bias = 'Neutral'

    # Entry window from the global signal
    global_sig = (snapshot.get('signal') or {})
    action = global_sig.get('action', 'WAIT')
    global_conf = float(global_sig.get('confidence', 0) or 0)
    entry_window = action in ('BUY', 'SELL') and global_conf >= 0.5

    # Load last state
    last = _db.prediction_shift_state.find_one({'symbol': symbol}) or {}
    last_bias = last.get('bias')
    last_conf = last.get('confidence', 0) or 0
    last_conv = last.get('conviction', 0) or 0
    last_entry = bool(last.get('entryWindowActive', False))
    last_state = last.get('marketState')

    # Triggers
    dir_shift = last_bias is not None and last_bias != new_bias
    conf_spike = last_bias is not None and abs(new_conf - last_conf) >= 15
    conv_spike = last_conv > 0 and abs(new_conv - last_conv) >= 15
    window_open = (not last_entry) and entry_window
    state_change = last_state is not None and last_state != new_state
    # TENSION = divergence (LOW agreement + HIGH conviction) = pre-move signal
    tension_new = new_state == 'TENSION' and last_state != 'TENSION'

    reasons = []
    if dir_shift:
        reasons.append('direction_shift')
    if window_open:
        reasons.append('entry_window_open')
    if tension_new:
        reasons.append('tension_rising')
    if state_change and not tension_new:
        reasons.append('state_change')
    if conf_spike:
        reasons.append('confidence_spike')
    if conv_spike:
        reasons.append('conviction_spike')

    shifted = len(reasons) > 0

    # Persist current state
    _db.prediction_shift_state.update_one(
        {'symbol': symbol},
        {'$set': {
            'symbol': symbol,
            'bias': new_bias,
            'confidence': new_conf,
            'conviction': new_conv,
            'marketState': new_state,
            'prevBias': last_bias,
            'prevConfidence': last_conf,
            'prevConviction': last_conv,
            'prevMarketState': last_state,
            'entryWindowActive': entry_window,
            'source': 'METABRAIN',
            'updatedAt': datetime.now(timezone.utc),
        }},
        upsert=True,
    )

    return {
        'shifted': shifted,
        'reasons': reasons,
        'prevBias': last_bias,
        'newBias': new_bias,
        'prevConfidence': last_conf,
        'confidence': new_conf,
        'prevConviction': last_conv,
        'conviction': new_conv,
        'prevMarketState': last_state,
        'marketState': new_state,
        'entryWindowActive': entry_window,
        'source': 'METABRAIN',
    }
