"""
FOMO Ingestion Service
Fetches real market data from CoinGecko API + Coinbase API fallback
Stores in MongoDB exchange_observations collection
"""
import httpx
import asyncio
import logging
import os
from datetime import datetime, timezone
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
observations = db['exchange_observations']

# Also write to intelligence_engine DB for home_service/forecast compatibility
intel_db = client['intelligence_engine']
intel_observations = intel_db['exchange_observations']

observations.create_index([('asset', 1), ('ts', -1)])
observations.create_index('ts', expireAfterSeconds=86400 * 7)
intel_observations.create_index([('asset', 1), ('ts', -1)])
intel_observations.create_index('ts', expireAfterSeconds=86400 * 7)

from services.asset_registry import get_coingecko_id, is_supported, normalize_symbol as _normalize

COINGECKO_BASE = 'https://api.coingecko.com/api/v3'
COINBASE_BASE = 'https://api.coinbase.com/v2'
COINBASE_EXCHANGE_BASE = 'https://api.exchange.coinbase.com'

# Coinbase symbol mapping
COINBASE_SYMBOLS = {
    'BTC': 'BTC-USD', 'ETH': 'ETH-USD', 'SOL': 'SOL-USD',
    'BNB': 'BNB-USD', 'XRP': 'XRP-USD', 'ADA': 'ADA-USD',
    'DOGE': 'DOGE-USD', 'LINK': 'LINK-USD', 'DOT': 'DOT-USD',
    'AVAX': 'AVAX-USD', 'MATIC': 'MATIC-USD', 'UNI': 'UNI-USD',
    'ATOM': 'ATOM-USD', 'OP': 'OP-USD', 'ARB': 'ARB-USD',
    'NEAR': 'NEAR-USD', 'FTM': 'FTM-USD', 'AAVE': 'AAVE-USD',
    'LDO': 'LDO-USD', 'ENS': 'ENS-USD', 'PEPE': 'PEPE-USD',
    'SHIB': 'SHIB-USD', 'DYDX': 'DYDX-USD', 'GRT': 'GRT-USD',
    'IMX': 'IMX-USD', 'BLUR': 'BLUR-USD',
}


