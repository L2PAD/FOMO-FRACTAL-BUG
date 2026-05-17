"""
technical_analysis — Stage A-2: TA as a perception layer.

Native-Python truthful TA v1.  NOT a charting service.  NOT a pattern
detection engine.  NOT a "BUY/SELL" signal generator.

This is *one* cognitive contributor among many — it observes price
structure and emits an honest opinion with conservative bias:

    - WAIT is the default
    - LONG_BIAS / SHORT_BIAS only when multiple indicators align
    - degraded state surfaces explicitly when history is missing
    - confidence is suppression-friendly (capped unless many signals align)
    - reasons[] explains why, in plain language

Data source:
    Historical daily candles via CoinGecko `market_chart` endpoint.
    Live spot price comes from services.market_prices.

Cache:
    History — 5 minute TTL per symbol (separate from spot 60s cache).
    No DB writes.

Contract (success):
    {
        symbol, ok=true,
        state ∈ {bullish, bearish, neutral},
        direction ∈ {WAIT, LONG_BIAS, SHORT_BIAS},
        confidence ∈ [0..1],
        trend ∈ {up, down, range},
        momentum ∈ {accelerating, decelerating, flat},
        rsi ∈ {overbought, oversold, neutral},
        volatility ∈ {expanded, normal, compressed},
        support, resistance, currentPrice,
        reasons[], source, asOf
    }

Contract (degraded):
    {
        symbol, ok=false, state='unavailable',
        direction='WAIT', confidence=0.0, degraded=true,
        reason='insufficient_price_history' | 'fetch_failed' | 'unsupported_symbol',
        source, asOf
    }
"""

from __future__ import annotations

import statistics
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests

from services.market_prices import (
    SYMBOL_TO_CG_ID, SYMBOLS, get_price as _get_spot,
)


# ─── Tuning ────────────────────────────────────────────────────────────
HISTORY_TTL_SEC = 300                  # 5 min cache for daily candles
HISTORY_DAYS = 30                      # 30 daily candles
COINGECKO_HISTORY_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"
HTTP_TIMEOUT = 8.0

# Minimum candles required for a non-degraded analysis.
MIN_CANDLES = 14

# Trend slope thresholds (% per day).
TREND_FLAT_BAND_PCT = 0.30             # below this → range

# Confidence policy (suppression-friendly).
CONF_PER_INDICATOR = 0.14              # each aligned indicator contributes
CONF_SOFT_CAP_BELOW_ALIGN = 0.55       # cap unless 4+ indicators align
SIGNALS_REQUIRED_FOR_BIAS = 3          # min aligned signals to leave WAIT

