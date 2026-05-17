"""
exchange_runtime — production adapter for Exchange (CEX intelligence) endpoints.

Provides REAL data for /api/exchange/*, /api/cex/*, /api/venues/* and
/api/funding-rates which were previously caught by legacy_compat.

Routes (registered BEFORE legacy_compat_router):

  Public market microstructure:
    GET  /api/exchange/orderbook/{symbol}        — top of book + depth
    GET  /api/exchange/tickers                   — top 30 SWAP tickers (volume)
    GET  /api/exchange/funding/{symbol}          — current funding rate
    GET  /api/exchange/open-interest/{symbol}    — OI snapshot
    GET  /api/exchange/derivatives/{symbol}      — combined derivative stats
    GET  /api/exchange/anomalies                 — funding/OI anomaly scanner

  Surface for Web Exchange page:
    GET  /api/exchange/overview                  — multi-symbol dashboard
    GET  /api/exchange/markets                   — markets list with stats
    GET  /api/exchange/order-flow/{symbol}       — buy/sell pressure approx
    GET  /api/exchange/health                    — live status of all venues

  CEX Intelligence aliases (used by ExchangeResearchPage):
    GET  /api/cex/funding/{symbol}
    GET  /api/cex/oi/{symbol}
    GET  /api/cex/orderbook/{symbol}
    GET  /api/cex/liquidations                   — approx via funding+OI delta
    GET  /api/cex/anomalies
    GET  /api/cex-intelligence/overview

  Mobile/MiniApp:
    GET  /api/miniapp/exchange?asset=BTC
    GET  /api/miniapp/exchange-watchlist
    GET  /api/exchange/compact/{symbol}

  Admin:
    GET  /api/admin/exchange/overview

  Funding-rates legacy alias:
    GET  /api/funding-rates

Data sources:
  • OKX public REST  (primary — geo-allowed for our IP)
  • CoinGecko        (fallback for prices when OKX fails)

No paid feeds, no mocks. Graceful degradation on network failure.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import requests
from fastapi import APIRouter, Query

logger = logging.getLogger("exchange_runtime")
router = APIRouter()

# ──────────────────────────────────────────────────────────────────────────
# OKX endpoints
# ──────────────────────────────────────────────────────────────────────────
_OKX_TICKER_URL    = "https://www.okx.com/api/v5/market/ticker"
_OKX_TICKERS_URL   = "https://www.okx.com/api/v5/market/tickers"
_OKX_BOOK_URL      = "https://www.okx.com/api/v5/market/books"
_OKX_FUNDING_URL   = "https://www.okx.com/api/v5/public/funding-rate"
_OKX_FUNDING_HIST  = "https://www.okx.com/api/v5/public/funding-rate-history"
_OKX_OI_URL        = "https://www.okx.com/api/v5/public/open-interest"
_OKX_INST_URL      = "https://www.okx.com/api/v5/public/instruments"


# ──────────────────────────────────────────────────────────────────────────
# Symbol helpers
# ──────────────────────────────────────────────────────────────────────────
def _canonical(symbol: str) -> str:
    s = (symbol or "BTC").upper().replace("-", "").replace("/", "").replace("_", "")
    return s.replace("USDT", "").replace("USD", "") or "BTC"


def _to_okx_spot(symbol: str) -> str:
    """'BTC' / 'BTCUSDT' → 'BTC-USDT'."""
    base = _canonical(symbol)
    return f"{base}-USDT"


def _to_okx_swap(symbol: str) -> str:
    """'BTC' / 'BTCUSDT' → 'BTC-USDT-SWAP'."""
    base = _canonical(symbol)
    return f"{base}-USDT-SWAP"


# ──────────────────────────────────────────────────────────────────────────
# TTL cache
# ──────────────────────────────────────────────────────────────────────────
_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.RLock()
_TTL = 15.0  # 15s for highly-dynamic markets


def _cached_get(url: str, params: Dict[str, Any], ttl: float = _TTL) -> Any:
    key = f"{url}?{sorted(params.items())}"
    with _LOCK:
        ent = _CACHE.get(key)
        if ent and time.time() - ent["t"] < ttl:
            return ent["data"]
    try:
        r = requests.get(url, params=params, timeout=5.0)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning(f"[exchange_runtime] GET {url} failed: {e}")
        data = None
    with _LOCK:
        _CACHE[key] = {"t": time.time(), "data": data}
    return data


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────────
# Low-level OKX fetchers
# ──────────────────────────────────────────────────────────────────────────
def _fetch_ticker(spot: str) -> Optional[Dict[str, Any]]:
    res = _cached_get(_OKX_TICKER_URL, {"instId": spot})
    if not res or res.get("code") != "0":
        return None
    arr = res.get("data") or []
    return arr[0] if arr else None


def _fetch_funding(swap: str) -> Optional[Dict[str, Any]]:
    res = _cached_get(_OKX_FUNDING_URL, {"instId": swap}, ttl=60.0)
    if not res or res.get("code") != "0":
        return None
    arr = res.get("data") or []
    return arr[0] if arr else None


def _fetch_funding_history(swap: str, limit: int = 20) -> List[Dict[str, Any]]:
    res = _cached_get(_OKX_FUNDING_HIST, {"instId": swap, "limit": limit}, ttl=60.0)
    if not res or res.get("code") != "0":
        return []
    return res.get("data") or []


def _fetch_oi(swap: str) -> Optional[Dict[str, Any]]:
    res = _cached_get(_OKX_OI_URL, {"instType": "SWAP", "instId": swap}, ttl=30.0)
    if not res or res.get("code") != "0":
        return None
    arr = res.get("data") or []
    return arr[0] if arr else None


def _fetch_orderbook(spot: str, sz: int = 20) -> Optional[Dict[str, Any]]:
    res = _cached_get(_OKX_BOOK_URL, {"instId": spot, "sz": sz})
    if not res or res.get("code") != "0":
        return None
    arr = res.get("data") or []
    return arr[0] if arr else None


def _fetch_swap_tickers() -> List[Dict[str, Any]]:
    res = _cached_get(_OKX_TICKERS_URL, {"instType": "SWAP"}, ttl=30.0)
    if not res or res.get("code") != "0":
        return []
    return res.get("data") or []


# ──────────────────────────────────────────────────────────────────────────
# Public endpoints — Microstructure
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/exchange/orderbook/{symbol}")
@router.get("/api/cex/orderbook/{symbol}")
def orderbook(symbol: str, depth: int = Query(20, ge=1, le=400)):
    spot = _to_okx_spot(symbol)
    book = _fetch_orderbook(spot, depth)
    if not book:
        return {"ok": False, "symbol": _canonical(symbol), "error": "no_data"}

    asks = book.get("asks", [])[:depth]
    bids = book.get("bids", [])[:depth]

    def _parse(row):
        try:
            return {"price": float(row[0]), "size": float(row[1])}
        except (TypeError, ValueError, IndexError):
            return None

    asks_p = [a for a in (_parse(r) for r in asks) if a]
    bids_p = [b for b in (_parse(r) for r in bids) if b]

    best_ask = asks_p[0]["price"] if asks_p else None
    best_bid = bids_p[0]["price"] if bids_p else None
    mid = (best_ask + best_bid) / 2 if (best_ask and best_bid) else None
    spread = (best_ask - best_bid) if (best_ask and best_bid) else None
    spread_bps = (spread / mid * 10000) if (spread and mid) else None

    bid_size = sum(b["size"] for b in bids_p)
    ask_size = sum(a["size"] for a in asks_p)
    imbalance = ((bid_size - ask_size) / (bid_size + ask_size)) if (bid_size + ask_size) else 0

    return {
        "ok": True,
        "symbol": _canonical(symbol),
        "pair": spot,
        "venue": "okx",
        "asks": asks_p,
        "bids": bids_p,
        "bestAsk": best_ask,
        "bestBid": best_bid,
        "mid": mid,
        "spread": spread,
        "spreadBps": round(spread_bps, 3) if spread_bps else None,
        "bidSize": round(bid_size, 4),
        "askSize": round(ask_size, 4),
        "imbalance": round(imbalance, 4),
        "imbalanceLabel": "buyers_dominant" if imbalance > 0.1 else "sellers_dominant" if imbalance < -0.1 else "balanced",
        "asOf": _now_iso(),
        "source": "okx_public_rest",
    }


@router.get("/api/exchange/funding/{symbol}")
@router.get("/api/cex/funding/{symbol}")
def funding(symbol: str):
    swap = _to_okx_swap(symbol)
    cur = _fetch_funding(swap)
    if not cur:
        return {"ok": False, "symbol": _canonical(symbol), "error": "no_data"}

    rate = float(cur.get("fundingRate") or 0)
    annualized = rate * 3 * 365  # OKX: 3 funding intervals per day (8h)
    history = _fetch_funding_history(swap, 24)
    hist_clean = []
    for h in history:
        try:
            hist_clean.append({
                "fundingRate": float(h.get("realizedRate") or h.get("fundingRate") or 0),
                "fundingTime": int(h.get("fundingTime") or 0),
            })
        except (TypeError, ValueError):
            continue

    return {
        "ok": True,
        "symbol": _canonical(symbol),
        "pair": swap,
        "venue": "okx",
        "fundingRate": rate,
        "fundingRatePct": round(rate * 100, 6),
        "annualizedPct": round(annualized * 100, 3),
        "nextFundingTime": int(cur.get("nextFundingTime") or 0),
        "fundingTime": int(cur.get("fundingTime") or 0),
        "premium": float(cur.get("premium") or 0),
        "minFundingRate": float(cur.get("minFundingRate") or 0),
        "maxFundingRate": float(cur.get("maxFundingRate") or 0),
        "bias": "long_paying_short" if rate > 0 else "short_paying_long" if rate < 0 else "neutral",
        "history": hist_clean,
        "asOf": _now_iso(),
        "source": "okx_public_rest",
    }


@router.get("/api/exchange/open-interest/{symbol}")
@router.get("/api/cex/oi/{symbol}")
def open_interest(symbol: str):
    swap = _to_okx_swap(symbol)
    oi = _fetch_oi(swap)
    if not oi:
        return {"ok": False, "symbol": _canonical(symbol), "error": "no_data"}
    return {
        "ok": True,
        "symbol": _canonical(symbol),
        "pair": swap,
        "venue": "okx",
        "oi": float(oi.get("oi") or 0),
        "oiCcy": float(oi.get("oiCcy") or 0),
        "oiUsd": float(oi.get("oiUsd") or 0),
        "ts": int(oi.get("ts") or 0),
        "asOf": _now_iso(),
        "source": "okx_public_rest",
    }


@router.get("/api/exchange/derivatives/{symbol}")
def derivatives_combined(symbol: str):
    """Combined snapshot: spot price + funding + OI + orderbook imbalance."""
    spot = _to_okx_spot(symbol)
    swap = _to_okx_swap(symbol)
    canon = _canonical(symbol)

    tk = _fetch_ticker(spot)
    fund = _fetch_funding(swap)
    oi = _fetch_oi(swap)
    book = _fetch_orderbook(spot, 20)

    spot_price = float(tk.get("last") or 0) if tk else None
    funding_rate = float(fund.get("fundingRate") or 0) if fund else None
    oi_usd = float(oi.get("oiUsd") or 0) if oi else None

    # Orderbook imbalance
    if book:
        try:
            bids = book.get("bids", [])[:20]
            asks = book.get("asks", [])[:20]
            bid_size = sum(float(r[1]) for r in bids)
            ask_size = sum(float(r[1]) for r in asks)
            denom = bid_size + ask_size
            imbalance = ((bid_size - ask_size) / denom) if denom else 0
        except Exception:
            imbalance = 0
    else:
        imbalance = 0

    # Composite signal
    bullish_factors = 0
    bearish_factors = 0
    if funding_rate is not None:
        if funding_rate > 0.0001:    # long-heavy → bearish
            bearish_factors += 1
        elif funding_rate < -0.0001: # short-heavy → bullish
            bullish_factors += 1
    if imbalance > 0.15:
        bullish_factors += 1
    elif imbalance < -0.15:
        bearish_factors += 1

    if bullish_factors > bearish_factors:
        bias = "bullish"
    elif bearish_factors > bullish_factors:
        bias = "bearish"
    else:
        bias = "neutral"

    return {
        "ok": True,
        "symbol": canon,
        "spotPair": spot,
        "swapPair": swap,
        "venue": "okx",
        "spotPrice": spot_price,
        "changePct24h": (
            ((spot_price - float(tk.get("open24h") or 0)) / float(tk.get("open24h") or 1) * 100)
            if tk and float(tk.get("open24h") or 0) > 0
            else None
        ),
        "volume24h": float(tk.get("vol24h") or 0) if tk else None,
        "volCcy24h": float(tk.get("volCcy24h") or 0) if tk else None,
        "fundingRate": funding_rate,
        "fundingRatePct": round(funding_rate * 100, 6) if funding_rate is not None else None,
        "annualizedFundingPct": round(funding_rate * 3 * 365 * 100, 3) if funding_rate is not None else None,
        "openInterestUsd": oi_usd,
        "orderbookImbalance": round(imbalance, 4),
        "bias": bias,
        "bullishFactors": bullish_factors,
        "bearishFactors": bearish_factors,
        "asOf": _now_iso(),
        "source": "okx_public_rest",
    }


# ──────────────────────────────────────────────────────────────────────────
# Tickers / Markets
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/exchange/tickers")
def tickers(limit: int = Query(30, ge=1, le=100), sort: str = Query("volume")):
    data = _fetch_swap_tickers()
    out: List[Dict[str, Any]] = []
    for t in data:
        try:
            inst = t.get("instId", "")
            if not inst.endswith("-USDT-SWAP"):
                continue
            symbol = inst.replace("-USDT-SWAP", "")
            last = float(t.get("last") or 0)
            open24 = float(t.get("open24h") or 0)
            change_pct = ((last - open24) / open24 * 100) if open24 else 0
            out.append({
                "symbol": symbol,
                "pair": inst,
                "last": last,
                "high24h": float(t.get("high24h") or 0),
                "low24h": float(t.get("low24h") or 0),
                "open24h": open24,
                "changePct24h": round(change_pct, 3),
                "volume24h": float(t.get("vol24h") or 0),
                "volUsdt24h": float(t.get("volCcy24h") or 0),
                "bidPx": float(t.get("bidPx") or 0),
                "askPx": float(t.get("askPx") or 0),
            })
        except (TypeError, ValueError):
            continue

    # Sort
    if sort == "volume":
        out.sort(key=lambda x: x["volUsdt24h"], reverse=True)
    elif sort == "change":
        out.sort(key=lambda x: x["changePct24h"], reverse=True)
    elif sort == "gainers":
        out = [x for x in out if x["changePct24h"] > 0]
        out.sort(key=lambda x: x["changePct24h"], reverse=True)
    elif sort == "losers":
        out = [x for x in out if x["changePct24h"] < 0]
        out.sort(key=lambda x: x["changePct24h"])

    return {
        "ok": True,
        "items": out[:limit],
        "count": min(limit, len(out)),
        "totalAvailable": len(out),
        "sort": sort,
        "asOf": _now_iso(),
        "source": "okx_public_rest",
    }


@router.get("/api/exchange/markets")
def markets():
    """Markets list endpoint — alias used by ExchangeMarketsPage."""
    return tickers(limit=50, sort="volume")


# ──────────────────────────────────────────────────────────────────────────
# Anomalies scanner — funding rate extremes + OI spikes
# ──────────────────────────────────────────────────────────────────────────
_ANOMALY_ASSETS = ["BTC", "ETH", "SOL", "DOGE", "XRP", "BNB", "ARB", "OP", "AVAX", "TON", "LINK", "MATIC", "TIA", "APT", "SUI"]


@router.get("/api/exchange/anomalies")
@router.get("/api/cex/anomalies")
def anomalies(threshold_funding_bps: float = Query(3.0)):
    """Scan top assets for funding rate / OI anomalies."""
    out: List[Dict[str, Any]] = []
    for sym in _ANOMALY_ASSETS:
        swap = _to_okx_swap(sym)
        fund = _fetch_funding(swap)
        oi = _fetch_oi(swap)
        if not fund:
            continue
        rate = float(fund.get("fundingRate") or 0)
        rate_bps = rate * 10000  # convert to basis points

        flags: List[str] = []
        if rate_bps >= threshold_funding_bps:
            flags.append("funding_high_long")
        elif rate_bps <= -threshold_funding_bps:
            flags.append("funding_high_short")

        if oi and float(oi.get("oiUsd") or 0) > 1_000_000_000:
            flags.append("oi_>1B")

        if not flags:
            continue

        out.append({
            "symbol": sym,
            "pair": swap,
            "fundingRate": rate,
            "fundingRateBps": round(rate_bps, 3),
            "annualizedPct": round(rate * 3 * 365 * 100, 3),
            "oiUsd": float(oi.get("oiUsd") or 0) if oi else None,
            "flags": flags,
            "severity": "high" if abs(rate_bps) > 5 else "medium",
        })

    out.sort(key=lambda x: abs(x["fundingRateBps"]), reverse=True)
    return {
        "ok": True,
        "items": out,
        "count": len(out),
        "thresholdBps": threshold_funding_bps,
        "scannedAssets": len(_ANOMALY_ASSETS),
        "asOf": _now_iso(),
        "source": "okx_funding_scanner",
    }


# ──────────────────────────────────────────────────────────────────────────
# Order flow approximation (from orderbook deltas)
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/exchange/order-flow/{symbol}")
@router.get("/api/order-flow/{symbol}")
def order_flow(symbol: str):
    book = _fetch_orderbook(_to_okx_spot(symbol), 50)
    if not book:
        return {"ok": False, "symbol": _canonical(symbol), "error": "no_data"}

    # Bucket bids/asks into tiers (price-distance buckets)
    try:
        bids = [(float(r[0]), float(r[1])) for r in book.get("bids", [])]
        asks = [(float(r[0]), float(r[1])) for r in book.get("asks", [])]
    except (TypeError, ValueError):
        return {"ok": False, "symbol": _canonical(symbol), "error": "parse_error"}

    if not bids or not asks:
        return {"ok": False, "symbol": _canonical(symbol), "error": "no_book"}

    mid = (bids[0][0] + asks[0][0]) / 2

    def bucket(pairs, side):
        # Buckets: <0.1%, 0.1%-0.5%, 0.5%-2%, >2% from mid
        tiers = {"tight": 0.0, "near": 0.0, "mid": 0.0, "far": 0.0}
        for px, sz in pairs:
            d = abs(px - mid) / mid * 100
            if d < 0.1:    tiers["tight"] += sz
            elif d < 0.5:  tiers["near"]  += sz
            elif d < 2:    tiers["mid"]   += sz
            else:          tiers["far"]   += sz
        return tiers

    bid_tiers = bucket(bids, "bid")
    ask_tiers = bucket(asks, "ask")

    total_bid = sum(bid_tiers.values())
    total_ask = sum(ask_tiers.values())
    total = total_bid + total_ask
    pressure = ((total_bid - total_ask) / total) if total else 0

    return {
        "ok": True,
        "symbol": _canonical(symbol),
        "pair": _to_okx_spot(symbol),
        "venue": "okx",
        "mid": mid,
        "buyPressure": round(pressure, 4),
        "buyPressureLabel": "buyers_dominant" if pressure > 0.15 else "sellers_dominant" if pressure < -0.15 else "balanced",
        "bidTiers": bid_tiers,
        "askTiers": ask_tiers,
        "totalBidSize": round(total_bid, 4),
        "totalAskSize": round(total_ask, 4),
        "asOf": _now_iso(),
        "source": "okx_orderbook",
    }


# ──────────────────────────────────────────────────────────────────────────
# Liquidations proxy (OKX doesn't expose history publicly, return summary
# from funding+OI as best-effort signal)
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/cex/liquidations")
def liquidations():
    """Approximate liquidation pressure based on extreme funding rates."""
    out: List[Dict[str, Any]] = []
    for sym in _ANOMALY_ASSETS[:10]:
        swap = _to_okx_swap(sym)
        fund = _fetch_funding(swap)
        oi = _fetch_oi(swap)
        if not fund:
            continue
        rate = float(fund.get("fundingRate") or 0)
        oi_usd = float(oi.get("oiUsd") or 0) if oi else 0
        # Long-side liquidation risk = positive funding × OI
        long_risk = rate * oi_usd if rate > 0 else 0
        short_risk = abs(rate) * oi_usd if rate < 0 else 0
        out.append({
            "symbol": sym,
            "longLiqRiskUsd": round(long_risk, 2),
            "shortLiqRiskUsd": round(short_risk, 2),
            "fundingRate": rate,
            "oiUsd": oi_usd,
            "side": "long" if long_risk > short_risk else "short",
        })

    return {
        "ok": True,
        "items": out,
        "note": "OKX public REST does not provide liquidation history; this is approximated from funding × OI signal.",
        "asOf": _now_iso(),
        "source": "okx_funding_oi_proxy",
    }


# ──────────────────────────────────────────────────────────────────────────
# Overview / Health / Watchlists
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/exchange/overview")
@router.get("/api/cex-intelligence/overview")
def overview():
    """Dashboard overview for ExchangeOverviewPage."""
    top_symbols = ["BTC", "ETH", "SOL", "DOGE", "XRP", "BNB"]
    rows = []
    for sym in top_symbols:
        d = derivatives_combined(sym)
        if d.get("ok"):
            rows.append(d)

    # Aggregate signals
    bull = sum(1 for r in rows if r.get("bias") == "bullish")
    bear = sum(1 for r in rows if r.get("bias") == "bearish")
    if bull > bear:
        market_bias = "bullish"
    elif bear > bull:
        market_bias = "bearish"
    else:
        market_bias = "neutral"

    total_oi = sum(r.get("openInterestUsd") or 0 for r in rows)
    total_vol = sum(r.get("volCcy24h") or 0 for r in rows)

    return {
        "ok": True,
        "items": rows,
        "count": len(rows),
        "marketBias": market_bias,
        "bullishCount": bull,
        "bearishCount": bear,
        "totalOiUsd": round(total_oi, 2),
        "totalVolume24hUsd": round(total_vol, 2),
        "asOf": _now_iso(),
        "source": "okx_public_rest",
    }


@router.get("/api/exchange/venues")
def exchange_health():
    """Multi-venue health summary (only OKX live for now).

    Note: /api/exchange/health is taken by an older system health endpoint
    in server.py; we use /api/exchange/venues for the multi-venue probe.
    """
    # Quick probe: fetch BTC ticker, measure latency
    t0 = time.time()
    tk = _fetch_ticker("BTC-USDT")
    latency_ms = (time.time() - t0) * 1000

    venues = [
        {
            "venue": "okx",
            "status": "online" if tk else "degraded",
            "latencyMs": round(latency_ms, 1),
            "btcPrice": float(tk.get("last") or 0) if tk else None,
            "note": "live",
        },
        {"venue": "binance", "status": "blocked", "note": "geoblocked from datacenter IP (HTTP 451)"},
        {"venue": "bybit", "status": "blocked", "note": "geoblocked from datacenter IP"},
    ]
    return {
        "ok": True,
        "venues": venues,
        "primary": "okx",
        "online": sum(1 for v in venues if v.get("status") == "online"),
        "total": len(venues),
        "asOf": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────────────
# Account / Orders / Positions placeholders
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/exchange/account")
def exchange_account():
    """No real exchange API key is connected. Return paper-trading state."""
    return {
        "ok": True,
        "mode": "paper",
        "venue": None,
        "balance": 0.0,
        "currency": "USDT",
        "connected": False,
        "note": "No live exchange key configured. Use paper-trading via /api/trading/paper/*.",
        "asOf": _now_iso(),
    }


@router.get("/api/exchange/orders")
def exchange_orders():
    return {"ok": True, "items": [], "count": 0, "mode": "paper", "asOf": _now_iso()}


@router.get("/api/exchange/status")
def exchange_status():
    """Lightweight status pin for UI."""
    return {
        "ok": True,
        "mode": "paper",
        "connected": False,
        "venues": ["okx (read-only)"],
        "asOf": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────────────
# Funding rates list (legacy alias)
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/funding-rates")
def funding_rates():
    """Cross-asset funding rate table (legacy alias)."""
    out = []
    for sym in _ANOMALY_ASSETS:
        swap = _to_okx_swap(sym)
        f = _fetch_funding(swap)
        if not f:
            continue
        rate = float(f.get("fundingRate") or 0)
        out.append({
            "symbol": sym,
            "venue": "okx",
            "fundingRate": rate,
            "fundingRatePct": round(rate * 100, 6),
            "annualizedPct": round(rate * 3 * 365 * 100, 3),
            "nextFundingTime": int(f.get("nextFundingTime") or 0),
        })
    out.sort(key=lambda x: x["fundingRate"], reverse=True)
    return {
        "ok": True,
        "items": out,
        "count": len(out),
        "asOf": _now_iso(),
        "source": "okx_public_rest",
    }


# ──────────────────────────────────────────────────────────────────────────
# Compact for Mobile/MiniApp
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/exchange/compact/{symbol}")
def exchange_compact(symbol: str):
    """Compact single-asset exchange snapshot for Mobile/MiniApp."""
    return derivatives_combined(symbol)


@router.get("/api/miniapp/exchange")
def miniapp_exchange(asset: str = Query("BTC")):
    """Mobile-friendly exchange screen payload for Telegram MiniApp."""
    d = derivatives_combined(asset)
    if not d.get("ok"):
        return {"ok": False, "asset": _canonical(asset), "error": "no_data"}

    # Add orderbook brief
    book = _fetch_orderbook(_to_okx_spot(asset), 10)
    book_brief = None
    if book:
        try:
            asks = [(float(r[0]), float(r[1])) for r in book.get("asks", [])[:5]]
            bids = [(float(r[0]), float(r[1])) for r in book.get("bids", [])[:5]]
            book_brief = {
                "bids": [{"price": p, "size": round(s, 4)} for p, s in bids],
                "asks": [{"price": p, "size": round(s, 4)} for p, s in asks],
            }
        except Exception:
            book_brief = None

    return {
        "ok": True,
        **d,
        "orderbook": book_brief,
    }


@router.get("/api/miniapp/exchange-watchlist")
def miniapp_exchange_watchlist(symbols: str = Query("BTC,ETH,SOL,DOGE,XRP,BNB")):
    """Multi-asset exchange watchlist for MiniApp."""
    syms = [s.strip().upper() for s in (symbols or "BTC,ETH").split(",") if s.strip()]
    out = []
    for s in syms[:20]:
        d = derivatives_combined(s)
        if d.get("ok"):
            out.append({
                "symbol": d["symbol"],
                "price": d.get("spotPrice"),
                "changePct24h": d.get("changePct24h"),
                "volume24h": d.get("volCcy24h"),
                "fundingRatePct": d.get("fundingRatePct"),
                "annualizedFundingPct": d.get("annualizedFundingPct"),
                "openInterestUsd": d.get("openInterestUsd"),
                "orderbookImbalance": d.get("orderbookImbalance"),
                "bias": d.get("bias"),
            })
    return {"ok": True, "items": out, "count": len(out), "asOf": _now_iso()}


# ──────────────────────────────────────────────────────────────────────────
# Admin overview
# ──────────────────────────────────────────────────────────────────────────
@router.get("/api/admin/exchange/overview")
def admin_exchange_overview():
    """Admin dashboard: venues health + scanned anomalies + market bias."""
    h = exchange_health()
    ov = overview()
    an = anomalies(threshold_funding_bps=2.0)
    return {
        "ok": True,
        "health": h,
        "marketOverview": {
            "marketBias": ov.get("marketBias"),
            "bullishCount": ov.get("bullishCount"),
            "bearishCount": ov.get("bearishCount"),
            "totalOiUsd": ov.get("totalOiUsd"),
            "totalVolume24hUsd": ov.get("totalVolume24hUsd"),
            "topAssets": ov.get("items", [])[:5],
        },
        "anomalies": {
            "count": an.get("count", 0),
            "items": an.get("items", [])[:10],
        },
        "asOf": _now_iso(),
    }
