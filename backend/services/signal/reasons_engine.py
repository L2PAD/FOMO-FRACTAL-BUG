"""Reasons Engine — builds structured signal reasons.

Each reason block is a separate function for testability.
"""


def momentum_reason(f: dict, signal: dict) -> dict | None:
    change24h = f.get('change24h', 0)
    price = f.get('price', 0)
    low24h = f.get('low24h', 0)
    high24h = f.get('high24h', 0)

    if abs(change24h) > 3:
        direction = 'bullish' if change24h > 0 else 'bearish'
        return {
            'module': 'exchange', 'type': 'momentum',
            'text': f"{'Strong upward' if change24h > 0 else 'Heavy downward'} momentum",
            'detail': f"Price moved {change24h:+.1f}% in 24h (${low24h:,.0f} → ${price:,.0f}). "
                      f"{'Buyers dominating with sustained pressure above key levels.' if change24h > 0 else 'Sellers in control, breaking through support levels.'}",
            'impact': 'strong', 'direction': direction,
            'weight': min(abs(change24h) / 10, 0.3),
        }
    elif abs(change24h) > 1:
        direction = 'bullish' if change24h > 0 else 'bearish'
        return {
            'module': 'exchange', 'type': 'momentum',
            'text': f"{'Moderate bullish' if change24h > 0 else 'Moderate bearish'} pressure",
            'detail': f"24h change: {change24h:+.1f}%. {'Steady buying interest.' if change24h > 0 else 'Gradual sell pressure building.'}",
            'impact': 'supporting', 'direction': direction,
            'weight': min(abs(change24h) / 10, 0.15),
        }
    else:
        return {
            'module': 'exchange', 'type': 'momentum',
            'text': 'Price consolidating in tight range',
            'detail': f"24h change: {change24h:+.1f}%. Range: ${low24h:,.0f} – ${high24h:,.0f}. Breakout direction will be decisive.",
            'impact': 'neutral', 'direction': 'neutral',
            'weight': 0.05,
        }


def volume_reason(f: dict, signal: dict) -> dict | None:
    volume = f.get('volume24h', 0)
    change24h = f.get('change24h', 0)
    vol_billions = volume / 1_000_000_000 if volume else 0

    if vol_billions > 30:
        return {
            'module': 'exchange', 'type': 'volume',
            'text': 'Institutional-level volume detected',
            'detail': f"24h volume: ${vol_billions:.1f}B — significantly above average. "
                      f"{'Validates upward move with real capital.' if change24h > 0 else 'Heavy selling backed by large positions.'}",
            'impact': 'strong',
            'direction': 'bullish' if change24h > 0 else 'bearish',
            'weight': 0.2,
        }
    elif vol_billions > 10:
        return {
            'module': 'exchange', 'type': 'volume',
            'text': 'Above-average trading volume',
            'detail': f"24h volume: ${vol_billions:.1f}B — healthy activity confirms market conviction.",
            'impact': 'supporting',
            'direction': 'bullish' if change24h > 0 else 'neutral',
            'weight': 0.1,
        }
    return None


def liquidity_reason(f: dict, signal: dict) -> dict | None:
    spread = f.get('spreadBps', 1)

    if spread < 2:
        return {
            'module': 'exchange', 'type': 'liquidity',
            'text': 'Exceptionally tight spread — deep liquidity',
            'detail': f"Spread: {spread:.1f}bps. Institutional-grade liquidity reduces slippage risk. Confirms large players are active.",
            'impact': 'supporting', 'direction': 'neutral', 'weight': 0.08,
        }
    elif spread > 8:
        return {
            'module': 'exchange', 'type': 'liquidity',
            'text': 'Widening spread — reduced liquidity',
            'detail': f"Spread: {spread:.1f}bps. Thinner orderbook increases execution risk. Position sizing should be reduced.",
            'impact': 'conflicting', 'direction': 'neutral', 'weight': 0.1,
        }
    return None


