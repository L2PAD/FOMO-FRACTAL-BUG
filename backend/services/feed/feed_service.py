"""Feed Service — generates feed events from real market data."""
from datetime import datetime


def _price_event(f: dict) -> dict:
    asset = f.get('asset', 'BTC')
    price = f.get('price', 0)
    change24h = f.get('change24h', 0)
    low24h = f.get('low24h', 0)
    high24h = f.get('high24h', 0)

    if abs(change24h) > 2:
        direction = 'BULLISH' if change24h > 0 else 'BEARISH'
        return {
            'id': f"{asset.lower()}-price-{int(datetime.utcnow().timestamp())}",
            'asset': asset, 'source': 'exchange', 'direction': direction,
            'impact': 'HIGH', 'impactPct': round(change24h, 1),
            'title': f"{'Strong Rally' if change24h > 0 else 'Sharp Decline'}",
            'summary': f"{asset} {'surged' if change24h > 0 else 'dropped'} {abs(change24h):.1f}% in 24h to ${price:,.0f}",
            'timestamp': 'live',
            'affectsSignal': 'supports' if change24h > 0 else 'weakens',
            'rawData': f"Price: ${price:,.2f} | 24h Range: ${low24h:,.0f} - ${high24h:,.0f}",
            'whyMatters': f"{'Buyers dominating with sustained momentum' if change24h > 0 else 'Sellers in control, support levels being tested'}. Volume confirms the move.",
            'modelInterpretation': f"{'Strong directional move backed by volume. Key driver of current signal.' if abs(change24h) > 3 else 'Moderate move within normal range. Adds weight to directional bias.'}",
            'priority': 'key',
        }
    return {
        'id': f"{asset.lower()}-price-{int(datetime.utcnow().timestamp())}",
        'asset': asset, 'source': 'exchange', 'direction': 'NEUTRAL',
        'impact': 'LOW', 'impactPct': round(change24h, 1),
        'title': 'Price Consolidation',
        'summary': f"{asset} holding at ${price:,.0f} with {change24h:+.1f}% change",
        'timestamp': 'live',
        'affectsSignal': 'neutral',
        'rawData': f"Price: ${price:,.2f} | Range: ${low24h:,.0f} - ${high24h:,.0f}",
        'whyMatters': 'Tight range indicates market indecision. Breakout direction will determine next move.',
        'modelInterpretation': 'Consolidation phase. Waiting for catalyst or volume expansion.',
        'priority': 'secondary',
    }


def _volume_event(f: dict) -> dict | None:
    volume = f.get('volume24h', 0)
    change24h = f.get('change24h', 0)
    asset = f.get('asset', 'BTC')
    vol_b = volume / 1_000_000_000
    if vol_b <= 30:
        return None
    return {
        'id': f"{asset.lower()}-vol-{int(datetime.utcnow().timestamp())}",
        'asset': asset, 'source': 'exchange',
        'direction': 'BULLISH' if change24h > 0 else 'BEARISH',
        'impact': 'HIGH', 'impactPct': round(change24h * 0.5, 1),
        'title': 'Volume Surge',
        'summary': f"24h volume at ${vol_b:.1f}B — institutional-level activity",
        'timestamp': '1h ago', 'affectsSignal': 'supports',
        'rawData': f"Volume: ${vol_b:.1f}B | Trades: {f.get('trades24h', 'N/A')}",
        'whyMatters': 'High volume confirms price action is backed by real capital. Not just noise.',
        'modelInterpretation': 'Volume validates the current trend. High conviction signal.',
        'priority': 'key',
    }


def _sentiment_event(f: dict) -> dict | None:
    sentiment_up = f.get('sentimentUp', 50)
    change24h = f.get('change24h', 0)
    asset = f.get('asset', 'BTC')
    if not (sentiment_up > 70 or sentiment_up < 35):
        return None
    sent_dir = 'BULLISH' if sentiment_up > 65 else 'BEARISH'
    return {
        'id': f"{asset.lower()}-sent-{int(datetime.utcnow().timestamp())}",
        'asset': asset, 'source': 'sentiment', 'direction': sent_dir,
        'impact': 'MED', 'impactPct': round((sentiment_up - 50) * 0.1, 1),
        'title': f"{'Extreme Bullish' if sentiment_up > 75 else 'Strong Bullish' if sentiment_up > 65 else 'Fear Rising' if sentiment_up < 35 else 'Bearish'} Sentiment",
        'summary': f"Community sentiment: {sentiment_up:.0f}% bullish — {'approaching euphoria' if sentiment_up > 75 else 'confidence high' if sentiment_up > 65 else 'fear spreading'}",
        'timestamp': '2h ago',
        'affectsSignal': 'supports' if sentiment_up > 60 else 'weakens',
        'rawData': f"Bullish: {sentiment_up:.0f}% | Bearish: {100 - sentiment_up:.0f}%",
        'whyMatters': f"{'High conviction from community. Historically can precede corrections when extreme.' if sentiment_up > 75 else 'Fear at these levels often marks bottoms.' if sentiment_up < 35 else 'Moderate conviction aligning with price action.'}",
        'modelInterpretation': f"{'Contrarian risk — too crowded. Reduces overall conviction by 5%.' if sentiment_up > 80 else 'Aligned with core signal. Adds confidence.'}",
        'priority': 'key' if abs(sentiment_up - 50) > 25 else 'secondary',
    }


