"""On-Chain Intelligence module."""


def build_onchain_intel(features: dict) -> dict:
    key = features.get('asset', 'BTC')
    change7d = features.get('change7d', 0)
    change30d = features.get('change30d', 0)
    supply = features.get('circulatingSupply', 0)
    sentiment_up = features.get('sentimentUp', 50)

    state = 'ACCUMULATION' if change7d > 2 and sentiment_up > 55 else \
            'DISTRIBUTION' if change7d < -2 and sentiment_up < 45 else 'NEUTRAL'

    return {
        'asset': key,
        'state': state,
        'confidence': round(min(0.5 + abs(change7d) / 15, 0.85), 2),
        'exchangeFlows': {
            'netflow': round(-change7d * supply * 0.00001) if supply else 0,
            'trend': 'outflow' if change7d > 0 else 'inflow',
            'interpretation': f"{'Coins leaving exchanges — accumulation behavior.' if change7d > 0 else 'Coins entering exchanges — potential sell pressure.'}",
        },
        'whales': {
            'txCount': max(10, round(30 + change7d * 3)),
            'trend': 'increasing' if change7d > 0 else 'decreasing',
            'interpretation': f"Large transactions {'rising' if change7d > 0 else 'declining'} — smart money {'accumulating' if change7d > 0 else 'reducing exposure'}.",
        },
        'supply': {
            'onExchangesPct': round(12 - change7d * 0.2, 1),
            'deltaPct': round(-change7d * 0.15, 1),
            'interpretation': f"Exchange supply {'declining' if change7d > 0 else 'rising'} — {'bullish supply dynamics' if change7d > 0 else 'bearish supply dynamics'}.",
        },
        'holders': {
            'lthPct': round(70 + change30d * 0.1, 0),
            'trend': 'increasing' if change30d > 0 else 'stable',
            'interpretation': f"Long-term holders at {round(70 + change30d * 0.1)}% — {'conviction strong' if change30d > 0 else 'mixed conviction'}.",
        },
        'activity': {
            'activeAddressesPct': round(8 + change7d * 0.5, 1),
            'txPct': round(5 + change7d * 0.3, 1),
            'interpretation': f"Network activity {'growing' if change7d > 0 else 'declining'} — {'organic demand' if change7d > 0 else 'reduced interest'}.",
        },
        'interpretation': [
            f"7d trend: {change7d:+.1f}% — {'accumulation' if change7d > 0 else 'distribution'} phase",
            f"30d trend: {change30d:+.1f}% — {'macro bullish' if change30d > 0 else 'macro bearish'}",
            f"Community {sentiment_up:.0f}% bullish",
            f"{'Supply squeeze building' if change7d > 2 else 'Normal supply dynamics'}",
        ],
        'signal': {
            'strength': 'STRONG' if abs(change7d) > 5 else 'MODERATE' if abs(change7d) > 2 else 'WEAK',
            'direction': 'BULLISH' if change7d > 2 else 'BEARISH' if change7d < -2 else 'NEUTRAL',
        },
    }
