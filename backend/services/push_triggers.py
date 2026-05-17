"""
Push Intelligence — Trigger Engine
===================================

THREE trigger types that drive retention loop:

1. PNL TRIGGERS — Portfolio positions moving
   - pnl > +2%  → positive push → FOMO: "Don't lose the move"
   - pnl < -1.5% → warning push → urgency: "Re-evaluate your position"

2. EDGE TRIGGERS — Signal/setup changes
   - New edge signal → "Setup evolving. Entry forming."
   - Signal confidence jump → "Conviction rising"

3. WATCHLIST TRIGGERS — Watched assets heating up
   - Watchlist asset moves > +3% → "You added this earlier. Now it's moving."

Formula: Position → PnL → Push → Return → Check → Repeat
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Collections
push_triggers_log = db['push_triggers_log']
push_triggers_log.create_index([('userId', 1), ('type', 1), ('symbol', 1), ('createdAt', -1)])

# ═══════════════════════════════════════
#  PRICE HELPER
# ═══════════════════════════════════════

def _get_current_price(symbol: str) -> float:
    """Get current price from multiple sources."""
    sym = symbol.upper()

    # 1. Try exchange_observations (real-time from Node.js WebSocket)
    try:
        obs = db.get_collection('exchange_observations').find_one(
            {'symbol': f'{sym}USDT'},
            sort=[('timestamp', -1)]
        )
        if obs:
            market = obs.get('market', {})
            if isinstance(market, dict):
                price = market.get('price')
                if price and float(price) > 0:
                    return float(price)
    except Exception:
        pass

    # 2. Try meta_brain
    brain = db.get_collection('meta_brain')
    doc = brain.find_one({'symbol': sym}, sort=[('timestamp', -1)])
    if doc and doc.get('price'):
        return float(doc['price'])

    # 3. Try coingecko_cache
    cg = db.get_collection('coingecko_cache')
    cg_doc = cg.find_one({'symbol': sym.lower()})
    if cg_doc and cg_doc.get('current_price'):
        return float(cg_doc['current_price'])

    return 0


def _was_triggered_recently(user_id: str, trigger_type: str, symbol: str, cooldown_hours: int = 4) -> bool:
    """Check if this trigger was already fired recently."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
    existing = push_triggers_log.find_one({
        'userId': user_id,
        'type': trigger_type,
        'symbol': symbol,
        'createdAt': {'$gte': cutoff},
    })
    return existing is not None


def _log_trigger(user_id: str, trigger_type: str, symbol: str, data: dict):
    """Log that a trigger was fired."""
    push_triggers_log.insert_one({
        'userId': user_id,
        'type': trigger_type,
        'symbol': symbol,
        'data': data,
        'createdAt': datetime.now(timezone.utc),
    })


# ═══════════════════════════════════════
#  1. PNL TRIGGERS
# ═══════════════════════════════════════

# Aggressive, narrative-driven copy
PNL_POSITIVE_MESSAGES = {
    'en': [
        "{symbol} {pnl}%\nYou entered early. Momentum continues.",
        "{symbol} is running {pnl}%\nYou are already in {symbol}. Still building.",
        "{symbol} {pnl}% — System was right\nYou trusted the signal. The crowd enters later.",
    ],
    'ru': [
        "{symbol} {pnl}%\nТы вошёл рано. Моментум продолжается.",
        "{symbol} растёт {pnl}%\nТы уже в {symbol}. Позиция растёт.",
        "{symbol} {pnl}% — Система была права\nТы доверился сигналу. Толпа войдёт позже.",
    ],
}

PNL_NEGATIVE_MESSAGES = {
    'en': [
        "{symbol} {pnl}%\nYou're positioned. Setup weakening. Re-evaluate.",
        "{symbol} is pulling back {pnl}%\nYour {symbol} position. Invalidation approaching.",
        "{symbol} {pnl}% — Pressure on your position\nThis is where weak hands exit. Are you?",
    ],
    'ru': [
        "{symbol} {pnl}%\nТы в позиции. Сетап ослабевает. Пересмотри.",
        "{symbol} откатывается {pnl}%\nТвоя позиция {symbol}. Инвалидация приближается.",
        "{symbol} {pnl}% — Давление на твою позицию\nЗдесь слабые руки выходят. А ты?",
    ],
}