# ─── In-memory history cache ───────────────────────────────────────────
_hist_lock = threading.RLock()
_history: Dict[str, dict] = {}         # symbol → {"prices":[...], "fetched_at":ts}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_history(symbol: str) -> Tuple[List[float], Optional[str]]:
    """Returns (prices_list, error_or_None).  Daily candles, USD, asc by time.

    Source hierarchy (P2 activation):
      1. CoinGecko (preferred — clean USD prices)
      2. Binance fallback (free, generous rate-limit) — when CoinGecko 429s

    Cache TTL is shared between the two sources so we never thrash.
    """
    sym_upper = symbol.upper()
    cg_id = SYMBOL_TO_CG_ID.get(sym_upper)
    if not cg_id:
        return [], "unsupported_symbol"

    with _hist_lock:
        cached = _history.get(symbol)
        if cached and time.time() - cached["fetched_at"] < HISTORY_TTL_SEC:
            return list(cached["prices"]), None

    prices: List[float] = []
    cg_error: Optional[str] = None
    try:
        url = COINGECKO_HISTORY_URL.format(id=cg_id)
        r = requests.get(
            url,
            params={
                "vs_currency": "usd",
                "days": HISTORY_DAYS,
                "interval": "daily",
            },
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        body = r.json() or {}
        raw = body.get("prices") or []
        prices = [float(p[1]) for p in raw if isinstance(p, list) and len(p) == 2 and p[1] is not None]
    except Exception as e:
        cg_error = f"coingecko_{type(e).__name__}"
        prices = []

    # Binance fallback when CoinGecko empty / failed (typically rate-limit 429)
    if not prices:
        try:
            binance_symbol = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}.get(sym_upper)
            if binance_symbol:
                br = requests.get(
                    "https://api.binance.com/api/v3/klines",
                    params={"symbol": binance_symbol, "interval": "1d", "limit": HISTORY_DAYS},
                    timeout=HTTP_TIMEOUT,
                )
                br.raise_for_status()
                kl = br.json() or []
                # kline: [openTime, open, high, low, close, ...]; close index = 4
                prices = [float(row[4]) for row in kl if isinstance(row, list) and len(row) > 4]
        except Exception as e:
            # P1-D · Defer to CCXT cascade below before declaring failure.
            binance_error = f"binance_{type(e).__name__}"
        else:
            binance_error = None
    else:
        binance_error = None

    # P1-D · CCXT cascade fallback (coinbase → kraken → kucoin → okx).
    # Both CoinGecko and Binance are unreliable from this environment
    # (429 / 451 respectively), but the listed CEXes return daily OHLC
    # consistently via `ccxt`. This is the third and final tier.
    ccxt_error: Optional[str] = None
    if not prices:
        try:
            from market_data.ohlc_provider import fetch_daily_closes as _ccxt_closes
            cc_prices, cc_err = _ccxt_closes(sym_upper, HISTORY_DAYS)
            if cc_prices and len(cc_prices) >= MIN_CANDLES:
                prices = cc_prices
            else:
                ccxt_error = cc_err or "ccxt_insufficient"
        except Exception as e:
            ccxt_error = f"ccxt_{type(e).__name__}"

    if not prices:
        with _hist_lock:
            if symbol in _history:
                return list(_history[symbol]["prices"]), None
        parts = [p for p in (cg_error, binance_error, ccxt_error) if p]
        reason = "fetch_failed:" + "_".join(parts) if parts else "fetch_failed:no_data"
        return [], reason

    with _hist_lock:
        _history[symbol] = {"prices": prices, "fetched_at": time.time()}
    return prices, None