def _volatility_event(f: dict) -> dict | None:
    volatility = f.get('volatility24h', 0)
    asset = f.get('asset', 'BTC')
    high24h = f.get('high24h', 0)
    low24h = f.get('low24h', 0)
    if volatility <= 5:
        return None
    return {
        'id': f"{asset.lower()}-vol2-{int(datetime.utcnow().timestamp())}",
        'asset': asset, 'source': 'exchange', 'direction': 'NEUTRAL',
        'impact': 'MED', 'impactPct': 0,
        'title': 'Elevated Volatility',
        'summary': f"24h range: {volatility:.1f}% — wider than average, caution advised",
        'timestamp': '3h ago', 'affectsSignal': 'weakens',
        'rawData': f"24h High: ${high24h:,.0f} | Low: ${low24h:,.0f} | Range: {volatility:.1f}%",
        'whyMatters': 'Wide ranges create opportunity but also risk. Position sizing should adjust.',
        'modelInterpretation': 'Volatility regime shift detected. Signals may be less reliable.',
        'priority': 'secondary',
    }


def _weekly_trend_event(f: dict) -> dict | None:
    change7d = f.get('change7d', 0)
    asset = f.get('asset', 'BTC')
    if abs(change7d) <= 3:
        return None
    return {
        'id': f"{asset.lower()}-trend-{int(datetime.utcnow().timestamp())}",
        'asset': asset, 'source': 'onchain',
        'direction': 'BULLISH' if change7d > 0 else 'BEARISH',
        'impact': 'MED', 'impactPct': round(change7d * 0.3, 1),
        'title': f"7-Day {'Uptrend' if change7d > 0 else 'Downtrend'}",
        'summary': f"{asset} {'gained' if change7d > 0 else 'lost'} {abs(change7d):.1f}% over the past week",
        'timestamp': '4h ago',
        'affectsSignal': 'supports' if change7d > 0 else 'weakens',
        'rawData': f"7d Change: {change7d:+.1f}% | 30d Change: {f.get('change30d', 0):+.1f}%",
        'whyMatters': f"{'Sustained buying pressure over multiple days confirms trend.' if change7d > 0 else 'Multi-day selling indicates structural weakness.'}",
        'modelInterpretation': 'Trend confirmation. Aligns with primary signal direction.',
        'priority': 'key',
    }


def _ath_event(f: dict) -> dict | None:
    ath_change = f.get('athChangePercent', 0)
    price = f.get('price', 0)
    ath = f.get('ath', 0)
    asset = f.get('asset', 'BTC')

    if ath_change > -10:
        return {
            'id': f"{asset.lower()}-ath-{int(datetime.utcnow().timestamp())}",
            'asset': asset, 'source': 'exchange', 'direction': 'BULLISH',
            'impact': 'HIGH', 'impactPct': 2,
            'title': 'Near All-Time High',
            'summary': f"{asset} only {abs(ath_change):.0f}% from ATH (${ath:,.0f})",
            'timestamp': '5h ago', 'affectsSignal': 'supports',
            'rawData': f"ATH: ${ath:,.0f} | Current: ${price:,.0f} | Gap: {ath_change:.1f}%",
            'whyMatters': 'Proximity to ATH indicates strong momentum. New highs attract more buying.',
            'modelInterpretation': 'Breakout potential high. Historical ATH tests often resolve upward with volume.',
            'priority': 'key',
        }
    elif ath_change < -40:
        return {
            'id': f"{asset.lower()}-ath-{int(datetime.utcnow().timestamp())}",
            'asset': asset, 'source': 'onchain', 'direction': 'NEUTRAL',
            'impact': 'LOW', 'impactPct': 0,
            'title': 'Deep Below ATH',
            'summary': f"{asset} is {abs(ath_change):.0f}% below ATH — potential value zone",
            'timestamp': '6h ago', 'affectsSignal': 'neutral',
            'rawData': f"ATH: ${ath:,.0f} | Current: ${price:,.0f}",
            'whyMatters': 'Large ATH gap could mean value opportunity or structural weakness. Context matters.',
            'modelInterpretation': 'Recovery potential exists but requires catalyst. Not actionable alone.',
            'priority': 'noise',
        }
    return None


def generate_feed_events(features: dict) -> list:
    """Generate feed events from market features."""
    if not features:
        return []
    generators = [
        _price_event,
        _volume_event,
        _sentiment_event,
        _volatility_event,
        _weekly_trend_event,
        _ath_event,
    ]
    events = []
    for fn in generators:
        ev = fn(features)
        if ev is not None:
            events.append(ev)
    return events
