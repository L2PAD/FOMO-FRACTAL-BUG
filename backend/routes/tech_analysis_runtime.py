"""
tech_analysis_runtime — production adapter for Tech Analysis tabs.

Provides REAL data for /api/market/* and /api/tech-analysis/* endpoints
which were previously caught by legacy_compat and returned empty stubs.

Routes (registered BEFORE legacy_compat_router):
  GET  /api/market/candles?symbol=BTCUSDT&timeframe=4h&limit=200
  GET  /api/market/state?symbol=BTCUSDT
  GET  /api/market/regime?symbol=BTCUSDT
  GET  /api/tech-analysis/{symbol}
  GET  /api/ta-prediction/{symbol}?timeframe=4H

Data sources:
  • Binance public REST /api/v3/klines (OHLC, multi-timeframe)
  • services.asset_intelligence (TA state + module breakdown)
  • services.bar_data (1m bars cache)

No mocks. No external paid APIs. Graceful degradation on network failure.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import requests
from fastapi import APIRouter, Query

logger = logging.getLogger("tech_analysis_runtime")
router = APIRouter()


# ──────────────────────────────────────────────────────────────────────────
# Symbol normalization
# ──────────────────────────────────────────────────────────────────────────
def _to_binance_pair(symbol: str) -> str:
    """Normalize 'BTC' / 'BTCUSDT' / 'btc-usdt' → 'BTCUSDT'."""
    s = (symbol or "BTC").upper().replace("-", "").replace("/", "").replace("_", "")
    if s.endswith("USDT"):
        return s
    if s.endswith("USD"):
        return s + "T"
    return s + "USDT"


def _to_canonical(symbol: str) -> str:
    """'BTCUSDT' / 'BTC' → 'BTC'."""
    s = (symbol or "BTC").upper().replace("-", "").replace("/", "").replace("_", "")
    return s.replace("USDT", "").replace("USD", "") or "BTC"


# ──────────────────────────────────────────────────────────────────────────
# Timeframe mapping
# ──────────────────────────────────────────────────────────────────────────
# Map UI timeframe → OKX bar code + ms per bar
# OKX bars: 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M
_TF_MAP = {
    "1M":  ("1m",  60_000),
    "5M":  ("5m",  300_000),
    "15M": ("15m", 900_000),
    "1H":  ("1H",  3_600_000),
    "2H":  ("2H",  7_200_000),
    "4H":  ("4H",  14_400_000),
    "6H":  ("6H",  21_600_000),
    "12H": ("12H", 43_200_000),
    "1D":  ("1D",  86_400_000),
    "3D":  ("1D",  86_400_000),   # OKX has no 3D — use 1D
    "7D":  ("1W",  604_800_000),
    "1W":  ("1W",  604_800_000),
    "1MO": ("1M",  2_592_000_000),
    "6M":  ("1D",  86_400_000),   # 6M view → daily candles
    "1Y":  ("1D",  86_400_000),   # 1Y view → daily candles
}


def _resolve_tf(tf: str) -> tuple[str, int]:
    """Returns (binance_interval, ms_per_bar). Defaults to 4h."""
    return _TF_MAP.get((tf or "4H").upper(), _TF_MAP["4H"])


# ──────────────────────────────────────────────────────────────────────────
# Candle cache (TTL 30s) — OKX primary, CoinGecko fallback
# ──────────────────────────────────────────────────────────────────────────
_OKX_URL = "https://www.okx.com/api/v5/market/candles"
_COINGECKO_OHLC_URL = "https://api.coingecko.com/api/v3/coins/{id}/ohlc"

# Map our canonical symbol to CoinGecko id (for fallback)
_COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "DOGE": "dogecoin", "XRP": "ripple", "ADA": "cardano", "AVAX": "avalanche-2",
    "LINK": "chainlink", "MATIC": "matic-network", "DOT": "polkadot", "TON": "the-open-network",
    "ARB": "arbitrum", "OP": "optimism", "SUI": "sui", "APT": "aptos",
    "TIA": "celestia", "JTO": "jito-governance-token", "PYTH": "pyth-network",
    "SEI": "sei-network", "STRK": "starknet", "BLAST": "blast",
    "ONDO": "ondo-finance", "ENA": "ethena", "WLD": "worldcoin-wld",
    "INJ": "injective-protocol", "FET": "fetch-ai", "RNDR": "render-token",
    "ATOM": "cosmos", "NEAR": "near", "FIL": "filecoin", "LTC": "litecoin",
    "BCH": "bitcoin-cash", "ETC": "ethereum-classic", "TRX": "tron",
}

_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_LOCK = threading.RLock()
_CACHE_TTL = 30.0


def _fetch_candles_okx(pair: str, bar: str, limit: int) -> List[Dict[str, Any]]:
    """Pull klines from OKX public REST.  Returns ascending OHLC list."""
    okx_inst = pair.replace("USDT", "-USDT")  # BTCUSDT → BTC-USDT
    try:
        r = requests.get(
            _OKX_URL,
            params={"instId": okx_inst, "bar": bar, "limit": max(1, min(limit, 300))},
            timeout=5.0,
        )
        r.raise_for_status()
        payload = r.json() or {}
        raw = payload.get("data", [])
    except Exception as e:
        logger.warning(f"[ta_runtime] OKX fetch failed {pair}/{bar}: {e}")
        return []

    bars: List[Dict[str, Any]] = []
    # OKX returns NEWEST first — reverse it
    for k in reversed(raw):
        if not isinstance(k, list) or len(k) < 6:
            continue
        try:
            ts = int(k[0])
            bars.append({
                "time":      ts // 1000,
                "openTime":  ts,
                "closeTime": ts,  # OKX gives open time only; close = open + bar
                "open":  float(k[1]),
                "high":  float(k[2]),
                "low":   float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })
        except (TypeError, ValueError):
            continue
    return bars


def _fetch_candles_coingecko(canonical: str, days: int) -> List[Dict[str, Any]]:
    """CoinGecko OHLC fallback. `days` ∈ {1,7,14,30,90,180,365}."""
    cg_id = _COINGECKO_IDS.get(canonical)
    if not cg_id:
        return []
    try:
        r = requests.get(
            _COINGECKO_OHLC_URL.format(id=cg_id),
            params={"vs_currency": "usd", "days": days},
            timeout=6.0,
        )
        r.raise_for_status()
        raw = r.json() or []
    except Exception as e:
        logger.warning(f"[ta_runtime] CoinGecko fetch failed {canonical}/{days}d: {e}")
        return []
    bars: List[Dict[str, Any]] = []
    for k in raw:
        if not isinstance(k, list) or len(k) < 5:
            continue
        try:
            ts = int(k[0])
            close = float(k[4])
            bars.append({
                "time": ts // 1000, "openTime": ts, "closeTime": ts,
                "open":  float(k[1]),
                "high":  float(k[2]),
                "low":   float(k[3]),
                "close": close,
                "volume": 0.0,
            })
        except (TypeError, ValueError):
            continue
    return bars


def _fetch_candles(pair: str, interval: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Cached fetcher: OKX first, CoinGecko fallback."""
    cache_key = f"{pair}:{interval}:{limit}"
    with _CACHE_LOCK:
        ent = _CACHE.get(cache_key)
        if ent and time.time() - ent["t"] < _CACHE_TTL:
            return list(ent["bars"])

    bars = _fetch_candles_okx(pair, interval, limit)
    if not bars:
        # Fallback to CoinGecko (daily granularity for now)
        canonical = pair.replace("USDT", "").replace("USD", "")
        # Map interval → days approximation
        days = 1 if interval in ("1m", "5m", "15m", "1H") else \
               7 if interval in ("2H", "4H", "6H") else \
               30 if interval in ("12H", "1D") else 90
        bars = _fetch_candles_coingecko(canonical, days)

    with _CACHE_LOCK:
        _CACHE[cache_key] = {"t": time.time(), "bars": bars}
    return bars