def sentiment_reason(f: dict, signal: dict) -> dict | None:
    sentiment_up = f.get('sentimentUp', 50)

    if sentiment_up > 75:
        return {
            'module': 'sentiment', 'type': 'sentiment',
            'text': 'Extreme bullish sentiment — crowd euphoria',
            'detail': f"Community {sentiment_up:.0f}% bullish. Historically, extreme optimism can precede corrections. "
                      f"Contrarian risk: when everyone agrees, the trade is crowded.",
            'impact': 'conflicting' if signal['decision'] == 'BUY' else 'supporting',
            'direction': 'bullish', 'weight': 0.12,
        }
    elif sentiment_up > 60:
        return {
            'module': 'sentiment', 'type': 'sentiment',
            'text': 'Bullish community conviction',
            'detail': f"Sentiment: {sentiment_up:.0f}% bullish. Healthy optimism aligned with price action. Not yet at contrarian extremes.",
            'impact': 'supporting', 'direction': 'bullish', 'weight': 0.1,
        }
    elif sentiment_up < 30:
        return {
            'module': 'sentiment', 'type': 'sentiment',
            'text': 'Extreme fear — potential bottom signal',
            'detail': f"Only {sentiment_up:.0f}% bullish. Fear at these levels has historically marked accumulation zones for smart money.",
            'impact': 'supporting' if signal['decision'] == 'BUY' else 'conflicting',
            'direction': 'bearish', 'weight': 0.15,
        }
    elif sentiment_up < 45:
        return {
            'module': 'sentiment', 'type': 'sentiment',
            'text': 'Cautious market sentiment',
            'detail': f"Sentiment: {sentiment_up:.0f}% bullish. Fear present but not extreme. Market participants are hedging positions.",
            'impact': 'supporting' if signal['decision'] == 'SELL' else 'neutral',
            'direction': 'bearish', 'weight': 0.08,
        }
    return None


def weekly_trend_reason(f: dict, signal: dict) -> dict | None:
    change7d = f.get('change7d', 0)

    if abs(change7d) > 5:
        direction = 'bullish' if change7d > 0 else 'bearish'
        return {
            'module': 'onchain', 'type': 'trend',
            'text': f"Strong {'accumulation' if change7d > 0 else 'distribution'} trend (7d)",
            'detail': f"7-day change: {change7d:+.1f}%. {'Sustained buying over multiple days confirms structural demand.' if change7d > 0 else 'Multi-day selling indicates institutional repositioning.'}",
            'impact': 'strong', 'direction': direction, 'weight': 0.2,
        }
    elif abs(change7d) > 2:
        direction = 'bullish' if change7d > 0 else 'bearish'
        return {
            'module': 'onchain', 'type': 'trend',
            'text': f"{'Building' if change7d > 0 else 'Declining'} weekly momentum",
            'detail': f"7-day change: {change7d:+.1f}%. Trend developing but not yet at extreme levels.",
            'impact': 'supporting', 'direction': direction, 'weight': 0.12,
        }
    return None


def macro_trend_reason(f: dict, signal: dict) -> dict | None:
    change30d = f.get('change30d', 0)

    if abs(change30d) > 10:
        direction = 'bullish' if change30d > 0 else 'bearish'
        return {
            'module': 'structure', 'type': 'structure',
            'text': f"{'Strong macro uptrend' if change30d > 0 else 'Macro downtrend in progress'}",
            'detail': f"30-day change: {change30d:+.1f}%. {'Longer-term structure remains constructive with higher highs.' if change30d > 0 else 'Structural weakness persists. Recovery requires catalyst.'}",
            'impact': 'strong' if abs(change30d) > 15 else 'supporting',
            'direction': direction, 'weight': 0.15,
        }
    return None


