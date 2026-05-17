"""
FOMO OS · Core Universe — Single Source of Truth (P1-B)
========================================================
Production universe registry for the entire system.  All downstream
modules MUST consult this module rather than maintaining their own
asset lists.

This module is **read-only and dependency-free** (stdlib only) so it
can be imported from any layer without circular imports.

Why this exists
---------------
Before P1-B we had three split-brain registries:
  1. `services/asset_registry.py::ASSET_UNIVERSE`     (20 entries, UI universe)
  2. `services/market_prices.py::SYMBOL_TO_CG_ID`     (10 entries, TA universe)
  3. `assets/asset_registry.py::ASSET_REGISTRY`       (3 entries, forecast universe)

Each layer had its own normalize_symbol() and quote-strip logic. Whenever
the trading aggregator received a venue symbol like `BTCUSDT` it would
hit different code paths and silently degrade modules. P1-A patched the
aggregator entry point; P1-B closes the architectural loop by giving the
whole system one canonical universe to read.

Honest by construction:
  * If an asset is listed in PRODUCTION_UNIVERSE here, every layer is
    expected to support it; if a layer cannot, it must degrade honestly
    (not invent data).
  * If an asset is NOT listed here, no layer should fabricate forecasts
    or signals for it — callers should reject the symbol explicitly.

Each entry contains:
  symbol         — canonical bare ticker (e.g. "BTC")
  name           — human-readable display
  coingecko_id   — CoinGecko slug (used by services/market_prices)
  yfinance       — Yahoo Finance ticker (override per asset where the
                   default `<SYM>-USD` is broken; None falls back to
                   `<SYM>-USD`)
  category       — UI grouping (layer1/layer2/defi/meme/infra)
  rank           — approx market-cap rank (used for default sort order)
  venues         — sorted venue preference for OHLC fetch (matches
                   market_data/ohlc_provider.py cascade)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# ── Production universe (single source of truth) ────────────────────────
PRODUCTION_UNIVERSE: Tuple[Dict[str, object], ...] = (
    # Crypto majors / production-ready (5-module verdict ≥3 active).
    {"symbol": "BTC",  "name": "Bitcoin",      "coingecko_id": "bitcoin",      "yfinance": "BTC-USD",        "category": "layer1", "rank": 1},
    {"symbol": "ETH",  "name": "Ethereum",     "coingecko_id": "ethereum",     "yfinance": "ETH-USD",        "category": "layer1", "rank": 2},
    {"symbol": "BNB",  "name": "BNB",          "coingecko_id": "binancecoin",  "yfinance": "BNB-USD",        "category": "layer1", "rank": 4},
    {"symbol": "SOL",  "name": "Solana",       "coingecko_id": "solana",       "yfinance": "SOL-USD",        "category": "layer1", "rank": 5},
    {"symbol": "XRP",  "name": "XRP",          "coingecko_id": "ripple",       "yfinance": "XRP-USD",        "category": "layer1", "rank": 6},
    {"symbol": "DOGE", "name": "Dogecoin",     "coingecko_id": "dogecoin",     "yfinance": "DOGE-USD",       "category": "meme",   "rank": 7},
    {"symbol": "ADA",  "name": "Cardano",      "coingecko_id": "cardano",      "yfinance": "ADA-USD",        "category": "layer1", "rank": 8},
    {"symbol": "AVAX", "name": "Avalanche",    "coingecko_id": "avalanche-2",  "yfinance": "AVAX-USD",       "category": "layer1", "rank": 12},
    {"symbol": "LINK", "name": "Chainlink",    "coingecko_id": "chainlink",    "yfinance": "LINK-USD",       "category": "defi",   "rank": 14},
    # Yahoo's default `ARB-USD` resolves to an unrelated asset; use the
    # numerical override and rely on CCXT fallback inside price_provider.
    {"symbol": "ARB",  "name": "Arbitrum",     "coingecko_id": "arbitrum",     "yfinance": "ARB11841-USD",   "category": "layer2", "rank": 35},
    {"symbol": "OP",   "name": "Optimism",     "coingecko_id": "optimism",     "yfinance": "OP-USD",         "category": "layer2", "rank": 40},
)

# ── Macro anchors (regime context, NOT trading assets) ─────────────────
MACRO_ANCHORS: Tuple[Dict[str, object], ...] = (
    {"symbol": "SPX",  "name": "S&P 500",      "coingecko_id": None,           "yfinance": "^GSPC",          "category": "macro",  "rank": 0},
    {"symbol": "DXY",  "name": "US Dollar Index", "coingecko_id": None,        "yfinance": "DX-Y.NYB",       "category": "macro",  "rank": 0},
)

# ── Indexes ────────────────────────────────────────────────────────────
_BY_SYMBOL: Dict[str, Dict[str, object]] = {
    str(a["symbol"]).upper(): dict(a) for a in (PRODUCTION_UNIVERSE + MACRO_ANCHORS)
}
_BY_CG_ID: Dict[str, str] = {
    str(a["coingecko_id"]).lower(): str(a["symbol"]).upper()
    for a in PRODUCTION_UNIVERSE if a.get("coingecko_id")
}

# Common venue quote suffixes (in priority order — longer first to avoid
# stripping "USD" out of "USDC").
_QUOTE_SUFFIXES: Tuple[str, ...] = (
    "-PERPETUAL", "-PERP", "PERP",
    "-USDT", "USDT",
    "-USDC", "USDC",
    "-USD",  "USD",
    "-BUSD", "BUSD",
    "-FDUSD", "FDUSD",
    "-USDP", "USDP",
    "-DAI",  "DAI",
)


# ── Public API ─────────────────────────────────────────────────────────
def canonical(raw: Optional[str]) -> str:
    """Return the canonical bare ticker for any input form.

    Examples:
      'btc'          → 'BTC'
      'BTCUSDT'      → 'BTC'
      'eth-perp'     → 'ETH'
      'BITCOIN'      → 'BTC'  (via coingecko_id reverse lookup)
      ''             → ''
    """
    if not raw:
        return ""
    s = str(raw).strip().upper()
    if not s:
        return ""
    # Direct hit on canonical symbol.
    if s in _BY_SYMBOL:
        return s
    # Strip venue suffix.
    for suf in _QUOTE_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            base = s[: -len(suf)]
            while base and base[-1] in ("-", "_", "/", ":"):
                base = base[:-1]
            if base in _BY_SYMBOL:
                return base
    # Coingecko ID reverse lookup (e.g. "bitcoin" → "BTC").
    lower = str(raw).strip().lower()
    if lower in _BY_CG_ID:
        return _BY_CG_ID[lower]
    return s  # unknown but still upper-case stripped — honest fallback


def is_supported(raw: Optional[str]) -> bool:
    """True iff `canonical(raw)` is in PRODUCTION_UNIVERSE (not macro)."""
    c = canonical(raw)
    if not c or c not in _BY_SYMBOL:
        return False
    return _BY_SYMBOL[c].get("category") != "macro"


def is_macro(raw: Optional[str]) -> bool:
    c = canonical(raw)
    return c in _BY_SYMBOL and _BY_SYMBOL[c].get("category") == "macro"


def get(raw: Optional[str]) -> Optional[Dict[str, object]]:
    """Return the full registry record for a symbol, or None."""
    c = canonical(raw)
    return dict(_BY_SYMBOL[c]) if c in _BY_SYMBOL else None


def coingecko_id(raw: Optional[str]) -> Optional[str]:
    rec = get(raw)
    return rec.get("coingecko_id") if rec else None  # type: ignore[return-value]


def yfinance_ticker(raw: Optional[str]) -> Optional[str]:
    rec = get(raw)
    if not rec:
        return None
    return rec.get("yfinance") or f"{rec['symbol']}-USD"  # type: ignore[return-value]


def list_production_symbols() -> List[str]:
    """Sorted-by-rank list of production crypto symbols."""
    items = [a for a in PRODUCTION_UNIVERSE]
    items.sort(key=lambda a: int(a.get("rank") or 9999))
    return [str(a["symbol"]).upper() for a in items]


def list_macro_symbols() -> List[str]:
    return [str(a["symbol"]).upper() for a in MACRO_ANCHORS]


def all_symbols(include_macro: bool = True) -> List[str]:
    out = list_production_symbols()
    if include_macro:
        out.extend(list_macro_symbols())
    return out


# Convenient flat dict {symbol: coingecko_id} for legacy callers.
SYMBOL_TO_CG_ID: Dict[str, str] = {
    str(a["symbol"]).upper(): str(a["coingecko_id"])
    for a in PRODUCTION_UNIVERSE if a.get("coingecko_id")
}
