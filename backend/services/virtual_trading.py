"""
Virtual Trading Service — Paper trading with real signal data.

Positions tracked in MongoDB. PnL calculated from real CoinGecko prices.
"""

import os
import logging
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

positions_col = db['virtual_positions']
positions_col.create_index([('userId', 1), ('status', 1)])
positions_col.create_index([('userId', 1), ('createdAt', DESCENDING)])


def _get_current_price(asset: str) -> float:
    """Get latest price from observations."""
    obs = db.observations.find_one(
        {'symbol': asset.upper()},
        {'_id': 0, 'price': 1},
        sort=[('timestamp', DESCENDING)],
    )
    if obs and obs.get('price'):
        return obs['price']
    # Fallback to exchange_forecasts
    fc = db.exchange_forecasts.find_one(
        {'asset': asset.upper()},
        {'_id': 0, 'entry': 1},
        sort=[('createdAt', DESCENDING)],
    )
    return fc.get('entry', 0) if fc else 0


def open_position(
    user_id: str, asset: str, action: str,
    entry_price: float = None, confidence: float = None,
    source: str = 'manual',
) -> dict:
    """Open a virtual position."""
    if not entry_price:
        entry_price = _get_current_price(asset)
    if not entry_price:
        return {'ok': False, 'error': 'Cannot determine entry price'}

    # Check if already has open position for this asset
    existing = positions_col.find_one({
        'userId': user_id,
        'asset': asset.upper(),
        'status': 'OPEN',
    })
    if existing:
        return {'ok': False, 'error': f'Already have open {asset} position'}

    pos_id = f"pos_{uuid.uuid4().hex[:10]}"
    doc = {
        '_id': pos_id,
        'userId': user_id,
        'asset': asset.upper(),
        'action': action.upper(),  # BUY or SELL
        'entryPrice': entry_price,
        'currentPrice': entry_price,
        'pnlPct': 0.0,
        'pnlUsd': 0.0,
        'confidence': confidence or 0,
        'source': source,
        'status': 'OPEN',
        'createdAt': datetime.now(timezone.utc),
        'closedAt': None,
        'closePrice': None,
    }
    positions_col.insert_one(doc)
    doc.pop('_id')
    doc['id'] = pos_id
    doc['createdAt'] = doc['createdAt'].isoformat()
    return {'ok': True, 'position': doc}


def close_position(user_id: str, position_id: str) -> dict:
    """Close a virtual position."""
    pos = positions_col.find_one({'_id': position_id, 'userId': user_id})
    if not pos:
        return {'ok': False, 'error': 'Position not found'}
    if pos['status'] != 'OPEN':
        return {'ok': False, 'error': 'Position already closed'}

    close_price = _get_current_price(pos['asset'])
    if not close_price:
        close_price = pos['entryPrice']

    entry = pos['entryPrice']
    if pos['action'] == 'BUY':
        pnl_pct = ((close_price - entry) / entry) * 100
    else:
        pnl_pct = ((entry - close_price) / entry) * 100
    pnl_usd = (close_price - entry) if pos['action'] == 'BUY' else (entry - close_price)

    positions_col.update_one(
        {'_id': position_id},
        {'$set': {
            'status': 'CLOSED',
            'closePrice': close_price,
            'currentPrice': close_price,
            'pnlPct': round(pnl_pct, 2),
            'pnlUsd': round(pnl_usd, 2),
            'closedAt': datetime.now(timezone.utc),
        }},
    )
    return {
        'ok': True,
        'pnlPct': round(pnl_pct, 2),
        'closePrice': close_price,
    }


def get_positions(user_id: str, status: str = 'OPEN') -> list:
    """Get user positions."""
    query = {'userId': user_id}
    if status:
        query['status'] = status

    positions = list(positions_col.find(
        query, {'_id': 0}
    ).sort('createdAt', DESCENDING).limit(20))

    # Update current prices for open positions
    for pos in positions:
        if pos['status'] == 'OPEN':
            cp = _get_current_price(pos['asset'])
            if cp:
                entry = pos['entryPrice']
                if pos['action'] == 'BUY':
                    pnl = ((cp - entry) / entry) * 100
                else:
                    pnl = ((entry - cp) / entry) * 100
                pos['currentPrice'] = cp
                pos['pnlPct'] = round(pnl, 2)
        if isinstance(pos.get('createdAt'), datetime):
            pos['createdAt'] = pos['createdAt'].isoformat()
        if isinstance(pos.get('closedAt'), datetime):
            pos['closedAt'] = pos['closedAt'].isoformat()

    return positions


def get_portfolio_summary(user_id: str) -> dict:
    """Get portfolio summary."""
    open_pos = get_positions(user_id, 'OPEN')
    closed = get_positions(user_id, 'CLOSED')

    total_pnl = sum(p.get('pnlPct', 0) for p in closed)
    wins = sum(1 for p in closed if p.get('pnlPct', 0) > 0)
    total_closed = len(closed)

    return {
        'openPositions': len(open_pos),
        'closedPositions': total_closed,
        'totalPnlPct': round(total_pnl, 2),
        'winRate': round(wins / total_closed * 100, 1) if total_closed > 0 else 0,
        'positions': open_pos,
    }
