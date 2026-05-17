"""
Fractal Forecast Generator — Python Native (No Node.js dependency)
===================================================================

Generates multi-horizon fractal forecasts for BTC, SPX, DXY
using yfinance price data and technical analysis.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")
_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]

SCOPES = {
    "BTC": {"ticker": "BTC-USD", "name": "Bitcoin"},
    "ETH": {"ticker": "ETH-USD", "name": "Ethereum"},
    "SOL": {"ticker": "SOL-USD", "name": "Solana"},
    "SPX": {"ticker": "^GSPC", "name": "S&P 500"},
    "DXY": {"ticker": "DX-Y.NYB", "name": "US Dollar Index"},
}

HORIZONS = {
    "7D": 7,
    "30D": 30,
    "90D": 90,
}


def _get_price_data(ticker: str, period: str = "6mo"):
    """Fetch price history from yfinance."""
    try:
        import yfinance as yf
        data = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if data.empty:
            return None
        return data
    except Exception as e:
        logger.error(f"[Fractal] Price fetch error for {ticker}: {e}")
        return None


def _compute_technical_signals(prices) -> dict:
    """Compute technical indicators from price history."""
    if prices is None or len(prices) < 20:
        return {"direction": "NEUTRAL", "confidence": 0.3, "volatility": 0.02}
    
    close = prices['Close'].values.flatten()
    current = float(close[-1])
    
    # Simple Moving Averages
    sma_20 = float(close[-20:].mean())
    sma_50 = float(close[-50:].mean()) if len(close) >= 50 else sma_20
    
    # Price change metrics
    change_7d = (current - float(close[-7])) / float(close[-7]) if len(close) >= 7 else 0
    change_30d = (current - float(close[-30])) / float(close[-30]) if len(close) >= 30 else 0
    
    # Volatility (30d annualized)
    import numpy as np
    n = min(30, len(close) - 1)
    returns = np.diff(close[-n-1:]) / close[-n-1:-1] if n > 1 else np.array([0.02])
    volatility = float(np.std(returns) * (365 ** 0.5)) if len(returns) > 1 else 0.02
    
    # Trend direction
    above_sma20 = current > sma_20
    above_sma50 = current > sma_50
    sma_cross = sma_20 > sma_50
    
    bullish_score = sum([above_sma20, above_sma50, sma_cross, change_7d > 0, change_30d > 0])
    
    if bullish_score >= 4:
        direction = "BULLISH"
        confidence = min(0.8 + change_30d, 0.95)
    elif bullish_score >= 3:
        direction = "MILD_BULL"
        confidence = 0.55 + abs(change_7d)
    elif bullish_score <= 1:
        direction = "BEARISH"
        confidence = min(0.8 + abs(change_30d), 0.95)
    elif bullish_score == 2:
        direction = "MILD_BEAR"
        confidence = 0.55 + abs(change_7d)
    else:
        direction = "NEUTRAL"
        confidence = 0.4
    
    return {
        "direction": direction,
        "confidence": max(0.1, min(confidence, 0.95)),
        "volatility": volatility,
        "current_price": current,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "change_7d": change_7d,
        "change_30d": change_30d,
        "trend_strength": bullish_score / 5.0,
    }


def _generate_target_price(current: float, direction: str, horizon_days: int, volatility: float, trend_strength: float) -> float:
    """Compute target price based on direction, volatility, and trend strength (NO randomness)."""
    # Expected move = volatility * sqrt(horizon/365) * trend_strength
    time_factor = (horizon_days / 365) ** 0.5
    base_move = volatility * time_factor
    
    # Scale by trend strength (0.0 to 1.0)
    scaled_move = base_move * max(0.3, trend_strength)
    
    # Direction multiplier
    if "BULL" in direction:
        move = scaled_move
    elif "BEAR" in direction:
        move = -scaled_move
    else:
        move = scaled_move * 0.1  # Slight drift for neutral
    
    return round(current * (1 + move), 2)


def generate_fractal_forecasts(scope: str = "BTC"):
    """Generate fractal forecasts for a given scope."""
    config = SCOPES.get(scope)
    if not config:
        logger.error(f"[Fractal] Unknown scope: {scope}")
        return []
    
    ticker = config["ticker"]
    prices = _get_price_data(ticker)
    if prices is None:
        logger.error(f"[Fractal] No price data for {scope} ({ticker})")
        return []
    
    signals = _compute_technical_signals(prices)
    current_price = signals["current_price"]
    now = datetime.now(timezone.utc)
    
    forecasts = []
    col = _db[f"{scope.lower()}_fractal_forecasts"]
    
    for horizon_key, horizon_days in HORIZONS.items():
        target = _generate_target_price(
            current_price, signals["direction"], horizon_days,
            signals["volatility"], signals["trend_strength"]
        )
        expected_return = (target - current_price) / current_price
        
        direction_map = {
            "BULLISH": "UP", "MILD_BULL": "UP",
            "BEARISH": "DOWN", "MILD_BEAR": "DOWN",
            "NEUTRAL": "FLAT",
        }
        
        forecast = {
            "scope": scope,
            "horizon": horizon_key,
            "createdAt": now,
            "evaluateAt": now + timedelta(days=horizon_days),
            "entryPrice": round(current_price, 2),
            "targetPrice": round(target, 2),
            "expectedReturn": round(expected_return, 4),
            "direction": direction_map.get(signals["direction"], "FLAT"),
            "confidence": round(signals["confidence"], 2),
            "modelVersion": "fractal-python-v1.0",
            "source": "python_ta",
            "signalId": f"fractal_{scope}_{horizon_key}_{now.strftime('%Y%m%d%H%M')}",
            "entryPriceSource": "yfinance",
            "status": "pending",
            "actualPrice": None,
            "errorPct": None,
            "hit": None,
            "directionCorrect": None,
            "fractal_eval": None,
            "technicals": {
                "sma_20": round(signals["sma_20"], 2),
                "sma_50": round(signals["sma_50"], 2),
                "volatility": round(signals["volatility"], 4),
                "change_7d": round(signals["change_7d"], 4),
                "change_30d": round(signals["change_30d"], 4),
                "trend_strength": round(signals["trend_strength"], 2),
            },
        }
        
        col.insert_one(forecast)
        forecasts.append(forecast)
        logger.info(f"[Fractal] {scope}/{horizon_key}: {forecast['direction']} @ ${current_price:,.2f} → ${target:,.2f} ({expected_return:+.2%})")
    
    return forecasts


def generate_all_fractal_forecasts():
    """Generate fractal forecasts for all scopes."""
    all_forecasts = []
    for scope in SCOPES:
        try:
            forecasts = generate_fractal_forecasts(scope)
            all_forecasts.extend(forecasts)
        except Exception as e:
            logger.error(f"[Fractal] Error generating {scope}: {e}")
    return all_forecasts


def get_fractal_summary(scope: str) -> dict:
    """Get the latest fractal analysis summary for a scope."""
    col = _db[f"{scope.lower()}_fractal_forecasts"]
    
    forecasts = list(col.find({"scope": scope}).sort("createdAt", -1).limit(3))
    
    if not forecasts:
        return {
            "scope": scope,
            "status": "no_data",
            "message": f"No fractal forecasts for {scope}. Run generation first.",
        }
    
    # Build summary
    latest = forecasts[0]
    
    return {
        "scope": scope,
        "status": "active",
        "currentPrice": latest.get("entryPrice"),
        "direction": latest.get("direction"),
        "confidence": latest.get("confidence"),
        "modelVersion": latest.get("modelVersion"),
        "createdAt": latest.get("createdAt").isoformat() if latest.get("createdAt") else None,
        "horizons": [
            {
                "horizon": f.get("horizon"),
                "targetPrice": f.get("targetPrice"),
                "expectedReturn": f.get("expectedReturn"),
                "direction": f.get("direction"),
                "confidence": f.get("confidence"),
                "evaluateAt": f.get("evaluateAt").isoformat() if f.get("evaluateAt") else None,
            }
            for f in forecasts
        ],
        "technicals": latest.get("technicals", {}),
    }
