"""Home & History routes."""
from fastapi import APIRouter, Query, Depends
from routes.auth import get_optional_user
from services.home_service import get_home as home_service_get_home
from services.ingestion import ensure_fresh_data, get_latest_observation
from services.asset_registry import normalize_symbol
from services.signal_history import (
    get_latest_closed, get_stats, get_open_signal,
    resolve_expired_signals, seed_history_if_empty,
    get_missed_signals,
)

router = APIRouter()


@router.get("/home")
async def get_home(asset: str = Query(default="BTC"), user=Depends(get_optional_user)):
    return await home_service_get_home(asset, user)


@router.get("/history")
async def get_signal_history(asset: str = Query(default="BTC")):
    asset_key = normalize_symbol(asset)

    obs = await ensure_fresh_data(asset_key, max_age_seconds=300)
    if obs:
        seed_history_if_empty(asset_key, obs['price'])
        current_prices = {}
        for a in ('BTC', 'ETH', 'SOL'):
            o = get_latest_observation(a)
            if o and 'price' in o:
                current_prices[a] = o['price']
        resolve_expired_signals(current_prices)

    stats = get_stats(asset_key)
    items = get_latest_closed(asset_key, limit=10)
    current_signal = get_open_signal(asset_key)

    formatted_items = []
    for item in items:
        if item.get('entryTs') and item.get('closeTs'):
            delta = item['closeTs'] - item['entryTs']
            hours = delta.total_seconds() / 3600
            if hours < 1:
                duration = f"{int(delta.total_seconds() / 60)}m"
            elif hours < 24:
                duration = f"{hours:.1f}h"
            else:
                duration = f"{hours / 24:.1f}d"
        else:
            duration = item.get('horizon', 'N/A')

        formatted_items.append({
            'action': item.get('action'),
            'confidence': item.get('confidence'),
            'entryPrice': item.get('entryPrice'),
            'closePrice': item.get('closePrice'),
            'pnlPct': item.get('pnlPct'),
            'outcome': item.get('outcome'),
            'duration': duration,
            'closedAt': item.get('closeTs').isoformat() if item.get('closeTs') else None,
            'horizon': item.get('horizon'),
        })

    return {
        'asset': asset_key,
        'stats': stats,
        'items': formatted_items,
        'missedSignals': get_missed_signals(limit=3),
        'currentSignal': {
            'action': current_signal.get('action'),
            'confidence': current_signal.get('confidence'),
            'entryPrice': current_signal.get('entryPrice'),
            'openedAt': current_signal.get('entryTs').isoformat() if current_signal and current_signal.get('entryTs') else None,
            'horizon': current_signal.get('horizon'),
        } if current_signal else None,
    }
