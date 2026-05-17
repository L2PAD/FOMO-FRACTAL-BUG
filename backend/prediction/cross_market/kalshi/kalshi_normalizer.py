"""
Kalshi Normalizer — converts raw Kalshi market data into our standard format.

Output: NormalizedMarket dict matching our internal structure.
"""
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger("cross_market.kalshi.normalizer")


def normalize_market(raw: dict) -> dict:
    """Normalize a single Kalshi market to our internal format."""
    ticker = raw.get("ticker", "")
    title = raw.get("title", "")
    rules = raw.get("rules_primary", "") or ""

    # Extract prices (Kalshi uses dollars 0.00-1.00)
    yes_bid = _parse_float(raw.get("yes_bid_dollars"))
    yes_ask = _parse_float(raw.get("yes_ask_dollars"))
    no_bid = _parse_float(raw.get("no_bid_dollars"))
    no_ask = _parse_float(raw.get("no_ask_dollars"))

    # Best estimate of current price
    if yes_bid is not None and yes_ask is not None and yes_bid > 0:
        yes_price = round((yes_bid + yes_ask) / 2, 4)
    elif yes_bid is not None and yes_bid > 0:
        yes_price = yes_bid
    elif yes_ask is not None:
        yes_price = yes_ask
    else:
        last = _parse_float(raw.get("last_price_dollars"))
        yes_price = last if last is not None else 0

    # Spread calculation
    spread = None
    if yes_bid is not None and yes_ask is not None:
        spread = round(yes_ask - yes_bid, 4) if yes_ask > yes_bid else 0

    # Volume
    volume = _parse_float(raw.get("volume_fp")) or 0
    volume_24h = _parse_float(raw.get("volume_24h_fp")) or 0
    open_interest = _parse_float(raw.get("open_interest_fp")) or 0
    liquidity = _parse_float(raw.get("liquidity_dollars")) or 0

    # Expiry
    close_time = raw.get("close_time", "")
    expiry_ts = _parse_timestamp(close_time)

    # Extract entity and threshold from ticker/rules
    entity = _extract_entity(ticker, title, rules)
    threshold, direction = _extract_threshold(ticker, rules)

    return {
        "id": f"kalshi:{ticker}",
        "platform": "kalshi",
        "ticker": ticker,
        "event_ticker": raw.get("event_ticker", ""),
        "series_ticker": _extract_series(ticker),
        "question": title,
        "rules": rules,
        "yes_price": yes_price,
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_bid": no_bid,
        "no_ask": no_ask,
        "spread": spread,
        "volume": volume,
        "volume_24h": volume_24h,
        "open_interest": open_interest,
        "liquidity": liquidity,
        "close_time": close_time,
        "expiry_ts": expiry_ts,
        "entity": entity,
        "threshold": threshold,
        "direction": direction,
        "status": raw.get("status", ""),
        "market_type": raw.get("market_type", ""),
    }


def normalize_all(raw_markets: list[dict]) -> list[dict]:
    """Normalize all Kalshi markets."""
    normalized = [normalize_market(m) for m in raw_markets]
    logger.info(f"[KalshiNorm] Normalized {len(normalized)} markets")
    return normalized


# ═══ Helpers ═══

def _parse_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_timestamp(iso_str: str) -> float | None:
    """Parse ISO timestamp to epoch ms."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.timestamp() * 1000
    except (ValueError, TypeError):
        return None


def _extract_entity(ticker: str, title: str, rules: str) -> str:
    """Extract primary entity (BTC, ETH, etc.)."""
    t_upper = ticker.upper()
    if "KXBTC" in t_upper or "bitcoin" in title.lower() or "bitcoin" in rules.lower():
        return "BTC"
    if "KXETH" in t_upper or "ethereum" in title.lower() or "ethereum" in rules.lower():
        return "ETH"
    if "KXSOL" in t_upper or "solana" in title.lower():
        return "SOL"
    return "UNKNOWN"


def _extract_threshold(ticker: str, rules: str) -> tuple[float, str | None]:
    """Extract price threshold and direction from ticker or rules.

    Kalshi tickers: KXBTC-26APR0117-T76249.99 (T=above), B75875 (B=between)
    """
    # From ticker: T{threshold} = above, B{threshold} = between range start
    ticker_match = re.search(r'-T(\d+\.?\d*)', ticker)
    if ticker_match:
        val = float(ticker_match.group(1))
        return val, "ABOVE"

    ticker_match = re.search(r'-B(\d+\.?\d*)', ticker)
    if ticker_match:
        val = float(ticker_match.group(1))
        return val, "BETWEEN"

    # From rules text
    above_match = re.search(r'above\s+(\d[\d,]*\.?\d*)', rules.lower())
    if above_match:
        val = float(above_match.group(1).replace(",", ""))
        return val, "ABOVE"

    below_match = re.search(r'below\s+(\d[\d,]*\.?\d*)', rules.lower())
    if below_match:
        val = float(below_match.group(1).replace(",", ""))
        return val, "BELOW"

    between_match = re.search(r'between\s+(\d[\d,]*\.?\d*)', rules.lower())
    if between_match:
        val = float(between_match.group(1).replace(",", ""))
        return val, "BETWEEN"

    return 0, None


def _extract_series(ticker: str) -> str:
    """Extract series ticker from market ticker."""
    parts = ticker.split("-")
    if parts:
        return parts[0]
    return ""
