"""
FOMO Daily Summary Engine — Honest daily recap.

Collects real data from the day and produces a structured summary.
NO fake narratives — if data is thin, the summary is short and neutral.

Summary includes:
  - Current bias (BUY/SELL/WAIT) with confidence
  - Best move today (strongest closed signal)
  - Market state (trending/ranging/volatile)
  - Top reason (from signal drivers)
  - Missed teaser for FREE users
  - Signals count and performance
"""
import logging
import os
from datetime import datetime, timedelta
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

signals_col = db['signal_history']
observations_col = db['exchange_observations']


def get_daily_summary(asset: str, user_id: str = None, plan: str = 'FREE') -> dict:
    """
    Build an honest daily summary for the given asset.
    Uses only real data from today — no fabrication.
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    now = datetime.utcnow()

    # 1. Get latest observation for market data
    obs = observations_col.find_one(
        {'asset': asset},
        sort=[('ts', DESCENDING)],
    )

    # 2. Get today's signals
    closed_today = list(signals_col.find({
        'asset': asset,
        'status': 'CLOSED',
        'closeTs': {'$gte': today_start},
    }).sort('pnlPct', DESCENDING))

    opened_today = signals_col.count_documents({
        'asset': asset,
        'entryTs': {'$gte': today_start},
    })

    # 3. Get current open signal (latest bias)
    current_signal = signals_col.find_one(
        {'asset': asset, 'status': 'OPEN'},
        sort=[('entryTs', DESCENDING)],
    )

    # 4. Compute honest metrics
    # Current bias
    if current_signal:
        bias = current_signal.get('action', 'WAIT')
        confidence = current_signal.get('confidence', 0)
    elif obs:
        # Derive from market data if no open signal
        change24h = obs.get('change24h', 0)
        if change24h > 2:
            bias = 'BUY'
            confidence = min(0.7 + change24h * 0.02, 0.92)
        elif change24h < -2:
            bias = 'SELL'
            confidence = min(0.7 + abs(change24h) * 0.02, 0.92)
        else:
            bias = 'WAIT'
            confidence = 0.5
    else:
        bias = 'WAIT'
        confidence = 0

    # Best move today (only from closed signals)
    best_move = None
    if closed_today:
        best = closed_today[0]  # Already sorted by pnlPct DESC
        if best.get('pnlPct', 0) > 0:
            best_move = {
                'asset': best.get('asset', asset),
                'action': best.get('action', ''),
                'pnlPct': best.get('pnlPct', 0),
                'confidence': best.get('confidence', 0),
                'horizon': best.get('horizon', 'INTRADAY'),
            }

    # Market state
    market_state = 'NEUTRAL'
    if obs:
        volatility = obs.get('volatility24h', 2)
        change24h = obs.get('change24h', 0)
        if volatility > 6:
            market_state = 'VOLATILE'
        elif abs(change24h) > 3:
            market_state = 'TRENDING'
        elif abs(change24h) < 0.5:
            market_state = 'RANGING'
        else:
            market_state = 'TRENDING' if abs(change24h) > 1 else 'CALM'

    # Top reason — from current signal reasons or latest observation
    top_reason = _get_top_reason(current_signal, obs, asset)

    # Win/loss stats for today
    wins_today = sum(1 for s in closed_today if s.get('outcome') == 'WIN')
    losses_today = sum(1 for s in closed_today if s.get('outcome') == 'LOSS')
    total_pnl_today = sum(s.get('pnlPct', 0) for s in closed_today)

    # Missed signals (for FREE teaser)
    missed_data = None
    if user_id:
        try:
            from services.missed_engine import get_missed_signals
            missed = get_missed_signals(user_id, asset, limit=3)
            if missed.get('count', 0) > 0:
                missed_data = {
                    'count': missed['count'],
                    'avgMovePct': missed['avgMovePct'],
                }
        except Exception as e:
            logger.warning(f"Missed data fetch for summary failed: {e}")

    # Locked insights count (for FREE teaser) — signals with confidence >= 0.8
    locked_insights = 0
    if plan == 'FREE':
        locked_insights = signals_col.count_documents({
            'asset': asset,
            'confidence': {'$gte': 0.8},
            'entryTs': {'$gte': today_start},
        })

    # Price data
    price = obs.get('price', 0) if obs else 0
    change_24h = obs.get('change24h', 0) if obs else 0

    # Build summary
    summary = {
        'asset': asset,
        'date': today_start.strftime('%Y-%m-%d'),
        'generatedAt': now.isoformat(),

        # Core decision
        'bias': bias,
        'confidence': round(confidence, 2),

        # Market context
        'price': price,
        'change24h': round(change_24h, 2),
        'marketState': market_state,

        # Today's performance
        'signalsToday': opened_today,
        'closedToday': len(closed_today),
        'winsToday': wins_today,
        'lossesToday': losses_today,
        'totalPnlToday': round(total_pnl_today, 2),

        # Best move
        'bestMove': best_move,

        # Top reason
        'topReason': top_reason,

        # FREE user teasers
        'missedTeaser': missed_data,
        'lockedInsights': locked_insights,

        # Summary text (honest)
        'summaryText': _build_summary_text(
            asset, bias, confidence, best_move, market_state,
            top_reason, change_24h, opened_today, len(closed_today)
        ),
        'freeTeaser': _build_free_teaser(locked_insights, missed_data, asset),
        'proSummary': _build_pro_summary(
            asset, bias, confidence, best_move, market_state,
            top_reason, wins_today, losses_today, total_pnl_today
        ) if plan in ('PRO', 'INSTITUTIONAL') else None,
    }

    return summary


def _get_top_reason(signal: dict | None, obs: dict | None, asset: str) -> str | None:
    """Extract the top reason from signal or market data — honest only."""
    # From signal reasons
    if signal and signal.get('reasons'):
        reasons = signal['reasons']
        # Get the strongest reason
        key_reasons = [r for r in reasons if r.get('impact') == 'strong']
        if key_reasons:
            return key_reasons[0].get('text', '')
        if reasons:
            return reasons[0].get('text', '')

    # From observation data — derive honest reason
    if obs:
        change24h = obs.get('change24h', 0)
        volume = obs.get('volume24h', 0)
        sentiment = obs.get('sentimentUp', 50)

        if abs(change24h) > 5:
            direction = 'rally' if change24h > 0 else 'selloff'
            return f'Strong {direction}: {abs(change24h):.1f}% in 24h'
        elif sentiment > 70:
            return f'High bullish sentiment: {sentiment:.0f}% community confidence'
        elif sentiment < 30:
            return f'Fear dominating: only {sentiment:.0f}% bullish'
        elif abs(change24h) > 2:
            direction = 'Momentum building' if change24h > 0 else 'Bearish pressure'
            return f'{direction}: {change24h:+.1f}% today'

    return None


def _build_summary_text(
    asset: str, bias: str, confidence: float,
    best_move: dict | None, market_state: str,
    top_reason: str | None, change24h: float,
    signals_count: int, closed_count: int,
) -> str:
    """Build honest summary text — no fabrication."""
    parts = []

    # Bias
    conf_pct = int(confidence * 100)
    if bias == 'WAIT':
        parts.append(f'{asset}: Mixed signals — no clear direction')
    else:
        parts.append(f'{asset}: {bias} ({conf_pct}% conviction)')

    # Best move
    if best_move:
        parts.append(f'Best move: +{best_move["pnlPct"]}%')

    # Market state
    state_map = {
        'VOLATILE': 'Volatile',
        'TRENDING': 'Trending',
        'RANGING': 'Ranging',
        'CALM': 'Calm',
        'NEUTRAL': 'Neutral',
    }
    parts.append(f'Market: {state_map.get(market_state, market_state)}')

    # Top reason
    if top_reason:
        parts.append(f'Why: {top_reason}')

    return ' | '.join(parts)


def _build_free_teaser(locked_insights: int, missed_data: dict | None, asset: str) -> str | None:
    """Build teaser text for FREE users — honest FOMO trigger."""
    parts = []
    if locked_insights > 0:
        parts.append(f'You had {locked_insights} locked insight{"s" if locked_insights > 1 else ""} today')
    if missed_data and missed_data.get('count', 0) > 0:
        parts.append(f'Missed: +{missed_data["avgMovePct"]}% avg move')

    return ' | '.join(parts) if parts else None


def _build_pro_summary(
    asset: str, bias: str, confidence: float,
    best_move: dict | None, market_state: str,
    top_reason: str | None,
    wins: int, losses: int, total_pnl: float,
) -> str:
    """Build extended summary for PRO users."""
    parts = []
    parts.append(f'{asset} Daily Recap')

    conf_pct = int(confidence * 100)
    parts.append(f'Current: {bias} at {conf_pct}%')
    parts.append(f'Market: {market_state}')

    if wins + losses > 0:
        parts.append(f'Closed: {wins}W/{losses}L ({total_pnl:+.1f}% total)')

    if best_move:
        parts.append(f'Top: {best_move["action"]} {best_move["asset"]} +{best_move["pnlPct"]}%')

    if top_reason:
        parts.append(f'Driver: {top_reason}')

    return ' | '.join(parts)


# ==================== PUSH INTEGRATION ====================

def build_daily_summary_push(summary: dict, variant: str = 'A') -> dict:
    """Build push notification payload for daily summary."""
    asset = summary['asset']
    bias = summary['bias']
    conf_pct = int(summary.get('confidence', 0) * 100)
    market_state = summary.get('marketState', 'NEUTRAL')
    best_move = summary.get('bestMove')

    if variant == 'A':
        title = f'Daily Summary: {asset}'
        body_parts = [f'{bias} ({conf_pct}%)']
        if best_move:
            body_parts.append(f'Best: +{best_move["pnlPct"]}%')
        body_parts.append(f'{market_state}')
        body = ' | '.join(body_parts)
    else:
        title = f'{asset}: {bias} • {market_state}'
        body_parts = []
        if best_move:
            body_parts.append(f'Best move: +{best_move["pnlPct"]}%')
        if summary.get('topReason'):
            body_parts.append(summary['topReason'])
        body = ' | '.join(body_parts) if body_parts else f'{conf_pct}% conviction today'

    return {
        'type': 'DAILY_SUMMARY',
        'asset': asset,
        'title': title,
        'body': body,
        'variant': variant,
        'priority': 60,  # Lower priority than signals
        'dedup_key': f'DAILY_SUMMARY:{asset}:{summary.get("date", "")}',
        'payload': {
            'screen': 'home',
            'asset': asset,
            'type': 'daily_summary',
        },
    }
