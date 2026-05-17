"""
CLOB Service — Polymarket Orderbook Integration.

Two data sources:
1. Gamma API bestBid/bestAsk — real-time CLOB spread (already in market data)
2. CLOB REST API /book — full orderbook depth for detailed analysis

For binary markets, the full orderbook spans 0.01-0.99.
We compute depth metrics around the current midpoint price.
"""
import logging
import time
import httpx

logger = logging.getLogger("prediction.feed.clob")

CLOB_API = "https://clob.polymarket.com"

_clob_cache = {}
CACHE_TTL = 90


def _parse_book(book: dict, midpoint: float = 0.5) -> dict:
    """Parse orderbook with depth metrics around the midpoint."""
    bids = book.get("bids", [])
    asks = book.get("asks", [])

    best_bid = float(bids[0]["price"]) if bids else 0
    best_ask = float(asks[0]["price"]) if asks else 1
    real_spread = best_ask - best_bid if best_ask > best_bid else 0

    # Depth within 10% of midpoint (relevant orders)
    low_band = max(midpoint - 0.10, 0)
    high_band = min(midpoint + 0.10, 1)

    near_bid_depth = sum(
        float(b["size"]) for b in bids
        if float(b["price"]) >= low_band
    )
    near_ask_depth = sum(
        float(a["size"]) for a in asks
        if float(a["price"]) <= high_band
    )

    # Total depth all levels
    total_bid = sum(float(b["size"]) for b in bids)
    total_ask = sum(float(a["size"]) for a in asks)

    last_trade = float(book.get("last_trade_price", 0) or 0)

    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "real_spread": round(real_spread, 4),
        "near_bid_depth": round(near_bid_depth, 2),
        "near_ask_depth": round(near_ask_depth, 2),
        "total_bid_depth": round(total_bid, 2),
        "total_ask_depth": round(total_ask, 2),
        "last_trade_price": last_trade,
        "bid_levels": len(bids),
        "ask_levels": len(asks),
    }


async def fetch_orderbooks(token_ids: list[str], midpoints: dict = None) -> dict[str, dict]:
    """Batch fetch orderbooks. Returns {token_id: metrics}."""
    if not token_ids:
        return {}

    now = time.time()
    results = {}
    to_fetch = []
    midpoints = midpoints or {}

    for tid in token_ids:
        if not tid:
            continue
        cached = _clob_cache.get(tid)
        if cached and (now - cached["ts"]) < CACHE_TTL:
            results[tid] = cached["data"]
        else:
            to_fetch.append(tid)

    if not to_fetch:
        return results

    for i in range(0, len(to_fetch), 20):
        chunk = to_fetch[i:i + 20]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                payload = [{"token_id": tid} for tid in chunk]
                resp = await client.post(f"{CLOB_API}/books", json=payload)
                if resp.status_code != 200:
                    logger.warning(f"CLOB books API {resp.status_code}")
                    continue
                books = resp.json()
                if not isinstance(books, list):
                    continue
                for book in books:
                    asset_id = book.get("asset_id", "")
                    mid = midpoints.get(asset_id, 0.5)
                    metrics = _parse_book(book, mid)
                    _clob_cache[asset_id] = {"data": metrics, "ts": now}
                    results[asset_id] = metrics
        except Exception as e:
            logger.error(f"CLOB batch error: {e}")

    return results


def compute_execution_hints(market: dict, clob_depth: dict | None = None) -> dict:
    """Compute execution hints from Gamma bestBid/bestAsk + CLOB depth."""
    best_bid = market.get("best_bid", 0)
    best_ask = market.get("best_ask", 0)
    yes_price = market.get("yes_price", 0.5)
    liquidity = market.get("liquidity", 0)

    # Real spread from Gamma CLOB data
    if best_bid > 0 and best_ask > 0:
        spread_abs = best_ask - best_bid
        spread_pct = round(spread_abs / best_ask * 100, 2) if best_ask > 0 else 0
    else:
        spread_abs = 0
        spread_pct = 0

    # Depth quality from CLOB or estimated from Gamma liquidity
    if clob_depth:
        near_bid = clob_depth.get("near_bid_depth", 0)
        near_ask = clob_depth.get("near_ask_depth", 0)
        total_depth = near_bid + near_ask
    else:
        near_bid = 0
        near_ask = 0
        total_depth = liquidity  # Gamma liquidity as proxy

    if total_depth > 10000:
        depth_quality = "deep"
    elif total_depth > 2000:
        depth_quality = "moderate"
    elif total_depth > 500:
        depth_quality = "thin"
    else:
        depth_quality = "empty"

    # Entry recommendation
    if spread_pct > 10:
        entry_hint = "LIMIT_ONLY"
    elif spread_pct > 3:
        entry_hint = "LIMIT_PREFERRED"
    elif depth_quality in ("deep", "moderate"):
        entry_hint = "MARKET_OK"
    else:
        entry_hint = "LIMIT_PREFERRED"

    # Slippage estimate for $100 trade
    slippage_100 = 0
    if near_ask > 0:
        slippage_100 = min(100 / near_ask * spread_pct, 10) if near_ask > 50 else 5.0
    elif total_depth > 0:
        slippage_100 = min(100 / total_depth * 100, 10)

    # Imbalance
    imbalance = 0
    if near_bid + near_ask > 0:
        imbalance = round((near_bid - near_ask) / (near_bid + near_ask), 3)

    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread_abs": round(spread_abs, 4),
        "spread_pct": spread_pct,
        "depth_quality": depth_quality,
        "total_depth": round(total_depth, 2),
        "bid_depth": round(near_bid, 2),
        "ask_depth": round(near_ask, 2),
        "slippage_100": round(slippage_100, 2),
        "entry_hint": entry_hint,
        "imbalance": imbalance,
        "last_trade": clob_depth.get("last_trade_price", 0) if clob_depth else 0,
        "bid_levels": clob_depth.get("bid_levels", 0) if clob_depth else 0,
        "ask_levels": clob_depth.get("ask_levels", 0) if clob_depth else 0,
    }