def timeframe_alignment_reason(f: dict, signal: dict) -> dict | None:
    change24h = f.get('change24h', 0)
    change7d = f.get('change7d', 0)
    change30d = f.get('change30d', 0)

    aligned_bull = sum(1 for c in [change24h, change7d, change30d] if c > 0)
    aligned_bear = sum(1 for c in [change24h, change7d, change30d] if c < 0)

    if aligned_bull == 3:
        return {
            'module': 'structure', 'type': 'structure',
            'text': 'All timeframes aligned bullish',
            'detail': f"24h ({change24h:+.1f}%), 7d ({change7d:+.1f}%), 30d ({change30d:+.1f}%) — all positive. Multi-timeframe confirmation is the strongest structural signal.",
            'impact': 'strong', 'direction': 'bullish', 'weight': 0.2,
        }
    elif aligned_bear == 3:
        return {
            'module': 'structure', 'type': 'structure',
            'text': 'All timeframes aligned bearish',
            'detail': f"24h ({change24h:+.1f}%), 7d ({change7d:+.1f}%), 30d ({change30d:+.1f}%) — all negative. Structural weakness across all horizons.",
            'impact': 'strong', 'direction': 'bearish', 'weight': 0.2,
        }
    elif aligned_bull >= 2 or aligned_bear >= 2:
        dom = 'bullish' if aligned_bull > aligned_bear else 'bearish'
        return {
            'module': 'structure', 'type': 'structure',
            'text': f'Majority of timeframes lean {dom}',
            'detail': f"24h ({change24h:+.1f}%), 7d ({change7d:+.1f}%), 30d ({change30d:+.1f}%). One timeframe diverges — partial confirmation.",
            'impact': 'supporting', 'direction': dom, 'weight': 0.1,
        }
    return None


def ath_proximity_reason(f: dict, signal: dict) -> dict | None:
    ath_change = f.get('athChangePercent', 0)
    ath = f.get('ath', 0)

    if ath_change > -5 and ath > 0:
        return {
            'module': 'structure', 'type': 'structure',
            'text': 'Testing all-time high territory',
            'detail': f"Only {abs(ath_change):.0f}% from ATH (${ath:,.0f}). New highs attract momentum buyers. Breakout probability elevated.",
            'impact': 'strong', 'direction': 'bullish', 'weight': 0.15,
        }
    elif ath_change < -40 and ath > 0:
        return {
            'module': 'structure', 'type': 'risk',
            'text': 'Deep below all-time high',
            'detail': f"{abs(ath_change):.0f}% below ATH (${ath:,.0f}). Recovery requires significant catalyst and time.",
            'impact': 'neutral', 'direction': 'neutral', 'weight': 0.05,
        }
    return None


def volatility_reason(f: dict, signal: dict) -> dict | None:
    volatility = f.get('volatility24h', 2)
    low24h = f.get('low24h', 0)
    high24h = f.get('high24h', 0)

    if volatility > 6:
        return {
            'module': 'exchange', 'type': 'risk',
            'text': 'Elevated volatility — increased risk',
            'detail': f"24h range: {volatility:.1f}% (${low24h:,.0f} – ${high24h:,.0f}). Wide swings reduce signal reliability. Reduce position size.",
            'impact': 'conflicting', 'direction': 'neutral', 'weight': 0.1,
        }
    elif volatility < 1.5:
        return {
            'module': 'exchange', 'type': 'risk',
            'text': 'Compressed volatility — breakout imminent',
            'detail': f"24h range: only {volatility:.1f}%. Extreme compression historically precedes explosive moves.",
            'impact': 'neutral', 'direction': 'neutral', 'weight': 0.08,
        }
    return None


def compute_reasons(features: dict, signal: dict) -> list:
    """Build structured signal reasons from market features."""
    builders = [
        momentum_reason,
        volume_reason,
        liquidity_reason,
        sentiment_reason,
        weekly_trend_reason,
        macro_trend_reason,
        timeframe_alignment_reason,
        ath_proximity_reason,
        volatility_reason,
    ]

    reasons = []
    for fn in builders:
        r = fn(features, signal)
        if r is not None:
            reasons.append(r)

    reasons.sort(key=lambda r: r['weight'], reverse=True)
    return reasons
