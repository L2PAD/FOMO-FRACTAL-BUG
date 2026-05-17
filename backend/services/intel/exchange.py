"""Exchange Intelligence module."""


def build_exchange_intel(features: dict) -> dict:
    change24h = features.get('change24h', 0)
    volatility = features.get('volatility24h', 2)
    volume = features.get('volume24h', 0)
    spread = features.get('spreadBps', 1)
    price = features.get('price', 0)

    est_funding = round(change24h * 0.003, 4)
    est_oi = round(volume * 0.25, 0)
    buy_pct = min(max(50 + change24h * 3, 30), 75)
    bias = 'BULLISH' if change24h > 1 else 'BEARISH' if change24h < -1 else 'NEUTRAL'
    confidence = round(min(0.5 + abs(change24h) / 8, 0.88), 2)

    return {
        'asset': features.get('asset', 'BTC'),
        'bias': bias,
        'confidence': confidence,
        'funding': {
            'current': est_funding,
            'delta': round(est_funding * 0.3, 4),
            'trend': 'increasing' if change24h > 0 else 'decreasing',
            'interpretation': f"{'Longs paying shorts — bullish pressure.' if est_funding > 0 else 'Shorts paying longs — bearish bias.'} Based on {abs(change24h):.1f}% 24h momentum.",
        },
        'openInterest': {
            'value': round(est_oi),
            'deltaPct': round(change24h * 1.5, 1),
            'interpretation': f"{'New capital entering market — confirms directional commitment.' if abs(change24h) > 1 else 'Stable positioning — market in wait mode.'}",
        },
        'liquidations': {
            'short': round(volume * 0.001 * max(change24h, 0), 0),
            'long': round(volume * 0.001 * max(-change24h, 0), 0),
            'ratio': round(max(change24h, 0.1) / max(-change24h, 0.1), 2) if change24h != 0 else 1.0,
            'interpretation': f"{'Shorts under pressure' if change24h > 0 else 'Longs being squeezed' if change24h < 0 else 'Balanced liquidation activity'}.",
        },
        'orderFlow': {
            'buyPct': round(buy_pct),
            'sellPct': round(100 - buy_pct),
            'interpretation': f"{'Buyers dominating' if buy_pct > 55 else 'Sellers dominating' if buy_pct < 45 else 'Balanced flow'}. Volume: ${volume/1e9:.1f}B.",
        },
        'interpretation': [
            f"{'Positive' if est_funding > 0 else 'Negative'} funding at {est_funding:.4f}",
            f"Volume: ${volume/1e9:.1f}B — {'institutional level' if volume > 20e9 else 'normal activity'}",
            f"Spread: {spread:.1f}bps — {'tight, high liquidity' if spread < 3 else 'moderate' if spread < 10 else 'wide, low liquidity'}",
            f"Price {change24h:+.1f}% in 24h with {'confirming' if abs(change24h) > 1 else 'low'} volume",
        ],
        'signal': {
            'strength': 'STRONG' if abs(change24h) > 3 else 'MODERATE' if abs(change24h) > 1 else 'WEAK',
            'direction': bias,
        },
    }
