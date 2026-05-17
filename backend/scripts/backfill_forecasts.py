"""
Forecast Backfill Script
========================
Generates 120 days of historical forecasts for 1D, 7D, 30D horizons
using real BTC price data. Each forecast is immutable — only outcome
fields are set after evaluation.

Architecture:
  Historical Prices → Forecast Generator → exchange_forecasts (append-only)
  → Evaluation Worker → outcome update (only outcome field)

Run once to populate historical data, then daily cron for new forecasts.
"""

import json
import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = 'intelligence_engine'
COLLECTION = 'exchange_forecasts'

HORIZONS = {
    '24H': timedelta(days=1),
    '7D': timedelta(days=7),
    '30D': timedelta(days=30),
}


def load_prices():
    with open('/tmp/btc_prices_150d.json') as f:
        return json.load(f)


def price_at_date(prices_by_date, target_date_str):
    """Get close price at a specific date, or nearest before it."""
    if target_date_str in prices_by_date:
        return prices_by_date[target_date_str]['close']
    # Find nearest earlier date
    sorted_dates = sorted(prices_by_date.keys())
    for d in reversed(sorted_dates):
        if d <= target_date_str:
            return prices_by_date[d]['close']
    return None


def compute_features(prices_by_date, date_str, lookback=14):
    """Compute simple features from price history for forecast generation."""
    sorted_dates = sorted(d for d in prices_by_date if d <= date_str)
    if len(sorted_dates) < lookback:
        return None

    recent = sorted_dates[-lookback:]
    closes = [prices_by_date[d]['close'] for d in recent]
    volumes = [prices_by_date[d]['volume'] for d in recent]

    current = closes[-1]
    ret_1d = (closes[-1] - closes[-2]) / closes[-2] if len(closes) >= 2 else 0
    ret_7d = (closes[-1] - closes[-8]) / closes[-8] if len(closes) >= 8 else 0
    ret_14d = (closes[-1] - closes[0]) / closes[0]

    # Simple volatility (std of daily returns)
    daily_returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
    volatility = (sum(r**2 for r in daily_returns) / len(daily_returns)) ** 0.5

    # Volume trend
    vol_recent = sum(volumes[-3:]) / 3
    vol_older = sum(volumes[-7:-3]) / 4 if len(volumes) >= 7 else vol_recent
    vol_ratio = vol_recent / vol_older if vol_older > 0 else 1

    # Momentum (EMA-like)
    momentum = ret_1d * 0.5 + ret_7d * 0.3 + ret_14d * 0.2

    return {
        'price': current,
        'ret_1d': ret_1d,
        'ret_7d': ret_7d,
        'ret_14d': ret_14d,
        'volatility': volatility,
        'vol_ratio': vol_ratio,
        'momentum': momentum,
    }


def generate_forecast(features, horizon_key, date_str, ts_ms):
    """Generate a deterministic forecast based on features.
    Uses a hash of date+horizon for reproducibility (same inputs = same output).
    """
    # Deterministic seed from date + horizon
    seed_str = f"{date_str}:{horizon_key}:BTCUSDT:v1.1.0"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)

    price = features['price']
    momentum = features['momentum']
    vol = features['volatility']
    vol_ratio = features['vol_ratio']

    # Direction logic based on momentum + volume
    bull_score = 0.5
    bull_score += momentum * 8  # momentum drives direction
    bull_score += (vol_ratio - 1) * 0.3  # volume expansion is slightly bullish
    bull_score = max(0.05, min(0.95, bull_score))

    # Use seed for consistent small perturbation (not random)
    perturbation = ((seed % 1000) / 1000 - 0.5) * 0.1
    bull_score += perturbation

    if bull_score > 0.58:
        direction = 'UP'
    elif bull_score < 0.42:
        direction = 'DOWN'
    else:
        direction = 'NEUTRAL'

    # Confidence based on signal strength + volatility regime
    signal_strength = abs(bull_score - 0.5) * 2
    confidence_raw = 0.3 + signal_strength * 0.5
    # Higher vol = lower confidence
    vol_penalty = min(vol * 15, 0.3)
    confidence = max(0.1, min(0.9, confidence_raw - vol_penalty))

    # Target price
    horizon_td = HORIZONS[horizon_key]
    horizon_days = horizon_td.days
    # Expected move scales with horizon
    base_move = momentum * (horizon_days ** 0.5) * 0.8
    # Clamp to realistic range
    if direction == 'UP':
        expected_move_pct = max(0.5, min(12, abs(base_move) * 100 + 0.5))
    elif direction == 'DOWN':
        expected_move_pct = max(0.5, min(12, abs(base_move) * 100 + 0.5))
        expected_move_pct = -expected_move_pct
    else:
        expected_move_pct = base_move * 100 * 0.3  # Neutral = small move

    target_price = price * (1 + expected_move_pct / 100)
    band_width = vol * (horizon_days ** 0.5) * 100
    upper_band = price * (1 + band_width / 100)
    lower_band = price * (1 - band_width / 100)

    evaluate_after = ts_ms + int(horizon_td.total_seconds() * 1000)

    forecast_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, seed_str))

    return {
        'id': forecast_id,
        'asset': 'BTC',
        'symbol': 'BTCUSDT',
        'horizon': horizon_key,
        'createdAt': ts_ms,
        'evaluateAfter': evaluate_after,
        'dataWindowEnd': ts_ms,  # No future data used
        'basePrice': round(price, 2),
        'targetPrice': round(target_price, 2),
        'expectedMovePct': round(expected_move_pct, 2),
        'upperBand': round(upper_band, 2),
        'lowerBand': round(lower_band, 2),
        'bandWidthPct': round(band_width, 2),
        'direction': direction,
        'confidence': round(confidence, 4),
        'confidenceRaw': round(confidence_raw, 4),
        'strength': round(signal_strength, 4),
        'volatilitySnapshot': round(vol, 6),
        'layers': {
            'exchange': {
                'score': round(bull_score, 4),
                'contribution': 0.45,
            }
        },
        'evaluated': False,
        'outcome': None,
        'modelVersion': 'v1.1.0-backfill',
        'source': 'backfill',
        'immutableHash': hashlib.sha256(
            f"{forecast_id}:{target_price}:{direction}:{confidence}".encode()
        ).hexdigest()[:16],
    }