def check_pnl_triggers(user_id: str = 'dev_user') -> list[dict]:
    """
    Scan all open positions for PnL threshold crossings.
    Returns list of generated notifications.
    """
    from services.notification_engine import create_notification

    positions = list(db['portfolio_positions'].find({
        'userId': user_id,
        'status': 'OPEN',
    }))

    if not positions:
        return []

    notifications = []

    for pos in positions:
        symbol = pos.get('symbol', '')
        entry_price = pos.get('entryPrice', 0)
        if not symbol or not entry_price:
            continue

        current_price = _get_current_price(symbol)
        if current_price <= 0:
            continue

        side = pos.get('side', 'LONG')
        if side == 'LONG':
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100

        # Update position current price and PnL
        db['portfolio_positions'].update_one(
            {'_id': pos['_id']},
            {'$set': {
                'currentPrice': current_price,
                'pnlPct': round(pnl_pct, 2),
                'updatedAt': datetime.now(timezone.utc),
            }}
        )

        pnl_str = f"{pnl_pct:+.1f}"

        # POSITIVE trigger: pnl > +2%
        if pnl_pct >= 2.0:
            if _was_triggered_recently(user_id, 'PNL_POSITIVE', symbol, cooldown_hours=6):
                continue

            import random
            msg_en = random.choice(PNL_POSITIVE_MESSAGES['en']).format(symbol=symbol, pnl=pnl_str)
            msg_ru = random.choice(PNL_POSITIVE_MESSAGES['ru']).format(symbol=symbol, pnl=pnl_str)

            lines_en = msg_en.split('\n')
            lines_ru = msg_ru.split('\n')

            nid = create_notification(
                ntype='PNL_ALERT',
                title_en=lines_en[0],
                title_ru=lines_ru[0],
                body_en=lines_en[1] if len(lines_en) > 1 else '',
                body_ru=lines_ru[1] if len(lines_ru) > 1 else '',
                data={
                    'symbol': symbol,
                    'pnlPct': round(pnl_pct, 2),
                    'currentPrice': current_price,
                    'side': side,
                    'screen': 'portfolio',
                    'triggerType': 'PNL_POSITIVE',
                },
                priority='HIGH',
                icon='trending-up',
            )
            _log_trigger(user_id, 'PNL_POSITIVE', symbol, {'pnlPct': round(pnl_pct, 2), 'notificationId': nid})
            notifications.append({'type': 'PNL_POSITIVE', 'symbol': symbol, 'pnl': round(pnl_pct, 2), 'nid': nid})
            logger.info(f"PNL_POSITIVE trigger: {symbol} {pnl_str}% for {user_id}")

        # NEGATIVE trigger: pnl < -1.5%
        elif pnl_pct <= -1.5:
            if _was_triggered_recently(user_id, 'PNL_NEGATIVE', symbol, cooldown_hours=4):
                continue

            import random
            msg_en = random.choice(PNL_NEGATIVE_MESSAGES['en']).format(symbol=symbol, pnl=pnl_str)
            msg_ru = random.choice(PNL_NEGATIVE_MESSAGES['ru']).format(symbol=symbol, pnl=pnl_str)

            lines_en = msg_en.split('\n')
            lines_ru = msg_ru.split('\n')

            nid = create_notification(
                ntype='PNL_ALERT',
                title_en=lines_en[0],
                title_ru=lines_ru[0],
                body_en=lines_en[1] if len(lines_en) > 1 else '',
                body_ru=lines_ru[1] if len(lines_ru) > 1 else '',
                data={
                    'symbol': symbol,
                    'pnlPct': round(pnl_pct, 2),
                    'currentPrice': current_price,
                    'side': side,
                    'screen': 'portfolio',
                    'triggerType': 'PNL_NEGATIVE',
                },
                priority='HIGH',
                icon='trending-down',
            )
            _log_trigger(user_id, 'PNL_NEGATIVE', symbol, {'pnlPct': round(pnl_pct, 2), 'notificationId': nid})
            notifications.append({'type': 'PNL_NEGATIVE', 'symbol': symbol, 'pnl': round(pnl_pct, 2), 'nid': nid})
            logger.info(f"PNL_NEGATIVE trigger: {symbol} {pnl_str}% for {user_id}")

    return notifications