# ──────────────────────────────────────────────────────────────────────────
# Technical indicators (pure-python, no deps)
# ──────────────────────────────────────────────────────────────────────────
def _ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    ema_v = values[0]
    for v in values[1:]:
        ema_v = v * k + ema_v * (1 - k)
    return ema_v


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) <= period:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = max(diff, 0)
        loss = max(-diff, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(closes: List[float]) -> Dict[str, Optional[float]]:
    if len(closes) < 35:
        return {"macd": None, "signal": None, "hist": None}
    ema12 = _ema(closes[-26:], 12)
    ema26 = _ema(closes, 26)
    if ema12 is None or ema26 is None:
        return {"macd": None, "signal": None, "hist": None}
    macd_v = ema12 - ema26
    # signal = EMA9 of MACD (we approximate via short calc)
    return {"macd": round(macd_v, 4), "signal": None, "hist": None}


def _support_resistance(bars: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Simple pivot-based S/R from last 50 bars."""
    if len(bars) < 20:
        return {"support": None, "resistance": None}
    recent = bars[-50:]
    lows = sorted([b["low"] for b in recent])
    highs = sorted([b["high"] for b in recent], reverse=True)
    # Take 5th percentile low and 5th percentile high
    n = max(1, len(lows) // 20)
    return {
        "support":    round(sum(lows[:n]) / n, 6),
        "resistance": round(sum(highs[:n]) / n, 6),
    }


def _compute_indicators(bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not bars:
        return {}
    closes = [b["close"] for b in bars]
    last = bars[-1]
    first = bars[0]
    sr = _support_resistance(bars)
    ema20 = _ema(closes[-20:], 20) if len(closes) >= 20 else None
    ema50 = _ema(closes[-50:], 50) if len(closes) >= 50 else None
    ema200 = _ema(closes[-200:], 200) if len(closes) >= 200 else None
    rsi = _rsi(closes, 14)
    macd = _macd(closes)
    change_pct = ((last["close"] - first["close"]) / first["close"] * 100) if first["close"] else 0

    # Trend classification
    if ema20 and ema50:
        if last["close"] > ema20 > ema50:
            trend = "uptrend"
        elif last["close"] < ema20 < ema50:
            trend = "downtrend"
        else:
            trend = "ranging"
    else:
        trend = "unknown"

    # Momentum
    if rsi is None:
        momentum = "unknown"
    elif rsi >= 70:
        momentum = "overbought"
    elif rsi <= 30:
        momentum = "oversold"
    elif rsi > 55:
        momentum = "bullish"
    elif rsi < 45:
        momentum = "bearish"
    else:
        momentum = "neutral"

    return {
        "price":     last["close"],
        "high24h":   max(b["high"] for b in bars[-24:]) if len(bars) >= 24 else last["high"],
        "low24h":    min(b["low"] for b in bars[-24:]) if len(bars) >= 24 else last["low"],
        "changePct": round(change_pct, 2),
        "rsi":       round(rsi, 2) if rsi is not None else None,
        "ema20":     round(ema20, 6) if ema20 else None,
        "ema50":     round(ema50, 6) if ema50 else None,
        "ema200":    round(ema200, 6) if ema200 else None,
        "macd":      macd["macd"],
        "support":   sr["support"],
        "resistance": sr["resistance"],
        "trend":     trend,
        "momentum":  momentum,
    }


# ──────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/api/market/candles")
def market_candles(
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("4h"),
    limit: int = Query(200, ge=1, le=1000),
):
    pair = _to_binance_pair(symbol)
    interval, ms = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, limit)
    return {
        "ok": True,
        "path": "/api/market/candles",
        "symbol": pair,
        "canonicalSymbol": _to_canonical(symbol),
        "timeframe": timeframe.upper(),
        "interval": interval,
        "candles": bars,
        "items": bars,
        "count": len(bars),
        "asOf": _now_iso(),
        "source": "okx_public_rest_or_coingecko_fallback",
    }


@router.get("/api/market/state")
def market_state(
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("4h"),
):
    pair = _to_binance_pair(symbol)
    interval, _ = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, 200)
    indicators = _compute_indicators(bars)

    # Macro / short-term derive from trend + momentum
    trend = indicators.get("trend", "unknown")
    momentum = indicators.get("momentum", "unknown")
    macro = "Bullish" if trend == "uptrend" else "Bearish" if trend == "downtrend" else "Neutral"
    mid_term = trend.capitalize() if trend != "unknown" else "Developing"
    short_term = "Trending" if trend in ("uptrend", "downtrend") else "Consolidation"

    # Confidence: blend of trend clarity + RSI extremes
    rsi = indicators.get("rsi") or 50
    rsi_pull = abs(rsi - 50) / 50  # 0..1
    trend_pull = 0.8 if trend in ("uptrend", "downtrend") else 0.3
    confidence = round(min(0.95, 0.3 + 0.4 * trend_pull + 0.3 * rsi_pull), 2)

    return {
        "ok": True,
        "path": "/api/market/state",
        "symbol": pair,
        "canonicalSymbol": _to_canonical(symbol),
        "timeframe": timeframe.upper(),
        "macro": macro,
        "midTerm": mid_term,
        "shortTerm": short_term,
        "confidence": confidence,
        "tradeability": "High" if confidence >= 0.6 else "Medium" if confidence >= 0.4 else "Low",
        "indicators": indicators,
        "coreInsight": _build_core_insight(trend, momentum, indicators),
        "asOf": _now_iso(),
        "source": "okx_public_rest_or_coingecko_fallback",
    }


def _build_core_insight(trend: str, momentum: str, ind: Dict[str, Any]) -> Dict[str, Any]:
    rsi = ind.get("rsi") or 50
    if trend == "uptrend" and momentum == "overbought":
        title = "Uptrend extended"
        text = f"Price above EMA20/50; RSI={rsi:.0f} (overbought). Watch for pullback."
    elif trend == "uptrend":
        title = "Uptrend developing"
        text = f"Price above EMA20={ind.get('ema20')}; RSI={rsi:.0f}. Momentum constructive."
    elif trend == "downtrend" and momentum == "oversold":
        title = "Downtrend extended"
        text = f"Price below EMA20/50; RSI={rsi:.0f} (oversold). Watch for bounce."
    elif trend == "downtrend":
        title = "Downtrend developing"
        text = f"Price below EMA20={ind.get('ema20')}; RSI={rsi:.0f}. Risk-off pressure."
    else:
        title = "Analyzing market structure"
        text = "Price ranging between support/resistance. Waiting for confirmation signal."
    return {"title": title, "text": text}


@router.get("/api/market/regime")
def market_regime(symbol: str = Query("BTCUSDT")):
    """Lightweight regime indicator: which OHLC structure dominates."""
    pair = _to_binance_pair(symbol)
    bars = _fetch_candles(pair, "4h", 200)
    if not bars:
        return {"ok": True, "regime": "unknown", "confidence": 0, "asOf": _now_iso()}
    closes = [b["close"] for b in bars]
    ema20 = _ema(closes[-20:], 20)
    ema50 = _ema(closes[-50:], 50)
    if ema20 and ema50:
        if ema20 > ema50 * 1.01:
            regime = "trending_up"
        elif ema20 < ema50 * 0.99:
            regime = "trending_down"
        else:
            regime = "ranging"
    else:
        regime = "unknown"
    return {
        "ok": True,
        "path": "/api/market/regime",
        "symbol": pair,
        "regime": regime,
        "ema20": ema20,
        "ema50": ema50,
        "asOf": _now_iso(),
    }


@router.get("/api/tech-analysis/{symbol}")
def tech_analysis(symbol: str, timeframe: str = Query("4h")):
    """Combined TA module output — used by Web Tech Analysis tab and MiniApp."""
    pair = _to_binance_pair(symbol)
    interval, _ = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, 200)
    indicators = _compute_indicators(bars)
    trend = indicators.get("trend", "unknown")
    momentum = indicators.get("momentum", "unknown")
    price = indicators.get("price")
    support = indicators.get("support")
    resistance = indicators.get("resistance")

    # Action recommendation
    if trend == "uptrend" and momentum in ("bullish", "neutral"):
        action = "LONG"
        action_reason = f"EMA stack bullish, RSI={indicators.get('rsi')}"
    elif trend == "downtrend" and momentum in ("bearish", "neutral"):
        action = "SHORT"
        action_reason = f"EMA stack bearish, RSI={indicators.get('rsi')}"
    elif momentum == "overbought":
        action = "WAIT"
        action_reason = "RSI overbought, wait for pullback"
    elif momentum == "oversold":
        action = "WAIT"
        action_reason = "RSI oversold, wait for bounce confirmation"
    else:
        action = "WAIT"
        action_reason = "No clear directional bias"

    return {
        "ok": True,
        "path": f"/api/tech-analysis/{symbol}",
        "symbol": pair,
        "canonicalSymbol": _to_canonical(symbol),
        "timeframe": timeframe.upper(),
        "action": action,
        "actionReason": action_reason,
        "trend": trend,
        "momentum": momentum,
        "price": price,
        "support": support,
        "resistance": resistance,
        "indicators": indicators,
        "candles": bars[-50:],  # ostatnich 50 для embedded chart
        "asOf": _now_iso(),
        "source": "tech_analysis_runtime",
    }


@router.get("/api/ta-prediction/{symbol}")
def ta_prediction(symbol: str, timeframe: str = Query("4H"), horizon: int = Query(5, ge=1, le=20)):
    """Rolling TA forecast: project next N bars based on trend extrapolation."""
    pair = _to_binance_pair(symbol)
    interval, _ = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, 200)
    if not bars:
        return {
            "ok": True,
            "symbol": pair,
            "forecasts": [],
            "horizons": [],
            "asOf": _now_iso(),
        }
    indicators = _compute_indicators(bars)
    last = bars[-1]
    closes = [b["close"] for b in bars[-30:]]
    # Linear regression slope on last 30 bars
    n = len(closes)
    xs = list(range(n))
    sum_x = sum(xs)
    sum_y = sum(closes)
    sum_xy = sum(x * y for x, y in zip(xs, closes))
    sum_xx = sum(x * x for x in xs)
    denom = n * sum_xx - sum_x * sum_x
    slope = (n * sum_xy - sum_x * sum_y) / denom if denom else 0
    intercept = (sum_y - slope * sum_x) / n

    forecasts = []
    for i in range(1, horizon + 1):
        projected = intercept + slope * (n - 1 + i)
        # Confidence decays with horizon
        conf = max(0.2, 0.85 - 0.05 * i)
        # Range widens with horizon
        sigma = abs(slope) * i + (last["close"] * 0.005 * i)
        forecasts.append({
            "step": i,
            "projected": round(projected, 6),
            "high": round(projected + sigma, 6),
            "low": round(projected - sigma, 6),
            "confidence": round(conf, 2),
        })

    # Direction summary
    if slope > 0:
        direction = "bullish"
    elif slope < 0:
        direction = "bearish"
    else:
        direction = "flat"

    return {
        "ok": True,
        "path": f"/api/ta-prediction/{symbol}",
        "symbol": pair,
        "canonicalSymbol": _to_canonical(symbol),
        "timeframe": timeframe.upper(),
        "currentPrice": last["close"],
        "slope": slope,
        "direction": direction,
        "horizonBars": horizon,
        "forecasts": forecasts,
        "indicators": indicators,
        "asOf": _now_iso(),
        "source": "ta_rolling_forecast_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# Dashboard state aggregation (multi-symbol) — used by Trading dashboards
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/dashboard/regime")
def dashboard_regime():
    """Multi-symbol regime snapshot."""
    symbols = ["BTC", "ETH", "SOL", "BNB", "DOGE", "XRP"]
    out = []
    for sym in symbols:
        pair = _to_binance_pair(sym)
        bars = _fetch_candles(pair, "4H", 100)
        if not bars:
            out.append({"symbol": sym, "regime": "unknown"})
            continue
        ind = _compute_indicators(bars)
        out.append({
            "symbol":   sym,
            "regime":   ind.get("trend", "unknown"),
            "price":    ind.get("price"),
            "rsi":      ind.get("rsi"),
            "changePct": ind.get("changePct"),
        })
    return {
        "ok": True,
        "path": "/api/dashboard/regime",
        "symbols": out,
        "asOf": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────────────
# Multi-Timeframe TA Engine — KEY endpoint used by ResearchViewNew (Analysis tab)
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/ta-engine/mtf/{symbol}")
def ta_engine_mtf(symbol: str, timeframes: str = Query("4H,1D,7D,30D,180D,1Y")):
    """Return per-timeframe TA snapshot. Used by Analysis tab.

    Expected response shape (matches ResearchViewNew):
      {
        ok: true,
        symbol: "BTC",
        tf_map: {
          "4H":  { state, momentum, levels, indicators, candles, action, ... },
          "1D":  { ... },
          ...
        },
        consensus: { action, confidence, reasons }
      }
    """
    pair = _to_binance_pair(symbol)
    canonical = _to_canonical(symbol)
    tf_list = [tf.strip().upper() for tf in (timeframes or "4H,1D").split(",") if tf.strip()]
    tf_map: Dict[str, Any] = {}

    long_votes = 0
    short_votes = 0
    wait_votes = 0
    all_reasons: List[str] = []

    for tf in tf_list:
        interval, _ = _resolve_tf(tf)
        bars = _fetch_candles(pair, interval, 200)
        if not bars:
            tf_map[tf] = {
                "ok": False, "state": "unknown", "candles": [], "indicators": {},
                "note": "no_data"
            }
            continue
        ind = _compute_indicators(bars)
        trend = ind.get("trend", "unknown")
        momentum = ind.get("momentum", "unknown")
        rsi = ind.get("rsi") or 50

        # State classification per TF
        if trend == "uptrend":
            state = "BULLISH" if momentum != "overbought" else "BULLISH_EXTENDED"
            action = "LONG"
            long_votes += 1
        elif trend == "downtrend":
            state = "BEARISH" if momentum != "oversold" else "BEARISH_EXTENDED"
            action = "SHORT"
            short_votes += 1
        else:
            state = "NEUTRAL"
            action = "WAIT"
            wait_votes += 1

        reason = f"{tf}: {trend} (RSI={rsi:.0f}, EMA20={ind.get('ema20')}, momentum={momentum})"
        all_reasons.append(reason)

        tf_map[tf] = {
            "ok": True,
            "tf": tf,
            "state": state,
            "action": action,
            "trend": trend,
            "momentum": momentum,
            "price": ind.get("price"),
            "rsi": ind.get("rsi"),
            "macd": ind.get("macd"),
            "ema20": ind.get("ema20"),
            "ema50": ind.get("ema50"),
            "ema200": ind.get("ema200"),
            "support": ind.get("support"),
            "resistance": ind.get("resistance"),
            "changePct": ind.get("changePct"),
            "high24h": ind.get("high24h"),
            "low24h": ind.get("low24h"),
            "indicators": ind,
            "candles": bars[-100:],  # последние 100 для chart
            # `levels` MUST be a flat array — frontend calls levels.filter(l => l.type === 'support')
            "levels": [
                {"type": "support",    "price": ind.get("support"),    "strength": 0.7, "tf": tf},
                {"type": "resistance", "price": ind.get("resistance"), "strength": 0.7, "tf": tf},
                {"type": "ema20",      "price": ind.get("ema20"),      "strength": 0.5, "tf": tf},
                {"type": "ema50",      "price": ind.get("ema50"),      "strength": 0.6, "tf": tf},
            ] if ind.get("support") else [],
            "reason": reason,
        }

    # Consensus across TFs
    total = max(1, long_votes + short_votes + wait_votes)
    if long_votes > short_votes and long_votes >= total / 2:
        consensus_action = "LONG"
        consensus_state = "BULLISH"
    elif short_votes > long_votes and short_votes >= total / 2:
        consensus_action = "SHORT"
        consensus_state = "BEARISH"
    else:
        consensus_action = "WAIT"
        consensus_state = "NEUTRAL"

    confidence = round(max(long_votes, short_votes) / total, 2)

    return {
        "ok": True,
        "path": f"/api/ta-engine/mtf/{symbol}",
        "symbol": canonical,
        "canonicalSymbol": canonical,
        "pair": pair,
        "timeframes": tf_list,
        "tf_map": tf_map,
        "consensus": {
            "action": consensus_action,
            "state": consensus_state,
            "confidence": confidence,
            "longVotes": long_votes,
            "shortVotes": short_votes,
            "waitVotes": wait_votes,
            "reasons": all_reasons,
        },
        "asOf": _now_iso(),
        "source": "ta_engine_mtf_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# Trade Setup — "Trade Setup" button in Analysis tab calls this
# ──────────────────────────────────────────────────────────────────────────
@router.post("/api/trade-this")
async def trade_this(payload: Dict[str, Any]):
    """Generate trade setup for given symbol/timeframe.

    Body: {symbol: "BTCUSDT", timeframe: "4H"}
    Returns: {entry, stop, target, rr, risk, sizeUsd, action, confidence, reasons}
    """
    symbol = payload.get("symbol", "BTCUSDT")
    timeframe = payload.get("timeframe", "4H")
    pair = _to_binance_pair(symbol)
    canonical = _to_canonical(symbol)
    interval, _ = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, 200)
    if not bars:
        return {"ok": False, "error": "no_market_data", "symbol": canonical}

    ind = _compute_indicators(bars)
    price = ind.get("price") or 0
    support = ind.get("support")
    resistance = ind.get("resistance")
    trend = ind.get("trend", "unknown")
    momentum = ind.get("momentum", "unknown")

    # Decide direction
    if trend == "uptrend" and momentum not in ("overbought",):
        action = "LONG"
        entry = price
        stop = support if support and support < price else price * 0.98
        target = resistance if resistance and resistance > price else price * 1.05
    elif trend == "downtrend" and momentum not in ("oversold",):
        action = "SHORT"
        entry = price
        stop = resistance if resistance and resistance > price else price * 1.02
        target = support if support and support < price else price * 0.95
    else:
        return {
            "ok": True,
            "symbol": canonical,
            "timeframe": timeframe,
            "action": "WAIT",
            "reason": f"No directional bias: trend={trend}, momentum={momentum}",
            "indicators": ind,
            "asOf": _now_iso(),
        }

    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = round(reward / risk, 2) if risk > 0 else None

    # Default risk: 1% of $10k portfolio
    portfolio_usd = float(payload.get("portfolioUsd", 10000))
    risk_pct = float(payload.get("riskPct", 0.01))
    risk_usd = portfolio_usd * risk_pct
    size_usd = round((risk_usd / risk) * entry, 2) if risk > 0 else 0

    return {
        "ok": True,
        "symbol": canonical,
        "canonicalSymbol": canonical,
        "pair": pair,
        "timeframe": timeframe.upper(),
        "action": action,
        "entry": round(entry, 6),
        "stop": round(stop, 6),
        "target": round(target, 6),
        "rr": rr,
        "risk": "Medium" if rr and rr >= 1.5 else "High" if rr and rr < 1.2 else "Low",
        "sizeUsd": size_usd,
        "confidence": round(0.4 + (0.4 if trend in ("uptrend","downtrend") else 0) + (0.2 if rr and rr >= 2 else 0), 2),
        "reasons": [
            f"Trend: {trend}",
            f"Momentum: {momentum}",
            f"RSI: {ind.get('rsi')}",
            f"R/R: {rr}",
        ],
        "indicators": ind,
        "asOf": _now_iso(),
        "source": "trade_setup_v1",
    }


# ──────────────────────────────────────────────────────────────────────────
# Compact analytics endpoint for Mobile/MiniApp (single-shot, lightweight)
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/ta/compact/{symbol}")
def ta_compact(symbol: str, timeframe: str = Query("4H")):
    """Compact TA snapshot optimized for Mobile/MiniApp screens.

    Returns minimal payload: action + reason + key levels + sparkline.
    """
    pair = _to_binance_pair(symbol)
    canonical = _to_canonical(symbol)
    interval, _ = _resolve_tf(timeframe)
    bars = _fetch_candles(pair, interval, 100)
    if not bars:
        return {"ok": False, "symbol": canonical, "error": "no_data"}

    ind = _compute_indicators(bars)
    trend = ind.get("trend", "unknown")
    momentum = ind.get("momentum", "unknown")
    rsi = ind.get("rsi") or 50

    # Compact action
    if trend == "uptrend" and rsi < 70:
        action = "LONG"
        emoji = "📈"
    elif trend == "downtrend" and rsi > 30:
        action = "SHORT"
        emoji = "📉"
    else:
        action = "WAIT"
        emoji = "⏸"

    # Sparkline: last 20 closes (normalized 0..1)
    closes = [b["close"] for b in bars[-20:]]
    lo, hi = min(closes), max(closes)
    spark = [round((c - lo) / (hi - lo) * 100, 1) if hi > lo else 50 for c in closes]

    return {
        "ok": True,
        "symbol": canonical,
        "pair": pair,
        "timeframe": timeframe.upper(),
        "action": action,
        "emoji": emoji,
        "price": ind.get("price"),
        "changePct": ind.get("changePct"),
        "rsi": ind.get("rsi"),
        "trend": trend,
        "momentum": momentum,
        "support": ind.get("support"),
        "resistance": ind.get("resistance"),
        "sparkline": spark,
        "reason": f"{trend.title()} on {timeframe.upper()}, RSI={rsi:.0f}",
        "asOf": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────────────
# Multi-symbol watchlist for Mobile/MiniApp Tech Analysis dashboard
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/ta/watchlist")
def ta_watchlist(symbols: str = Query("BTC,ETH,SOL,DOGE,ARB,XRP,BNB,AVAX")):
    """Returns compact TA for multiple assets — for dashboard lists."""
    syms = [s.strip().upper() for s in (symbols or "BTC,ETH").split(",") if s.strip()]
    out = []
    for sym in syms[:20]:  # cap at 20
        try:
            data = ta_compact(sym, "4H")
            if data.get("ok"):
                out.append(data)
        except Exception as e:
            logger.info(f"  watchlist {sym} skipped: {e}")
    return {
        "ok": True,
        "path": "/api/ta/watchlist",
        "items": out,
        "count": len(out),
        "asOf": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────────────
# MiniApp Tech Analysis endpoint — single-shot, optimized payload for TG
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/miniapp/tech-analysis")
def miniapp_tech_analysis(asset: str = Query("BTC"), timeframe: str = Query("4H")):
    """Mobile-friendly Tech Analysis screen for Telegram MiniApp.

    Returns: a small payload with key metrics + sparkline + 4 multi-TF
    snapshots, designed to render quickly in a Telegram WebView.
    """
    canonical = _to_canonical(asset)
    pair = _to_binance_pair(asset)

    # 1. Compact for selected TF
    compact = ta_compact(canonical, timeframe)
    if not compact.get("ok"):
        return {"ok": False, "asset": canonical, "error": "no_data"}

    # 2. Multi-TF brief (4H, 1D, 7D, 30D) — only state + action
    tfs = ["4H", "1D", "7D", "30D"]
    mtf_brief = []
    for tf in tfs:
        interval, _ = _resolve_tf(tf)
        bars = _fetch_candles(pair, interval, 100)
        if not bars:
            mtf_brief.append({"tf": tf, "ok": False})
            continue
        ind = _compute_indicators(bars)
        trend = ind.get("trend", "unknown")
        rsi = ind.get("rsi") or 50
        if trend == "uptrend":
            state, action, color = "BULLISH", "LONG", "#10b981"
        elif trend == "downtrend":
            state, action, color = "BEARISH", "SHORT", "#ef4444"
        else:
            state, action, color = "NEUTRAL", "WAIT", "#94a3b8"
        mtf_brief.append({
            "tf": tf, "ok": True,
            "state": state, "action": action, "color": color,
            "rsi": round(rsi, 1),
            "price": ind.get("price"),
            "trend": trend,
        })

    # 3. Trade idea (if any)
    trade_setup = None
    if compact["action"] in ("LONG", "SHORT"):
        try:
            ts = trade_this({"symbol": pair, "timeframe": timeframe, "portfolioUsd": 1000, "riskPct": 0.01})
            if isinstance(ts, dict) and ts.get("ok") and ts.get("action") != "WAIT":
                trade_setup = {
                    "action": ts["action"],
                    "entry": ts["entry"],
                    "stop": ts["stop"],
                    "target": ts["target"],
                    "rr": ts["rr"],
                    "confidence": ts["confidence"],
                }
        except Exception:
            pass

    return {
        "ok": True,
        "asset": canonical,
        "pair": pair,
        "timeframe": timeframe.upper(),
        "price": compact.get("price"),
        "changePct": compact.get("changePct"),
        "rsi": compact.get("rsi"),
        "trend": compact.get("trend"),
        "momentum": compact.get("momentum"),
        "action": compact.get("action"),
        "emoji": compact.get("emoji"),
        "support": compact.get("support"),
        "resistance": compact.get("resistance"),
        "sparkline": compact.get("sparkline"),
        "reason": compact.get("reason"),
        "mtf": mtf_brief,
        "tradeSetup": trade_setup,
        "asOf": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────────────
# MiniApp watchlist — top N assets compact view
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/miniapp/tech-watchlist")
def miniapp_tech_watchlist(symbols: str = Query("BTC,ETH,SOL,DOGE,ARB,XRP")):
    """Compact multi-asset TA list for MiniApp dashboard."""
    res = ta_watchlist(symbols)
    return res
