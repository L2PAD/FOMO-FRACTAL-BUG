"""Drivers Engine — generates 4 analytical modules (Exchange, Sentiment, On-chain, Structure)."""


def exchange_driver(f: dict) -> dict:
    change24h = f.get('change24h', 0)
    if change24h > 1:
        return {'module': 'Exchange', 'state': 'BULLISH', 'label': f"Price up {change24h:.1f}% in 24h, momentum strong"}
    elif change24h < -1:
        return {'module': 'Exchange', 'state': 'BEARISH', 'label': f"Price down {abs(change24h):.1f}% in 24h, sellers active"}
    return {'module': 'Exchange', 'state': 'NEUTRAL', 'label': f"Price flat ({change24h:+.1f}%), consolidating"}


def sentiment_driver(f: dict) -> dict:
    sentiment_up = f.get('sentimentUp', 50)
    if sentiment_up > 65:
        return {'module': 'Sentiment', 'state': 'BULLISH', 'label': f"Community {sentiment_up:.0f}% bullish"}
    elif sentiment_up < 40:
        return {'module': 'Sentiment', 'state': 'BEARISH', 'label': f"Community only {sentiment_up:.0f}% bullish"}
    return {'module': 'Sentiment', 'state': 'NEUTRAL', 'label': f"Mixed sentiment ({sentiment_up:.0f}% bullish)"}


def onchain_driver(f: dict) -> dict:
    change7d = f.get('change7d', 0)
    if change7d > 3:
        return {'module': 'On-chain', 'state': 'BULLISH', 'label': f"7d trend +{change7d:.1f}%, accumulation pattern"}
    elif change7d < -3:
        return {'module': 'On-chain', 'state': 'BEARISH', 'label': f"7d trend {change7d:.1f}%, distribution pattern"}
    return {'module': 'On-chain', 'state': 'NEUTRAL', 'label': f"7d range-bound ({change7d:+.1f}%)"}


def structure_driver(f: dict) -> dict:
    change24h = f.get('change24h', 0)
    change7d = f.get('change7d', 0)
    if change7d > 0 and change24h > 0:
        return {'module': 'Structure', 'state': 'BULLISH', 'label': 'Multi-timeframe aligned bullish'}
    elif change7d < 0 and change24h < 0:
        return {'module': 'Structure', 'state': 'BEARISH', 'label': 'Multi-timeframe aligned bearish'}
    return {'module': 'Structure', 'state': 'NEUTRAL', 'label': 'Mixed timeframe signals'}


def compute_drivers(features: dict) -> list:
    """Generate data-driven driver analysis."""
    return [
        exchange_driver(features),
        sentiment_driver(features),
        onchain_driver(features),
        structure_driver(features),
    ]