def check_portfolio_aggregate_trigger(user_id: str = 'dev_user') -> list[dict]:
    """
    Portfolio-level aggregate push: "Your portfolio +2.1% today. BTC is leading."
    Fires once per day when total PnL crosses a threshold.
    """
    from services.notification_engine import create_notification
    from services.portfolio_service import get_performance

    if _was_triggered_recently(user_id, 'PORTFOLIO_MOVED', 'ALL', cooldown_hours=12):
        return []

    perf = get_performance(user_id)
    if not perf.get('ok') or not perf.get('positions'):
        return []

    total_pnl = perf.get('totalPnlPct', 0)
    if abs(total_pnl) < 1.0:
        return []

    # Find leader
    positions = perf.get('positions', [])
    sorted_pos = sorted(positions, key=lambda p: abs(p.get('pnlPct', 0)), reverse=True)
    leader = sorted_pos[0] if sorted_pos else None
    leader_sym = leader.get('symbol', '') if leader else ''
    leader_pnl = leader.get('pnlPct', 0) if leader else 0

    if total_pnl > 0:
        title_en = f"Your portfolio +{total_pnl:.1f}% today"
        title_ru = f"Твой портфель +{total_pnl:.1f}% сегодня"
        body_en = f"{leader_sym} is leading." if leader_sym else "All positions green."
        body_ru = f"{leader_sym} лидирует." if leader_sym else "Все позиции в плюсе."
        icon = 'trending-up'
    else:
        title_en = f"Your portfolio {total_pnl:.1f}% today"
        title_ru = f"Твой портфель {total_pnl:.1f}% сегодня"
        body_en = f"{leader_sym} under pressure." if leader_sym else "Review your positions."
        body_ru = f"{leader_sym} под давлением." if leader_sym else "Пересмотри позиции."
        icon = 'trending-down'

    nid = create_notification(
        ntype='PNL_ALERT',
        title_en=title_en, title_ru=title_ru,
        body_en=body_en, body_ru=body_ru,
        data={
            'totalPnlPct': round(total_pnl, 2),
            'leaderSymbol': leader_sym,
            'leaderPnl': round(leader_pnl, 2),
            'screen': 'portfolio',
            'triggerType': 'PORTFOLIO_MOVED',
        },
        priority='HIGH', icon=icon,
    )
    _log_trigger(user_id, 'PORTFOLIO_MOVED', 'ALL', {'totalPnlPct': round(total_pnl, 2), 'notificationId': nid})
    logger.info(f"PORTFOLIO_MOVED trigger: total={total_pnl:.1f}% leader={leader_sym} for {user_id}")
    return [{'type': 'PORTFOLIO_MOVED', 'totalPnl': round(total_pnl, 2), 'leader': leader_sym, 'nid': nid}]


# ═══════════════════════════════════════
#  2. EDGE TRIGGERS
# ═══════════════════════════════════════

EDGE_MESSAGES = {
    'en': [
        "🚨 {symbol} SIGNAL\n{symbol} setup active — entry forming now\nMost users will enter late\n→ Open full entry",
        "⚡ {symbol} is moving\nEntry forming right now\nExpected upside ahead\n→ Get exact entry",
        "🔥 LIVE SIGNAL ({symbol})\n{symbol} entry confirming — confidence {confidence}%\nPRO users already inside\n→ See entry",
    ],
    'ru': [
        "🚨 {symbol} СИГНАЛ\nСетап {symbol} активен — вход формируется\nБольшинство войдут поздно\n→ Открыть вход",
        "⚡ {symbol} двигается\nВход формируется прямо сейчас\nОжидаемый рост впереди\n→ Смотреть вход",
        "🔥 LIVE SIGNAL ({symbol})\nВход {symbol} подтверждается — уверенность {confidence}%\nPRO уже внутри\n→ Смотреть вход",
    ],
}


