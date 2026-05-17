"""Fractal / Structure Intelligence module."""


def build_fractal_intel(features: dict) -> dict:
    key = features.get('asset', 'BTC')
    price = features.get('price', 0)
    change24h = features.get('change24h', 0)
    change7d = features.get('change7d', 0)
    change30d = features.get('change30d', 0)
    volatility = features.get('volatility24h', 2)
    high24h = features.get('high24h', price)
    low24h = features.get('low24h', price)
    ath = features.get('ath', price * 1.5)

    # Regime detection
    if change7d > 5 and change24h > 0:
        state, regime, bias = 'TREND_CONTINUATION', 'TRENDING', 'BULLISH'
    elif change7d < -5 and change24h < 0:
        state, regime, bias = 'TREND_CONTINUATION', 'TRENDING', 'BEARISH'
    elif abs(change7d) < 2 and volatility < 3:
        state, regime, bias = 'COMPRESSION', 'RANGING', 'NEUTRAL'
    elif change7d > 0 and change24h < -1:
        state, regime, bias = 'PULLBACK', 'CORRECTING', 'BULLISH'
    else:
        state, regime, bias = 'TRANSITION', 'SHIFTING', 'NEUTRAL'

    # Timeframe alignment
    tf_5m = 'UP' if change24h > 0.3 else 'DOWN' if change24h < -0.3 else 'FLAT'
    tf_1h = 'UP' if change24h > 0 else 'DOWN' if change24h < 0 else 'FLAT'
    tf_4h = 'UP' if change7d > 1 else 'DOWN' if change7d < -1 else 'FLAT'
    tf_1d = 'UP' if change30d > 3 else 'DOWN' if change30d < -3 else 'FLAT'

    aligned_up = sum(1 for tf in [tf_5m, tf_1h, tf_4h, tf_1d] if tf == 'UP')
    aligned_down = sum(1 for tf in [tf_5m, tf_1h, tf_4h, tf_1d] if tf == 'DOWN')
    alignment_score = aligned_up if aligned_up > aligned_down else -aligned_down

    support = round(low24h * 0.995, 2)
    resistance = round(high24h * 1.005, 2)
    invalidation = round(low24h * 0.97, 2)
    confidence = round(min(0.45 + abs(alignment_score) * 0.1 + abs(change7d) / 20, 0.88), 2)

    return {
        'asset': key,
        'state': state,
        'confidence': confidence,
        'regime': {
            'current': regime, 'bias': bias,
            'interpretation': f"Market in {regime.lower()} regime. {'Trend following favored.' if regime == 'TRENDING' else 'Range trading favored.' if regime == 'RANGING' else 'Caution — regime shifting.'}",
        },
        'alignment': {
            'tf5m': tf_5m, 'tf1h': tf_1h, 'tf4h': tf_4h, 'tf1d': tf_1d,
            'score': alignment_score,
            'interpretation': f"{max(aligned_up, aligned_down)}/4 timeframes aligned {'bullish' if aligned_up > aligned_down else 'bearish' if aligned_down > aligned_up else 'mixed'}.",
        },
        'levels': {
            'support': support, 'resistance': resistance,
            'breakoutLow': round(price * 0.998, 2), 'breakoutHigh': round(resistance, 2),
            'invalidation': invalidation,
            'interpretation': f"Support at ${support:,.0f}, resistance at ${resistance:,.0f}. Invalidation below ${invalidation:,.0f}.",
        },
        'scenarios': {
            'base': f"Continuation toward ${round(price * 1.05):,.0f} — primary path" if bias == 'BULLISH' else f"Decline toward ${round(price * 0.95):,.0f}" if bias == 'BEARISH' else 'Range continuation',
            'alternative': f"Rejection to ${round(support):,.0f} retest" if bias == 'BULLISH' else f"Bounce to ${round(resistance):,.0f}" if bias == 'BEARISH' else 'Breakout in either direction',
            'interpretation': f"Base scenario favored while price holds above ${round(support):,.0f}." if bias != 'BEARISH' else f"Bearish until price reclaims ${round(resistance):,.0f}.",
        },
        'volatility': {
            'compression': 'LOW' if volatility < 2 else 'MODERATE' if volatility < 5 else 'HIGH',
            'expansionRisk': 'HIGH' if volatility < 2 else 'MODERATE' if volatility < 4 else 'LOW',
            'interpretation': f"Volatility at {volatility:.1f}%. {'Compression — breakout imminent.' if volatility < 2 else 'Normal range.' if volatility < 5 else 'Expanded — directional move in progress.'}",
        },
        'interpretation': [
            f"{state} regime — {regime.lower()}",
            f"{max(aligned_up, aligned_down)}/4 timeframes aligned",
            f"Support: ${support:,.0f} | Resistance: ${resistance:,.0f}",
            f"Volatility: {volatility:.1f}% {'(compressed)' if volatility < 2 else '(expanded)' if volatility > 5 else ''}",
            f"Invalidation below ${invalidation:,.0f}",
        ],
        'signal': {
            'strength': 'STRONG' if abs(alignment_score) >= 3 else 'MODERATE' if abs(alignment_score) >= 2 else 'WEAK',
            'direction': 'BULLISH' if alignment_score > 0 else 'BEARISH' if alignment_score < 0 else 'NEUTRAL',
        },
    }
