"""Intel Service — orchestrates deep intelligence modules."""
from services.ingestion import ensure_fresh_data
from services.asset_registry import normalize_symbol
from .exchange import build_exchange_intel
from .onchain import build_onchain_intel
from .sentiment import build_sentiment_intel
from .fractal import build_fractal_intel


async def load_features(asset: str, max_age: int = 120) -> dict | None:
    """Load fresh observation and return as feature dict."""
    key = normalize_symbol(asset)
    obs = await ensure_fresh_data(key, max_age_seconds=max_age)
    if not obs:
        return None
    obs['asset'] = key
    return obs


async def get_exchange_intel(asset: str) -> dict:
    features = await load_features(asset)
    if not features:
        return {'error': 'Data unavailable'}
    return build_exchange_intel(features)


async def get_onchain_intel(asset: str) -> dict:
    features = await load_features(asset)
    if not features:
        return {'error': 'Data unavailable'}
    return build_onchain_intel(features)


async def get_sentiment_intel(asset: str) -> dict:
    features = await load_features(asset)
    if not features:
        # Fallback: synthesise sentimentUp from sentiment_runtime (real news+VADER score)
        from services.sentiment_runtime import runtime as _sent_runtime
        sym = normalize_symbol(asset)
        rt = _sent_runtime(sym)
        score = rt.get("score") if rt.get("ok") else None
        if score is not None:
            features = {
                "asset": sym,
                "sentimentUp": round(50 + float(score) * 50),  # map -1..1 → 0..100
                "change24h": 0.0,
                "_source": "sentiment_runtime",
            }
        else:
            return {"error": "Data unavailable", "asset": sym}
    return build_sentiment_intel(features)


async def get_fractal_intel(asset: str) -> dict:
    features = await load_features(asset)
    if not features:
        return {'error': 'Data unavailable'}
    return build_fractal_intel(features)


async def get_intel_overview(asset: str) -> dict:
    """Intel overview with real data enrichment."""
    features = await load_features(asset)
    if not features:
        return {'asset': asset, 'verdict': {'direction': 'NEUTRAL', 'confidence': 0.5, 'alignedModules': 0, 'totalModules': 5}, 'modules': []}

    from services.signal.signal_engine import compute_signal
    signal = compute_signal(features)

    key = features.get('asset', asset)
    change24h = features.get('change24h', 0)
    sentiment_up = features.get('sentimentUp', 50)
    change7d = features.get('change7d', 0)
    direction = 'BULLISH' if signal.get('score', 0) > 5 else 'BEARISH' if signal.get('score', 0) < -5 else 'NEUTRAL'

    modules = [
        {
            'id': 'exchange', 'name': 'Exchange Intelligence', 'status': 'ACTIVE',
            'direction': 'BULLISH' if change24h > 1 else 'BEARISH' if change24h < -1 else 'NEUTRAL',
            'confidence': round(min(0.5 + abs(change24h) / 10, 0.9), 2),
            'summary': f"{'Positive momentum' if change24h > 0 else 'Negative momentum'} — {abs(change24h):.1f}% move in 24h.",
        },
        {
            'id': 'fractal', 'name': 'Fractal Analysis', 'status': 'ACTIVE',
            'direction': 'BULLISH' if change7d > 2 else 'BEARISH' if change7d < -2 else 'NEUTRAL',
            'confidence': round(min(0.5 + abs(change7d) / 15, 0.85), 2),
            'summary': f"7d trend {'up' if change7d > 0 else 'down'} {abs(change7d):.1f}%. {'Aligned with daily bias.' if (change7d > 0 and change24h > 0) else 'Mixed timeframe signals.'}",
        },
        {
            'id': 'sentiment', 'name': 'Sentiment Analysis', 'status': 'ACTIVE',
            'direction': 'BULLISH' if sentiment_up > 60 else 'BEARISH' if sentiment_up < 40 else 'NEUTRAL',
            'confidence': round(abs(sentiment_up - 50) / 50 * 0.7 + 0.3, 2),
            'summary': f"Community {sentiment_up:.0f}% bullish. {'Strong conviction.' if sentiment_up > 70 else 'Mixed signals.' if 40 < sentiment_up < 60 else 'Fear present.'}",
        },
        {
            'id': 'onchain', 'name': 'On-Chain Analytics', 'status': 'ACTIVE',
            'direction': 'BULLISH' if change7d > 0 and sentiment_up > 55 else 'BEARISH' if change7d < 0 and sentiment_up < 45 else 'NEUTRAL',
            'confidence': round(signal.get('confidence', 0.5) * 0.9, 2),
            'summary': f"{'Accumulation signals detected' if change7d > 0 else 'Distribution phase likely' if change7d < -2 else 'Neutral flow patterns'}.",
        },
        {'id': 'ta', 'name': 'Technical Analysis', 'status': 'SUN', 'message': 'Coming soon'},
    ]

    aligned = sum(1 for m in modules if m.get('direction') == direction and m.get('status') == 'ACTIVE')

    return {
        'asset': key,
        'verdict': {'direction': direction, 'confidence': signal.get('confidence', 0.5), 'alignedModules': aligned, 'totalModules': 5},
        'modules': modules,
    }