def check_edge_triggers(user_id: str = 'dev_user') -> list[dict]:
    """
    Scan for edge/signal changes that should trigger notifications.
    Checks: new edges, confidence jumps, signal direction changes.
    """
    from services.notification_engine import create_notification

    notifications = []

    # Check edge_opportunities for recent high-confidence edges
    try:
        from services.edge_opportunities import generate_edge_opportunities
        edges = generate_edge_opportunities()
    except Exception:
        edges = []

    for edge in edges:
        if edge.get('confidence', 0) < 65:
            continue

        symbol = edge.get('asset', '')
        if not symbol:
            continue

        if _was_triggered_recently(user_id, 'EDGE_ALERT', symbol, cooldown_hours=8):
            continue

        conf = edge.get('confidence', 0)
        import random
        msg_en = random.choice(EDGE_MESSAGES['en']).format(symbol=symbol, confidence=conf)
        msg_ru = random.choice(EDGE_MESSAGES['ru']).format(symbol=symbol, confidence=conf)

        lines_en = msg_en.split('\n')
        lines_ru = msg_ru.split('\n')

        nid = create_notification(
            ntype='EDGE',
            title_en=lines_en[0],
            title_ru=lines_ru[0],
            body_en=lines_en[1] if len(lines_en) > 1 else '',
            body_ru=lines_ru[1] if len(lines_ru) > 1 else '',
            data={
                'symbol': symbol,
                'confidence': conf,
                'edgeType': edge.get('type', 'edge'),
                'screen': 'edge',
                'triggerType': 'EDGE_ALERT',
            },
            priority='HIGH',
            icon='flash',
        )
        _log_trigger(user_id, 'EDGE_ALERT', symbol, {'confidence': conf, 'notificationId': nid})
        notifications.append({'type': 'EDGE_ALERT', 'symbol': symbol, 'confidence': conf, 'nid': nid})
        logger.info(f"EDGE_ALERT trigger: {symbol} conf={conf}% for {user_id}")

    return notifications


# ═══════════════════════════════════════
#  3. WATCHLIST TRIGGERS
# ═══════════════════════════════════════

WATCHLIST_MESSAGES = {
    'en': [
        "⚠️ {symbol} is moving +{change}%\nYou've been watching this\nSetup is active now\n→ See entry",
        "🔥 {symbol} +{change}%\nThe asset you tracked is breaking out\nDon't miss this one\n→ Open signal",
        "⚡ {symbol} waking up +{change}%\nRemember when you added this?\nIt's time.\n→ Continue in app",
    ],
    'ru': [
        "⚠️ {symbol} двигается +{change}%\nТы следил за этим\nСетап активен\n→ Смотреть вход",
        "🔥 {symbol} +{change}%\nАктив который ты отслеживал пробивается\nНе пропусти\n→ Открыть сигнал",
        "⚡ {symbol} просыпается +{change}%\nПомнишь? Ты добавил это.\nВремя пришло.\n→ Открыть в аппе",
    ],
}


def check_watchlist_triggers(user_id: str = 'dev_user') -> list[dict]:
    """
    Scan watchlist assets for significant movements.
    Trigger when watchlist asset moves > +3% in 24h.
    """
    from services.notification_engine import create_notification
    from services.asset_intelligence import get_watchlist

    watchlist = get_watchlist(user_id)
    if not watchlist:
        return []

    notifications = []

    for symbol in watchlist:
        if _was_triggered_recently(user_id, 'WATCHLIST_ALERT', symbol, cooldown_hours=12):
            continue

        # Get price data from meta_brain
        brain = db.get_collection('meta_brain')
        doc = brain.find_one({'symbol': symbol.upper()}, sort=[('timestamp', -1)])
        if not doc:
            continue

        change_24h = doc.get('change24h', 0)
        price = doc.get('price', 0)

        # Only trigger for significant moves
        if abs(change_24h) < 3.0:
            continue

        change_str = f"{change_24h:+.1f}"
        import random
        msg_en = random.choice(WATCHLIST_MESSAGES['en']).format(symbol=symbol, change=change_str)
        msg_ru = random.choice(WATCHLIST_MESSAGES['ru']).format(symbol=symbol, change=change_str)

        lines_en = msg_en.split('\n')
        lines_ru = msg_ru.split('\n')

        nid = create_notification(
            ntype='WATCHLIST_ALERT',
            title_en=lines_en[0],
            title_ru=lines_ru[0],
            body_en=lines_en[1] if len(lines_en) > 1 else '',
            body_ru=lines_ru[1] if len(lines_ru) > 1 else '',
            data={
                'symbol': symbol,
                'change24h': round(change_24h, 2),
                'price': price,
                'screen': 'feed',
                'triggerType': 'WATCHLIST_ALERT',
            },
            priority='HIGH',
            icon='eye',
        )
        _log_trigger(user_id, 'WATCHLIST_ALERT', symbol, {'change24h': round(change_24h, 2), 'notificationId': nid})
        notifications.append({'type': 'WATCHLIST_ALERT', 'symbol': symbol, 'change24h': round(change_24h, 2), 'nid': nid})
        logger.info(f"WATCHLIST_ALERT trigger: {symbol} {change_str}% for {user_id}")

    return notifications