async def fetch_coinbase_prices(http: httpx.AsyncClient) -> dict:
    """Fetch prices from Coinbase public API (no rate limits, no geo-blocks)"""
    prices = {}
    try:
        # Use Coinbase exchange API for ticker data
        for symbol, pair in COINBASE_SYMBOLS.items():
            try:
                r = await http.get(f'{COINBASE_EXCHANGE_BASE}/products/{pair}/ticker', timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    prices[symbol] = {
                        'price': float(data.get('price', 0)),
                        'volume': float(data.get('volume', 0)),
                        'bid': float(data.get('bid', 0)),
                        'ask': float(data.get('ask', 0)),
                    }
                await asyncio.sleep(0.15)  # Rate limit: ~6 req/sec
            except Exception:
                continue
    except Exception as e:
        logger.error(f'Coinbase batch error: {e}')
    return prices


async def fetch_coinbase_24h_stats(http: httpx.AsyncClient, pair: str) -> dict:
    """Fetch 24h stats from Coinbase for a single pair"""
    try:
        r = await http.get(f'{COINBASE_EXCHANGE_BASE}/products/{pair}/stats', timeout=5)
        if r.status_code == 200:
            data = r.json()
            return {
                'open': float(data.get('open', 0)),
                'high': float(data.get('high', 0)),
                'low': float(data.get('low', 0)),
                'volume': float(data.get('volume', 0)),
                'last': float(data.get('last', 0)),
            }
    except Exception:
        pass
    return {}


async def fetch_coingecko_detail(http: httpx.AsyncClient, cg_id: str) -> dict:
    """Fetch detailed coin data from CoinGecko"""
    try:
        r = await http.get(
            f'{COINGECKO_BASE}/coins/{cg_id}',
            params={
                'localization': 'false',
                'tickers': 'false',
                'community_data': 'false',
                'developer_data': 'false',
                'sparkline': 'false',
            }
        )
        r.raise_for_status()
        d = r.json()
        m = d.get('market_data', {})
        
        return {
            'price': m.get('current_price', {}).get('usd', 0),
            'high24h': m.get('high_24h', {}).get('usd', 0),
            'low24h': m.get('low_24h', {}).get('usd', 0),
            'change24h': m.get('price_change_percentage_24h', 0),
            'change7d': m.get('price_change_percentage_7d', 0),
            'change30d': m.get('price_change_percentage_30d', 0),
            'volume24h': m.get('total_volume', {}).get('usd', 0),
            'marketCap': m.get('market_cap', {}).get('usd', 0),
            'ath': m.get('ath', {}).get('usd', 0),
            'athChangePercent': m.get('ath_change_percentage', {}).get('usd', 0),
            'circulatingSupply': m.get('circulating_supply', 0),
            'totalSupply': m.get('total_supply', 0),
            'maxSupply': m.get('max_supply'),
            'fullyDilutedVal': m.get('fully_diluted_valuation', {}).get('usd', 0),
            'sentimentUp': d.get('sentiment_votes_up_percentage', 50),
            'sentimentDown': d.get('sentiment_votes_down_percentage', 50),
            'marketCapRank': d.get('market_cap_rank', 0),
        }
    except Exception as e:
        logger.error(f'CoinGecko detail error for {cg_id}: {e}')
        return {}


async def fetch_coingecko_prices(http: httpx.AsyncClient) -> dict:
    """Fetch quick prices for all assets in universe"""
    from services.asset_registry import get_all_assets
    try:
        ids = ','.join(a['coingecko_id'] for a in get_all_assets())
        r = await http.get(
            f'{COINGECKO_BASE}/simple/price',
            params={
                'ids': ids,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_24hr_vol': 'true',
                'include_market_cap': 'true',
            }
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f'CoinGecko prices error: {e}')
        return {}


async def fetch_all_for_symbol(asset: str) -> dict:
    """Fetch comprehensive data for a single asset"""
    key = _normalize(asset)
    if not is_supported(key):
        return {}
    cg_id = get_coingecko_id(key)
    
    async with httpx.AsyncClient(timeout=15) as http:
        detail = await fetch_coingecko_detail(http, cg_id)
    
    if not detail or detail.get('price', 0) == 0:
        return {}
    
    now = datetime.utcnow()
    price = detail['price']
    
    # Derive institutional-grade metrics from available data
    # Spread estimation from price range
    range_24h = detail.get('high24h', price) - detail.get('low24h', price)
    volatility_pct = (range_24h / price * 100) if price else 0
    
    # Synthetic spread estimation (tighter for larger cap assets)
    if detail.get('volume24h', 0) > 10_000_000_000:
        est_spread_bps = round(0.5 + (volatility_pct * 0.1), 2)
    elif detail.get('volume24h', 0) > 1_000_000_000:
        est_spread_bps = round(1.0 + (volatility_pct * 0.2), 2)
    else:
        est_spread_bps = round(2.0 + (volatility_pct * 0.3), 2)
    
    # Quality assessment
    quality = 'HIGH' if detail.get('volume24h', 0) > 5_000_000_000 else \
              'MEDIUM' if detail.get('volume24h', 0) > 500_000_000 else 'LOW'
    
    observation = {
        'asset': asset,
        'symbol': f'{asset}USDT',
        'ts': now,
        'providersUsed': ['coingecko'],
        'quality': quality,
        
        # Price
        'price': price,
        'high24h': detail.get('high24h', 0),
        'low24h': detail.get('low24h', 0),
        'change24h': round(detail.get('change24h', 0), 4),
        'change7d': round(detail.get('change7d', 0), 4),
        'change30d': round(detail.get('change30d', 0), 4),
        'volume24h': detail.get('volume24h', 0),
        'marketCap': detail.get('marketCap', 0),
        
        # Market structure
        'ath': detail.get('ath', 0),
        'athChangePercent': round(detail.get('athChangePercent', 0), 2),
        'circulatingSupply': detail.get('circulatingSupply', 0),
        'totalSupply': detail.get('totalSupply', 0),
        'maxSupply': detail.get('maxSupply'),
        'marketCapRank': detail.get('marketCapRank', 0),
        
        # Derived metrics
        'spreadBps': est_spread_bps,
        'volatility24h': round(volatility_pct, 2),
        
        # Sentiment
        'sentimentUp': detail.get('sentimentUp', 50),
        'sentimentDown': detail.get('sentimentDown', 50),
    }
    
    return observation


def store_observation(obs: dict):
    """Store observation in both main DB, intelligence_engine DB, and canonical_tokens"""
    observations.insert_one(obs.copy())
    intel_observations.insert_one(obs.copy())
    # Also update canonical_tokens — used by signals_service for prices
    asset = obs.get('asset', '')
    if asset and obs.get('price', 0) > 0:
        db.canonical_tokens.update_one(
            {"symbol": asset},
            {"$set": {
                "symbol": asset,
                "market": {
                    "current_price": obs['price'],
                    "price_change_percentage_24h": obs.get('change24h', 0),
                    "price_change_percentage_1h": obs.get('change1h', 0),
                    "price_change_percentage_7d": obs.get('change7d', 0),
                    "market_cap": obs.get('marketCap', 0),
                    "total_volume": obs.get('volume24h', 0),
                    "high_24h": obs.get('high24h', 0),
                    "low_24h": obs.get('low24h', 0),
                },
                "updatedAt": obs.get('timestamp', datetime.now(timezone.utc).isoformat()),
            }},
            upsert=True)
    logger.info(f"Stored: {obs['asset']} @ ${obs['price']:,.2f} quality={obs['quality']}")


def get_latest_observation(asset: str = 'BTC') -> dict | None:
    """Get the most recent observation for an asset"""
    doc = observations.find_one({'asset': asset}, sort=[('ts', -1)])
    if doc:
        doc['_id'] = str(doc['_id'])
    return doc


def get_recent_observations(asset: str = 'BTC', limit: int = 10) -> list:
    """Get recent observations for trend analysis"""
    docs = list(observations.find({'asset': asset}, sort=[('ts', -1)]).limit(limit))
    for d in docs:
        d['_id'] = str(d['_id'])
    return docs


async def ensure_fresh_data(asset: str = 'BTC', max_age_seconds: int = 120) -> dict | None:
    """Ensure we have fresh data, fetch if stale"""
    latest = get_latest_observation(asset)
    if latest:
        age = (datetime.utcnow() - latest['ts']).total_seconds()
        if age < max_age_seconds:
            return latest
    
    obs = await fetch_all_for_symbol(asset)
    if obs and obs.get('price', 0) > 0:
        store_observation(obs)
        obs['_id'] = str(obs.get('_id', ''))
        return obs
    return latest


async def ingest_all():
    """Fetch and store data for all tracked assets.
    Strategy: Coinbase first (no rate limits), CoinGecko as fallback.
    """
    from services.asset_registry import get_all_assets
    
    assets = get_all_assets()
    if not assets:
        logger.warning('No assets in registry')
        return
    
    id_to_symbol = {a['coingecko_id']: a['symbol'] for a in assets}
    count = 0
    now = datetime.now(timezone.utc)
    
    async with httpx.AsyncClient(timeout=30) as http:
        # ═══ PHASE 1: Coinbase (primary, no rate limits) ═══
        coinbase_prices = await fetch_coinbase_prices(http)
        
        if coinbase_prices:
            for symbol, data in coinbase_prices.items():
                price = data.get('price', 0)
                if not price or price == 0:
                    continue
                
                # Get 24h stats for this pair
                pair = COINBASE_SYMBOLS.get(symbol)
                stats_24h = await fetch_coinbase_24h_stats(http, pair) if pair else {}
                
                open_price = stats_24h.get('open', 0)
                change_24h = ((price - open_price) / open_price * 100) if open_price > 0 else 0
                
                obs = {
                    'asset': symbol,
                    'price': price,
                    'change1h': 0,
                    'change24h': round(change_24h, 2),
                    'change7d': 0,
                    'marketCap': 0,
                    'volume24h': data.get('volume', 0) * price,
                    'high24h': stats_24h.get('high', 0),
                    'low24h': stats_24h.get('low', 0),
                    'volatility': round(abs(stats_24h.get('high', 0) - stats_24h.get('low', 0)) / price * 100, 2) if price and stats_24h.get('high') else 0,
                    'quality': 'good',
                    'providersUsed': ['coinbase'],
                    'timestamp': now.isoformat(),
                }
                store_observation(obs)
                
                # Also update canonical_tokens + exchange_observations with symbol format
                sym_usdt = f'{symbol}USDT'
                db.exchange_observations.update_many(
                    {'symbol': sym_usdt},
                    {'$set': {'price': price, 'change24h': round(change_24h, 2), 'timestamp': now}},
                )
                db.canonical_tokens.update_one(
                    {'symbol': symbol},
                    {'$set': {
                        'price': price,
                        'market': {'current_price': price, 'price_change_percentage_24h': round(change_24h, 2)},
                        'updatedAt': now,
                    }},
                    upsert=True,
                )
                count += 1
                await asyncio.sleep(0.2)
            
            logger.info(f'Coinbase ingestion: {count}/{len(COINBASE_SYMBOLS)} assets updated')
        
        # ═══ PHASE 2: CoinGecko for remaining assets (with rate limit respect) ═══
        coinbase_covered = set(coinbase_prices.keys())
        missing_assets = [a for a in assets if a['symbol'] not in coinbase_covered]
        
        if missing_assets:
            ids = ','.join(a['coingecko_id'] for a in missing_assets)
            try:
                await asyncio.sleep(2)  # Rate limit buffer
                r = await http.get(
                    f'{COINGECKO_BASE}/coins/markets',
                    params={
                        'vs_currency': 'usd',
                        'ids': ids,
                        'order': 'market_cap_desc',
                        'per_page': 100,
                        'page': 1,
                        'sparkline': 'false',
                        'price_change_percentage': '1h,24h,7d',
                    }
                )
                r.raise_for_status()
                coins = r.json()
                
                for coin in coins:
                    cg_id = coin.get('id', '')
                    symbol = id_to_symbol.get(cg_id, coin.get('symbol', '').upper())
                    price = coin.get('current_price', 0)
                    if not price or price == 0:
                        continue
                    
                    obs = {
                        'asset': symbol,
                        'price': price,
                        'change1h': round(coin.get('price_change_percentage_1h_in_currency', 0) or 0, 2),
                        'change24h': round(coin.get('price_change_percentage_24h', 0) or 0, 2),
                        'change7d': round(coin.get('price_change_percentage_7d_in_currency', 0) or 0, 2),
                        'marketCap': coin.get('market_cap', 0) or 0,
                        'volume24h': coin.get('total_volume', 0) or 0,
                        'high24h': coin.get('high_24h', 0) or 0,
                        'low24h': coin.get('low_24h', 0) or 0,
                        'volatility': round(abs((coin.get('high_24h', 0) or 0) - (coin.get('low_24h', 0) or 0)) / price * 100, 2) if price else 0,
                        'quality': 'good' if (coin.get('market_cap', 0) or 0) > 1e8 else 'low',
                        'providersUsed': ['coingecko'],
                        'timestamp': now.isoformat(),
                    }
                    store_observation(obs)
                    
                    # Update canonical_tokens
                    db.canonical_tokens.update_one(
                        {'symbol': symbol},
                        {'$set': {
                            'price': price,
                            'market': {'current_price': price, 'price_change_percentage_24h': round(coin.get('price_change_percentage_24h', 0) or 0, 2)},
                            'updatedAt': now,
                        }},
                        upsert=True,
                    )
                    count += 1
                
                logger.info(f'CoinGecko supplement: {len(coins)} additional assets')
            except Exception as e:
                logger.warning(f'CoinGecko supplement failed (non-critical): {e}')
    
    logger.info(f'Ingestion complete: {count} total assets updated')


if __name__ == '__main__':
    from services.asset_registry import get_all_assets
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ingest_all())
    print('\nLatest observations:')
    for a in get_all_assets():
        latest = get_latest_observation(a['symbol'])
        if latest:
            print(f"  {a['symbol']}: ${latest['price']:,.2f} change24h={latest['change24h']}% quality={latest['quality']}")
