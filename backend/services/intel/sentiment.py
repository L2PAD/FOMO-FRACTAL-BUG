"""Sentiment Intelligence module."""


def build_sentiment_intel(features: dict) -> dict:
    key = features.get('asset', 'BTC')
    sentiment_up = features.get('sentimentUp', 50)
    change24h = features.get('change24h', 0)

    if sentiment_up > 75: state = 'EUPHORIA'
    elif sentiment_up > 60: state = 'OPTIMISM'
    elif sentiment_up > 40: state = 'NEUTRAL'
    elif sentiment_up > 25: state = 'FEAR'
    else: state = 'CAPITULATION'

    fear_greed = min(max(round(sentiment_up * 1.1 + change24h * 2), 5), 95)

    return {
        'asset': key,
        'state': state,
        'confidence': round(abs(sentiment_up - 50) / 50 * 0.6 + 0.35, 2),
        'score': {
            'value': round(sentiment_up),
            'trend': 'rising' if change24h > 0 else 'falling',
            'interpretation': f"Sentiment at {sentiment_up:.0f}% — {'approaching overheated' if sentiment_up > 75 else 'healthy optimism' if sentiment_up > 60 else 'cautious market' if sentiment_up > 40 else 'fear present'}.",
        },
        'social': {
            'mentionsPct': round(20 + sentiment_up * 0.3 + abs(change24h) * 2),
            'trend': 'increasing' if change24h > 0 else 'stable',
            'interpretation': f"Social activity {'surging' if sentiment_up > 70 else 'moderate' if sentiment_up > 45 else 'declining'}.",
        },
        'twitter': {
            'velocityPct': round(15 + abs(change24h) * 5 + (sentiment_up - 50) * 0.3),
            'activeInfluencers': round(5 + sentiment_up * 0.1),
            'interpretation': f"{'Influencer amplification in progress' if sentiment_up > 65 else 'Normal social activity'}.",
        },
        'narrative': {
            'title': f"{key} {'rally' if change24h > 2 else 'momentum' if change24h > 0 else 'correction' if change24h < -2 else 'consolidation'}",
            'sentiment': 'positive' if sentiment_up > 55 else 'negative' if sentiment_up < 45 else 'mixed',
            'interpretation': f"{'Bullish narrative dominant' if sentiment_up > 60 else 'Bearish sentiment spreading' if sentiment_up < 40 else 'No clear narrative consensus'}.",
        },
        'positioning': {
            'longPct': round(sentiment_up * 0.9 + 10),
            'shortPct': round(100 - (sentiment_up * 0.9 + 10)),
            'interpretation': f"Crowd {round(sentiment_up * 0.9 + 10)}% long — {'crowded' if sentiment_up > 70 else 'balanced' if 40 < sentiment_up < 60 else 'underweight'}.",
        },
        'fearGreed': {
            'value': fear_greed,
            'state': 'EXTREME_GREED' if fear_greed > 80 else 'GREED' if fear_greed > 55 else 'NEUTRAL' if fear_greed > 45 else 'FEAR' if fear_greed > 25 else 'EXTREME_FEAR',
            'interpretation': f"Fear & Greed at {fear_greed} — {'extreme greed, contrarian risk' if fear_greed > 80 else 'greed zone' if fear_greed > 55 else 'neutral' if fear_greed > 45 else 'fear present, potential bottom'}.",
        },
        'interpretation': [
            f"Sentiment: {sentiment_up:.0f}% bullish ({state})",
            f"Fear & Greed: {fear_greed}",
            f"{'Social volume surging' if sentiment_up > 70 else 'Normal social activity'}",
            f"{'Contrarian warning: crowd too bullish' if sentiment_up > 80 else 'Sentiment aligned with price action' if (sentiment_up > 55 and change24h > 0) else 'Divergence between sentiment and price'}",
        ],
        'signal': {
            'strength': 'STRONG' if abs(sentiment_up - 50) > 25 else 'MODERATE' if abs(sentiment_up - 50) > 10 else 'WEAK',
            'direction': 'BULLISH' if sentiment_up > 55 else 'BEARISH' if sentiment_up < 45 else 'NEUTRAL',
        },
    }