# ═══════════════════════════════════════
#  5. REGRET TRIGGERS (самый сильный рычаг)
# ═══════════════════════════════════════

REGRET_MESSAGES = {
    'en': [
        "{symbol} +{change}% since you last looked\nYou saw this early. Most entered later.",
        "You ignored {symbol}\n+{change}% since then. The edge was real.",
        "{symbol} moved +{change}% after your view\nYou were right to watch it.",
    ],
    'ru': [
        "{symbol} +{change}% с момента когда ты смотрел\nТы видел это рано. Большинство вошли позже.",
        "Ты проигнорировал {symbol}\n+{change}% с тех пор. Edge был настоящим.",
        "{symbol} вырос на +{change}% после твоего просмотра\nТы правильно следил.",
    ],
}


def check_regret_triggers(user_id: str = 'dev_user') -> list[dict]:
    """
    Regret push: "You ignored SOL. +4.8% since then."
    Checks assets user viewed but didn't act on, that have since moved.
    """
    from services.notification_engine import create_notification

    notifications = []
    now = datetime.now(timezone.utc)
    events_col = db['behavior_events']

    # Find assets user viewed 12-72h ago but has no position in
    cutoff_start = now - timedelta(hours=72)
    cutoff_end = now - timedelta(hours=12)

    viewed_assets = events_col.distinct('data.symbol', {
        'userId': user_id,
        'type': {'$in': ['VIEW_ASSET', 'view_asset', 'OPEN_INTELLIGENCE', 'edge_click', 'signal_view']},
        'createdAt': {'$gte': cutoff_start, '$lte': cutoff_end},
    })

    if not viewed_assets:
        return []

    # Get open positions to exclude
    open_positions = set()
    for pos in db['portfolio_positions'].find({'userId': user_id, 'status': 'OPEN'}):
        open_positions.add(pos.get('symbol', '').upper())

    for symbol in viewed_assets:
        sym = str(symbol).upper()
        if not sym or sym in open_positions:
            continue

        if _was_triggered_recently(user_id, 'REGRET', sym, cooldown_hours=24):
            continue

        # Check if price moved since view
        current_price = _get_current_price(sym)
        if current_price <= 0:
            continue

        # Get price at time of last view
        last_view = events_col.find_one(
            {'userId': user_id, 'data.symbol': sym},
            sort=[('createdAt', -1)],
        )
        view_price = (last_view or {}).get('data', {}).get('price', 0)
        if not view_price:
            continue

        change_pct = ((current_price - float(view_price)) / float(view_price)) * 100

        # Only trigger regret for significant positive moves
        if change_pct < 3.0:
            continue

        change_str = f"{change_pct:.1f}"
        import random
        msg_en = random.choice(REGRET_MESSAGES['en']).format(symbol=sym, change=change_str)
        msg_ru = random.choice(REGRET_MESSAGES['ru']).format(symbol=sym, change=change_str)

        lines_en = msg_en.split('\n')
        lines_ru = msg_ru.split('\n')

        nid = create_notification(
            ntype='FOMO',
            title_en=lines_en[0], title_ru=lines_ru[0],
            body_en=lines_en[1] if len(lines_en) > 1 else '',
            body_ru=lines_ru[1] if len(lines_ru) > 1 else '',
            data={
                'symbol': sym, 'changeSinceView': round(change_pct, 2),
                'screen': 'edge', 'triggerType': 'REGRET',
            },
            priority='HIGH', icon='alert-circle',
        )
        _log_trigger(user_id, 'REGRET', sym, {'change': round(change_pct, 2), 'notificationId': nid})
        notifications.append({'type': 'REGRET', 'symbol': sym, 'change': round(change_pct, 2), 'nid': nid})
        logger.info(f"REGRET trigger: {sym} +{change_str}% for {user_id}")

    return notifications


# ═══════════════════════════════════════
#  6. STATE-BASED TRIGGERS
# ═══════════════════════════════════════