# ─── Indicator primitives ──────────────────────────────────────────────
def _trend(prices: List[float]) -> Tuple[str, float]:
    """Returns (label, slope_pct_per_day).

    Slope via simple linear regression on the last 14 closes.
    """
    sample = prices[-14:]
    n = len(sample)
    if n < 6:
        return "range", 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(sample) / n
    num = sum((xs[i] - mean_x) * (sample[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n)) or 1e-9
    slope = num / den                   # USD per day
    slope_pct = (slope / mean_y) * 100  # % per day vs mean
    if slope_pct > TREND_FLAT_BAND_PCT:
        return "up", slope_pct
    if slope_pct < -TREND_FLAT_BAND_PCT:
        return "down", slope_pct
    return "range", slope_pct


def _momentum(prices: List[float]) -> str:
    """Compare last-7 mean vs prior-7 mean."""
    if len(prices) < 14:
        return "flat"
    last7 = prices[-7:]
    prior7 = prices[-14:-7]
    mean_last = sum(last7) / 7
    mean_prior = sum(prior7) / 7
    delta_pct = ((mean_last - mean_prior) / mean_prior) * 100 if mean_prior else 0.0
    if delta_pct > 1.0:
        return "accelerating"
    if delta_pct < -1.0:
        return "decelerating"
    return "flat"


def _rsi(prices: List[float], period: int = 14) -> Tuple[str, float]:
    """Wilder-style RSI.  Returns (label, rsi_value)."""
    if len(prices) < period + 1:
        return "neutral", 50.0
    gains, losses = [], []
    for i in range(1, period + 1):
        chg = prices[-i] - prices[-i - 1]
        if chg > 0:
            gains.append(chg)
        else:
            losses.append(-chg)
    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0
    if avg_loss == 0:
        rsi = 100.0 if avg_gain > 0 else 50.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    if rsi >= 70:
        return "overbought", rsi
    if rsi <= 30:
        return "oversold", rsi
    return "neutral", rsi


def _volatility(prices: List[float]) -> str:
    """Compare 14d vol vs 30d vol."""
    if len(prices) < 30:
        return "normal"
    def _stdev_returns(seq: List[float]) -> float:
        rets = [(seq[i] / seq[i - 1] - 1.0) for i in range(1, len(seq))]
        return statistics.pstdev(rets) if rets else 0.0
    short = _stdev_returns(prices[-14:])
    long = _stdev_returns(prices[-30:])
    if long == 0:
        return "normal"
    ratio = short / long
    if ratio > 1.3:
        return "expanded"
    if ratio < 0.7:
        return "compressed"
    return "normal"


def _support_resistance(prices: List[float]) -> Tuple[Optional[float], Optional[float]]:
    if len(prices) < 7:
        return None, None
    window = prices[-30:] if len(prices) >= 30 else prices
    return float(min(window)), float(max(window))


# ─── Composite analysis ────────────────────────────────────────────────
def _compose_state_and_direction(
    trend: str, momentum: str, rsi_label: str
) -> Tuple[str, str, List[str], int]:
    """Aggregate indicators into a state + direction + reasons + aligned count.

    Suppression-friendly: defaults to neutral/WAIT, only leaves WAIT when at
    least SIGNALS_REQUIRED_FOR_BIAS indicators agree on direction.
    """
    bull_count = 0
    bear_count = 0
    reasons: List[str] = []

    if trend == "up":
        bull_count += 1
        reasons.append("price structure trending up over 14 days")
    elif trend == "down":
        bear_count += 1
        reasons.append("price structure trending down over 14 days")
    else:
        reasons.append("price inside a broad range, no directional trend")

    if momentum == "accelerating":
        if trend == "up":
            bull_count += 1
            reasons.append("momentum is accelerating in the trend direction")
        elif trend == "down":
            # acceleration *against* a down trend — confusing, don't count
            reasons.append("momentum is shifting but not confirmed")
        else:
            reasons.append("momentum is building but trend not yet defined")
    elif momentum == "decelerating":
        if trend == "down":
            bear_count += 1
            reasons.append("momentum is decelerating in the trend direction")
        else:
            reasons.append("momentum is decelerating, no clear signal")
    else:
        reasons.append("momentum is flat")

    if rsi_label == "overbought":
        bear_count += 1
        reasons.append("RSI is overbought — buying exhaustion risk")
    elif rsi_label == "oversold":
        bull_count += 1
        reasons.append("RSI is oversold — selling exhaustion possible")
    else:
        reasons.append("RSI is in neutral territory")

    aligned = max(bull_count, bear_count)

    if bull_count >= SIGNALS_REQUIRED_FOR_BIAS and bull_count > bear_count:
        return "bullish", "LONG_BIAS", reasons, aligned
    if bear_count >= SIGNALS_REQUIRED_FOR_BIAS and bear_count > bull_count:
        return "bearish", "SHORT_BIAS", reasons, aligned
    return "neutral", "WAIT", reasons, aligned


def _confidence(aligned: int, total_signals: int = 3) -> float:
    """Confidence rises with alignment but is softly capped to keep the
    system suppression-biased.  Caller decides what to do with it."""
    raw = min(1.0, aligned * CONF_PER_INDICATOR + 0.18)  # baseline 18% + alignment
    if aligned < total_signals + 1:                     # i.e. not 4-of-3 (impossible) — keep capped
        raw = min(raw, CONF_SOFT_CAP_BELOW_ALIGN)
    return round(raw, 4)


# ─── Public API ────────────────────────────────────────────────────────
def _degraded(symbol: str, reason: str) -> dict:
    return {
        "symbol": symbol.upper(),
        "ok": False,
        "state": "unavailable",
        "direction": "WAIT",
        "confidence": 0.0,
        "degraded": True,
        "reason": reason,
        "source": "native_ta_v1",
        "asOf": _now_iso(),
    }


def analyze(symbol: str) -> dict:
    sym = (symbol or "").upper().strip()
    if not sym:
        return _degraded("", "unsupported_symbol")
    if sym not in SYMBOL_TO_CG_ID:
        return _degraded(sym, "unsupported_symbol")

    prices, err = _fetch_history(sym)
    if err and err.startswith("fetch_failed"):
        return _degraded(sym, err)
    if len(prices) < MIN_CANDLES:
        return _degraded(sym, "insufficient_price_history")

    trend, slope_pct = _trend(prices)
    momentum = _momentum(prices)
    rsi_label, rsi_val = _rsi(prices)
    vol = _volatility(prices)
    support, resistance = _support_resistance(prices)

    state, direction, reasons, aligned = _compose_state_and_direction(
        trend, momentum, rsi_label
    )
    confidence = _confidence(aligned)

    # Live spot price (truthful — comes from market_prices)
    spot = _get_spot(sym)
    current_price = spot.get("price") if spot.get("ok") else (prices[-1] if prices else None)

    return {
        "symbol": sym,
        "ok": True,
        "state": state,
        "direction": direction,
        "confidence": confidence,
        "trend": trend,
        "trendSlopePct": round(slope_pct, 3),
        "momentum": momentum,
        "rsi": rsi_label,
        "rsiValue": round(rsi_val, 1),
        "volatility": vol,
        "support": round(support, 2) if support is not None else None,
        "resistance": round(resistance, 2) if resistance is not None else None,
        "currentPrice": round(float(current_price), 2) if current_price else None,
        "reasons": reasons,
        "alignedIndicators": aligned,
        "source": "native_ta_v1",
        "asOf": _now_iso(),
        "degraded": False,
    }


def analyze_many(symbols: Optional[List[str]] = None) -> Dict[str, dict]:
    syms = symbols or SYMBOLS
    return {s.upper(): analyze(s) for s in syms}


def service_health() -> dict:
    """Quick diagnostic for /api/ta/health."""
    with _hist_lock:
        tracked = len(SYMBOL_TO_CG_ID)
        with_history = sum(1 for s in SYMBOL_TO_CG_ID if len(_history.get(s, {}).get("prices", [])) >= MIN_CANDLES)
        return {
            "ok": with_history > 0,
            "symbolsTracked": tracked,
            "symbolsWithHistory": with_history,
            "historyDays": HISTORY_DAYS,
            "minCandles": MIN_CANDLES,
            "historyTtlSec": HISTORY_TTL_SEC,
            "source": "native_ta_v1",
            "asOf": _now_iso(),
        }


def as_miniapp_module(ta: dict) -> dict:
    """Adapt a TA record to the shape that /api/miniapp/home's modules array
    consumes (`{module, direction, confidence, insight}`).  Honest — if TA is
    degraded, status='WAIT', confidence=0, insight explains why."""
    if not ta.get("ok"):
        return {
            "module": "Technical Analysis",
            "direction": "neutral",
            "confidence": 0.0,
            "insight": "Technical analysis unavailable — {}".format(
                ta.get("reason") or "no price history yet"
            ),
        }
    # Map TA direction to module direction enum used by the SPA.
    dir_map = {
        "LONG_BIAS": "bullish",
        "SHORT_BIAS": "bearish",
        "WAIT": "neutral",
    }
    insight_parts = []
    insight_parts.append(f"Trend: {ta['trend']}.")
    insight_parts.append(f"Momentum: {ta['momentum']}.")
    insight_parts.append(f"RSI: {ta['rsi']}.")
    insight = " ".join(insight_parts)
    return {
        "module": "Technical Analysis",
        "direction": dir_map.get(ta["direction"], "neutral"),
        "confidence": float(ta["confidence"]),
        "insight": insight,
    }



# ═══════════════════════════════════════════════════════════════════════
# Phase D Pass 2A — Canonical adapter (Unified Runtime Contract)
# ═══════════════════════════════════════════════════════════════════════
# Strictly PURE: this function NEVER calls analyze(), NEVER touches the
# network, NEVER reads the DB. It only normalizes a pre-computed TA record
# into a CognitionSnapshot. Callers (e.g. observatory, home composer) are
# expected to obtain the raw payload by their own established route and
# then pass it here for normalization.

# Free-text TA reason → snake_case token. Anything not on this map is
# discarded (with a sentinel 'unmapped_ta_reason' if reasons becomes empty).
_TA_REASON_TOKEN_MAP = {
    "price structure trending up over 14 days": "trend_up_14d",
    "price structure trending down over 14 days": "trend_down_14d",
    "price inside a broad range, no directional trend": "trend_neutral",
    "momentum is accelerating in the trend direction": "momentum_accelerating_aligned",
    "momentum is shifting but not confirmed": "momentum_shifting",
    "momentum is building but trend not yet defined": "momentum_building",
    "momentum is decelerating in the trend direction": "momentum_decelerating_aligned",
    "momentum is decelerating, no clear signal": "momentum_decelerating",
    "momentum is flat": "momentum_flat",
    "rsi is overbought — buying exhaustion risk": "rsi_overbought",
    "rsi is oversold — selling exhaustion possible": "rsi_oversold",
    "rsi is in neutral territory": "rsi_neutral",
}


def _ta_reasons_to_tokens(reasons):
    if not reasons:
        return []
    out = []
    for r in reasons:
        if not r:
            continue
        key = str(r).strip().lower()
        tok = _TA_REASON_TOKEN_MAP.get(key)
        if tok and tok not in out:
            out.append(tok)
    return out


def _ta_canonical_direction(direction_raw):
    """Map TA's internal direction enum to canonical direction."""
    m = {
        "LONG_BIAS": "long",
        "SHORT_BIAS": "short",
        "WAIT": "neutral",
    }
    return m.get(str(direction_raw or "").upper(), "neutral")


def _ta_canonical_state(payload):
    """
    Map TA's (ok, state, direction) to a canonical state.

      ok=False                                        → 'degraded' (if known
                                                        provider failure)
                                                        or 'insufficient' (if
                                                        substrate missing)
      ok=True, direction='WAIT'                       → 'wait'
      ok=True, direction in (LONG_BIAS, SHORT_BIAS)   → 'active'
    """
    if not payload.get("ok"):
        reason = str(payload.get("reason") or "").lower()
        if reason in (
            "insufficient_price_history",
            "unsupported_symbol",
        ):
            return "insufficient"
        return "degraded"
    direction = str(payload.get("direction") or "").upper()
    if direction == "WAIT":
        return "wait"
    if direction in ("LONG_BIAS", "SHORT_BIAS"):
        return "active"
    return "wait"


def canonical(payload):
    """
    Adapt a raw TA `analyze(symbol)` result to a CognitionSnapshot.

    Pure: no DB, no network, no recomputation. The caller is responsible
    for obtaining `payload` via the established read path.

    Args:
        payload: dict — return value of `analyze(symbol)`. If None or empty,
                 yields an 'insufficient' snapshot (no exception).

    Returns:
        services.runtime_contract.CognitionSnapshot
    """
    # Local import keeps the contract module side-effect free even if a
    # caller imports technical_analysis early in startup.
    from services.runtime_contract import (
        CognitionSnapshot, make_insufficient,
    )

    if not isinstance(payload, dict) or not payload:
        return make_insufficient(
            module="ta",
            source="native_ta_v1",
            reasons=("missing_ta_payload",),
        )

    source = str(payload.get("source") or "native_ta_v1").strip().lower()
    updated_at = payload.get("asOf")

    state = _ta_canonical_state(payload)

    if state in ("insufficient", "degraded"):
        reason_token = str(payload.get("reason") or "ta_unavailable").lower()
        return CognitionSnapshot.build(
            module="ta",
            source=source,
            state=state,
            reasons=(reason_token,),
            degraded=bool(payload.get("degraded")) or state == "degraded",
            updatedAt=updated_at,
        )

    direction = _ta_canonical_direction(payload.get("direction"))
    confidence = payload.get("confidence")
    reasons = _ta_reasons_to_tokens(payload.get("reasons") or [])
    if not reasons:
        reasons = ["ta_reasons_unmapped"]

    return CognitionSnapshot.build(
        module="ta",
        source=source,
        state=state,
        direction=direction,
        confidence=confidence,
        reasons=reasons,
        degraded=bool(payload.get("degraded")),
        updatedAt=updated_at,
    )