def evaluate_forecast(forecast, prices_by_date):
    """Evaluate a forecast against actual price at evaluateAfter."""
    eval_date = datetime.fromtimestamp(forecast['evaluateAfter'] / 1000, tz=timezone.utc)
    eval_date_str = eval_date.strftime('%Y-%m-%d')

    actual_price = price_at_date(prices_by_date, eval_date_str)
    if actual_price is None:
        return None  # Can't evaluate — no price data

    entry = forecast['basePrice']
    target = forecast['targetPrice']
    direction = forecast['direction']

    real_move_pct = (actual_price - entry) / entry * 100
    deviation_pct = abs(actual_price - target) / entry * 100

    # Direction match
    if direction == 'UP':
        dir_match = actual_price > entry
    elif direction == 'DOWN':
        dir_match = actual_price < entry
    else:
        dir_match = abs(real_move_pct) < 1  # Neutral = small move

    # Target reached
    if direction == 'UP':
        target_reached = actual_price >= target
    elif direction == 'DOWN':
        target_reached = actual_price <= target
    else:
        target_reached = abs(real_move_pct) < 0.5

    # Outcome label
    if direction == 'NEUTRAL':
        label = 'WEAK' if abs(real_move_pct) < 2 else 'FN'
    elif target_reached:
        label = 'TP'
    elif dir_match:
        label = 'WEAK'
    else:
        label = 'FP' if abs(real_move_pct) > 2 else 'FN'

    return {
        'realPrice': round(actual_price, 2),
        'realMovePct': round(real_move_pct, 2),
        'deviationPct': round(deviation_pct, 2),
        'directionMatch': dir_match,
        'hit': target_reached,
        'label': label,
        'evaluatedAt': forecast['evaluateAfter'],
    }


def main():
    prices = load_prices()
    prices_by_date = {p['date']: p for p in prices}
    sorted_dates = sorted(prices_by_date.keys())

    print(f"Loaded {len(prices)} daily prices: {sorted_dates[0]} → {sorted_dates[-1]}")

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    col = db[COLLECTION]

    # Clear old backfill data (keep real forecasts)
    deleted = col.delete_many({'source': 'backfill'})
    print(f"Cleared {deleted.deleted_count} old backfill records")

    now = datetime.now(timezone.utc)
    forecasts = []

    for horizon_key, horizon_td in HORIZONS.items():
        horizon_days = horizon_td.days
        # Start from 120 days ago (or as far back as data allows)
        start_idx = max(14, 0)  # Need 14 days lookback for features

        for i in range(start_idx, len(sorted_dates)):
            date_str = sorted_dates[i]
            date_dt = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            ts_ms = int(date_dt.timestamp() * 1000)

            # Only generate if we're within 120 days
            days_ago = (now - date_dt).days
            if days_ago > 120:
                continue

            features = compute_features(prices_by_date, date_str)
            if not features:
                continue

            forecast = generate_forecast(features, horizon_key, date_str, ts_ms)

            # Evaluate if evaluateAfter is in the past
            if forecast['evaluateAfter'] <= int(now.timestamp() * 1000):
                outcome = evaluate_forecast(forecast, prices_by_date)
                if outcome:
                    forecast['evaluated'] = True
                    forecast['outcome'] = outcome

            forecasts.append(forecast)

    print(f"\nGenerated {len(forecasts)} forecasts:")
    for h in HORIZONS:
        h_forecasts = [f for f in forecasts if f['horizon'] == h]
        evaluated = [f for f in h_forecasts if f['evaluated']]
        pending = [f for f in h_forecasts if not f['evaluated']]
        tp = sum(1 for f in evaluated if f['outcome']['label'] == 'TP')
        fp = sum(1 for f in evaluated if f['outcome']['label'] == 'FP')
        weak = sum(1 for f in evaluated if f['outcome']['label'] == 'WEAK')
        fn = sum(1 for f in evaluated if f['outcome']['label'] == 'FN')
        denom = tp + fp + weak
        wr = tp / denom if denom > 0 else 0
        print(f"  {h}: {len(h_forecasts)} total, {len(evaluated)} evaluated, {len(pending)} pending")
        print(f"       TP={tp} FP={fp} WEAK={weak} FN={fn} WinRate={wr:.1%}")

    # Insert into MongoDB
    if forecasts:
        col.insert_many(forecasts)
        print(f"\nInserted {len(forecasts)} forecasts into {DB_NAME}.{COLLECTION}")

    # Verify
    total = col.count_documents({})
    backfill = col.count_documents({'source': 'backfill'})
    real = col.count_documents({'source': {'$ne': 'backfill'}})
    print(f"\nCollection stats: {total} total ({backfill} backfill + {real} real)")

    client.close()


if __name__ == '__main__':
    main()