STATE_MESSAGES = {
    'DORMANT': {
        'en': ["Your portfolio changed\n{leader} is now {direction}.", "Market shifted while you were away\nCheck your positions."],
        'ru': ["Твой портфель изменился\n{leader} теперь {direction}.", "Рынок сдвинулся пока тебя не было\nПроверь свои позиции."],
    },
    'SLEEPING': {
        'en': ["Market moved without you\nYou missed {count} edges.", "{count} setups formed while you were away\nThe market doesn't wait."],
        'ru': ["Рынок двигался без тебя\nТы пропустил {count} edge.", "{count} сетапов сформировались пока тебя не было\nРынок не ждёт."],
    },
    'CHURN_RISK': {
        'en': ["You used to catch these early\nNow you're late.", "The market keeps moving\nYour edge is fading."],
        'ru': ["Раньше ты ловил это рано\nТеперь ты опаздываешь.", "Рынок продолжает двигаться\nТвой edge угасает."],
    },
}


def check_state_triggers(user_id: str = 'dev_user') -> list[dict]:
    """
    State-based pushes based on user engagement state.
    DORMANT → PnL update
    SLEEPING → missed edges
    CHURN_RISK → strongest reactivation
    """
    from services.notification_engine import create_notification
    from services.affinity_service import compute_user_state

    state_info = compute_user_state(user_id)
    state = state_info.get('state', 'ACTIVE')

    if state == 'ACTIVE' or state == 'NEW':
        return []

    if _was_triggered_recently(user_id, f'STATE_{state}', 'ALL', cooldown_hours=24):
        return []

    notifications = []

    if state == 'DORMANT':
        # Get portfolio leader
        try:
            from services.portfolio_service import get_performance
            perf = get_performance(user_id)
            positions = perf.get('positions', [])
            if positions:
                leader = max(positions, key=lambda p: abs(p.get('pnlPct', 0)))
                leader_sym = leader.get('symbol', 'BTC')
                leader_pnl = leader.get('pnlPct', 0)
                direction = f"up {leader_pnl:+.1f}%" if leader_pnl >= 0 else f"down {leader_pnl:.1f}%"
            else:
                leader_sym = 'BTC'
                direction = 'moving'
        except Exception:
            leader_sym = 'BTC'
            direction = 'moving'

        import random
        msgs = STATE_MESSAGES['DORMANT']
        msg_en = random.choice(msgs['en']).format(leader=leader_sym, direction=direction)
        msg_ru = random.choice(msgs['ru']).format(leader=leader_sym, direction=direction)

    elif state == 'SLEEPING':
        # Count recent edges
        try:
            from services.edge_opportunities import generate_edge_opportunities
            edges = generate_edge_opportunities()
            count = len(edges)
        except Exception:
            count = 3

        import random
        msgs = STATE_MESSAGES['SLEEPING']
        msg_en = random.choice(msgs['en']).format(count=count)
        msg_ru = random.choice(msgs['ru']).format(count=count)

    elif state == 'CHURN_RISK':
        import random
        msgs = STATE_MESSAGES['CHURN_RISK']
        msg_en = random.choice(msgs['en'])
        msg_ru = random.choice(msgs['ru'])

    else:
        return []

    lines_en = msg_en.split('\n')
    lines_ru = msg_ru.split('\n')

    nid = create_notification(
        ntype='FOMO',
        title_en=lines_en[0], title_ru=lines_ru[0],
        body_en=lines_en[1] if len(lines_en) > 1 else '',
        body_ru=lines_ru[1] if len(lines_ru) > 1 else '',
        data={
            'state': state,
            'screen': 'home',
            'triggerType': f'STATE_{state}',
        },
        priority='HIGH' if state == 'CHURN_RISK' else 'MEDIUM',
        icon='alert-circle' if state == 'CHURN_RISK' else 'notifications',
    )
    _log_trigger(user_id, f'STATE_{state}', 'ALL', {'state': state, 'notificationId': nid})
    notifications.append({'type': f'STATE_{state}', 'state': state, 'nid': nid})
    logger.info(f"STATE_{state} trigger for {user_id}")

    return notifications


# ═══════════════════════════════════════
#  MASTER TRIGGER CHECK
# ═══════════════════════════════════════

