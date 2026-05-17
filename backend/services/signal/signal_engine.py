"""Signal Engine — scores market data and maps to BUY/SELL/WAIT.

Pure computation, no DB, no I/O.
"""


def calculate_score(features: dict) -> int:
    """Calculate raw score from market features (-100 to +100)."""
    score = 0

    change24h = features.get('change24h', 0)
    change7d = features.get('change7d', 0)
    change30d = features.get('change30d', 0)
    sentiment_up = features.get('sentimentUp', 50)
    ath_change = features.get('athChangePercent', 0)

    # Momentum (24h)
    if change24h > 3:
        score += 25
    elif change24h > 1:
        score += 15
    elif change24h > 0:
        score += 5
    elif change24h > -1:
        score -= 5
    elif change24h > -3:
        score -= 15
    else:
        score -= 25

    # Trend (7d)
    if change7d > 5:
        score += 20
    elif change7d > 2:
        score += 10
    elif change7d > 0:
        score += 5
    elif change7d > -2:
        score -= 5
    elif change7d > -5:
        score -= 10
    else:
        score -= 20

    # Macro trend (30d)
    if change30d > 10:
        score += 15
    elif change30d > 3:
        score += 8
    elif change30d > 0:
        score += 3
    elif change30d > -3:
        score -= 3
    elif change30d > -10:
        score -= 8
    else:
        score -= 15

    # Sentiment
    if sentiment_up > 70:
        score += 10
    elif sentiment_up > 55:
        score += 5
    elif sentiment_up < 30:
        score -= 10
    elif sentiment_up < 45:
        score -= 5

    # ATH proximity (contrarian)
    if ath_change > -5:
        score -= 5
    elif ath_change < -30:
        score += 5

    return score


def map_score_to_action(score: int) -> dict:
    """Map raw score to decision + confidence + strength."""
    confidence = min(max((score + 50) / 100, 0.25), 0.92)

    if score > 20:
        decision = 'BUY'
        strength = 'STRONG' if score > 40 else 'MODERATE'
    elif score > 5:
        decision = 'BUY'
        strength = 'LOW_EDGE'
    elif score < -20:
        decision = 'SELL'
        strength = 'STRONG' if score < -40 else 'MODERATE'
    elif score < -5:
        decision = 'SELL'
        strength = 'LOW_EDGE'
    else:
        decision = 'WAIT'
        strength = 'LOW_EDGE'

    return {
        'decision': decision,
        'confidence': round(confidence, 2),
        'strength': strength,
        'score': score,
    }


def compute_signal(features: dict) -> dict:
    """Main entry point: features → Signal dict."""
    if not features:
        return {'decision': 'WAIT', 'confidence': 0.5, 'strength': 'LOW_EDGE', 'score': 0}
    score = calculate_score(features)
    return map_score_to_action(score)