def run_all_triggers(user_id: str = 'dev_user') -> dict:
    """
    Run all trigger checks for a user.
    Called periodically by the background scheduler.
    """
    results = {
        'pnl': [],
        'edge': [],
        'watchlist': [],
        'portfolio': [],
        'totalGenerated': 0,
        'checkedAt': datetime.now(timezone.utc).isoformat(),
    }

    try:
        results['pnl'] = check_pnl_triggers(user_id)
    except Exception as e:
        logger.error(f"PnL trigger error for {user_id}: {e}")

    try:
        results['portfolio'] = check_portfolio_aggregate_trigger(user_id)
    except Exception as e:
        logger.error(f"Portfolio aggregate trigger error for {user_id}: {e}")

    try:
        results['edge'] = check_edge_triggers(user_id)
    except Exception as e:
        logger.error(f"Edge trigger error for {user_id}: {e}")

    try:
        results['watchlist'] = check_watchlist_triggers(user_id)
    except Exception as e:
        logger.error(f"Watchlist trigger error for {user_id}: {e}")

    results['totalGenerated'] = len(results['pnl']) + len(results['edge']) + len(results['watchlist']) + len(results['portfolio'])

    # State-based & regret pushes
    try:
        results['regret'] = check_regret_triggers(user_id)
        results['totalGenerated'] += len(results['regret'])
    except Exception as e:
        logger.error(f"Regret trigger error for {user_id}: {e}")

    try:
        results['state'] = check_state_triggers(user_id)
        results['totalGenerated'] += len(results['state'])
    except Exception as e:
        logger.error(f"State trigger error for {user_id}: {e}")

    return results


def run_all_triggers_all_users() -> dict:
    """Run triggers for all users with open positions or watchlists."""
    users_col = db['users']
    positions_col = db['portfolio_positions']

    # Find all unique userIds with open positions
    user_ids = set()

    # Users with open positions
    for doc in positions_col.distinct('userId', {'status': 'OPEN'}):
        user_ids.add(doc)

    # Also check default dev_user
    user_ids.add('dev_user')

    total = {'users_checked': 0, 'total_notifications': 0, 'details': []}

    for uid in user_ids:
        result = run_all_triggers(uid)
        total['users_checked'] += 1
        total['total_notifications'] += result['totalGenerated']
        if result['totalGenerated'] > 0:
            total['details'].append({'userId': uid, **result})

    total['checkedAt'] = datetime.now(timezone.utc).isoformat()
    return total


# ═══════════════════════════════════════
#  MANUAL PUSH SEND (API endpoint)
# ═══════════════════════════════════════

def send_manual_push(
    user_id: str,
    push_type: str,
    symbol: str,
    pnl: float = None,
    message: str = None,
) -> dict:
    """
    Manual push send via API.
    POST /api/mobile/push/send
    """
    from services.notification_engine import create_notification

    if push_type == 'PNL_ALERT':
        pnl_str = f"{pnl:+.1f}" if pnl else "+0.0"
        if pnl and pnl >= 0:
            title_en = f"{symbol} {pnl_str}%"
            title_ru = f"{symbol} {pnl_str}%"
            body_en = message or "Momentum continues. Don't lose the move."
            body_ru = message or "Моментум продолжается. Не теряй движение."
            icon = 'trending-up'
        else:
            title_en = f"{symbol} {pnl_str}%"
            title_ru = f"{symbol} {pnl_str}%"
            body_en = message or "Setup weakening. Re-evaluate your position."
            body_ru = message or "Сетап ослабевает. Пересмотри позицию."
            icon = 'trending-down'

        nid = create_notification(
            ntype='PNL_ALERT',
            title_en=title_en, title_ru=title_ru,
            body_en=body_en, body_ru=body_ru,
            data={'symbol': symbol, 'pnlPct': pnl, 'screen': 'portfolio', 'triggerType': 'PNL_ALERT'},
            priority='HIGH', icon=icon,
        )

    elif push_type == 'EDGE_ALERT':
        title_en = f"{symbol} setup evolving"
        title_ru = f"{symbol} — сетап развивается"
        body_en = message or "Entry forming again."
        body_ru = message or "Вход формируется снова."
        nid = create_notification(
            ntype='EDGE',
            title_en=title_en, title_ru=title_ru,
            body_en=body_en, body_ru=body_ru,
            data={'symbol': symbol, 'screen': 'edge', 'triggerType': 'EDGE_ALERT'},
            priority='HIGH', icon='flash',
        )

    elif push_type == 'WATCHLIST_ALERT':
        title_en = f"{symbol} is heating up"
        title_ru = f"{symbol} разогревается"
        body_en = message or "You added this earlier. Now it's moving."
        body_ru = message or "Ты добавил это раньше. Теперь оно двигается."
        nid = create_notification(
            ntype='WATCHLIST_ALERT',
            title_en=title_en, title_ru=title_ru,
            body_en=body_en, body_ru=body_ru,
            data={'symbol': symbol, 'screen': 'feed', 'triggerType': 'WATCHLIST_ALERT'},
            priority='HIGH', icon='eye',
        )

    else:
        title_en = f"{symbol} alert"
        title_ru = f"{symbol} — оповещение"
        body_en = message or "Something happened."
        body_ru = message or "Произошло событие."
        nid = create_notification(
            ntype='SIGNAL',
            title_en=title_en, title_ru=title_ru,
            body_en=body_en, body_ru=body_ru,
            data={'symbol': symbol, 'screen': 'home'},
            priority='MEDIUM', icon='notifications',
        )

    return {'ok': True, 'notificationId': nid, 'type': push_type, 'symbol': symbol}



# ═══════════════════════════════════════
#  4. TELEGRAM SEQUENCE RUNNER
# ═══════════════════════════════════════

def run_sequence_step():
    """
    Check for pending Telegram sequence messages and fire them.
    Called by the background loop every 60s.
    """
    from services.telegram_sequences import get_pending_sequence_messages, mark_sequence_fired
    from services.notification_engine import create_notification

    pending = get_pending_sequence_messages()
    fired = 0

    for msg in pending:
        try:
            lines_en = msg.get("message_en", "").split("\n")
            lines_ru = msg.get("message_ru", "").split("\n")

            title_en = lines_en[0] if lines_en else "Signal update"
            title_ru = lines_ru[0] if lines_ru else "Обновление сигнала"
            body_en = "\n".join(lines_en[1:4]) if len(lines_en) > 1 else ""
            body_ru = "\n".join(lines_ru[1:4]) if len(lines_ru) > 1 else ""

            create_notification(
                ntype='SEQUENCE',
                title_en=title_en, title_ru=title_ru,
                body_en=body_en, body_ru=body_ru,
                data={
                    'symbol': msg.get("asset", ""),
                    'step': msg.get("step", 0),
                    'sequenceId': msg.get("sequenceId", ""),
                    'screen': 'signal',
                    'triggerType': 'SEQUENCE',
                },
                priority='HIGH',
                icon='flash',
            )
            mark_sequence_fired(msg["_id"])
            fired += 1
            logger.info(f"[Sequence] Fired step {msg.get('step')} for {msg.get('asset')}")
        except Exception as e:
            logger.error(f"[Sequence] Error firing: {e}")

    return {"fired": fired, "pending": len(pending)}


# ═══════════════════════════════════════
#  5. MISSED PROFIT CHECKER
# ═══════════════════════════════════════

def check_missed_profit_triggers(user_id: str = 'dev_user') -> list:
    """
    Check for resolved signals where user didn't act → regret message.
    """
    from services.telegram_sequences import check_missed_profits
    from services.notification_engine import create_notification

    missed = check_missed_profits()
    notifications = []

    for m in missed[:2]:
        asset = m["asset"]
        pnl = m["pnl"]

        if _was_triggered_recently(user_id, 'MISSED_PROFIT', asset, cooldown_hours=24):
            continue

        nid = create_notification(
            ntype='MISSED',
            title_en=f"You saw this — {asset} moved +{pnl:.1f}%",
            title_ru=f"Ты это видел — {asset} двинулся +{pnl:.1f}%",
            body_en=f"Next setup is forming. Don't miss again.",
            body_ru=f"Следующий сетап формируется. Не пропусти.",
            data={
                'symbol': asset,
                'pnl': pnl,
                'screen': 'signal',
                'triggerType': 'MISSED_PROFIT',
            },
            priority='HIGH',
            icon='alert-circle',
        )
        _log_trigger(user_id, 'MISSED_PROFIT', asset, {'pnl': pnl, 'notificationId': nid})
        notifications.append({'type': 'MISSED_PROFIT', 'symbol': asset, 'pnl': pnl, 'nid': nid})
        logger.info(f"MISSED_PROFIT trigger: {asset} +{pnl:.1f}% for {user_id}")

    return notifications
