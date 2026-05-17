"""
R1.3 — Research V3 Snapshot Builder
Three modes: global, asset, universe.
Direct function calls for Python services, HTTP only for Node.js labs.
"""

import asyncio
import httpx
import time

NODE_URL = "http://127.0.0.1:8003"


async def _fetch_json(url: str, timeout: float = 10.0):
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(url)
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return None


def _get_radar_selfcheck() -> dict:
    """Direct call to radar selfcheck (avoids HTTP self-call deadlock)."""
    try:
        from radar_v11.routes import radar_selfcheck
        return radar_selfcheck()
    except Exception:
        return {}


def _get_market_board(universe: str = "alpha") -> dict:
    """Direct call to market board."""
    try:
        from radar_v11.spot_engine import scan_spot
        from radar_v11.market_board import build_market_board
        rows = scan_spot(venue=universe, limit=500)
        return build_market_board(rows)
    except Exception:
        return {}


def _get_health() -> dict:
    """Direct call to health."""
    try:
        from exchange_health import compute_health
        return compute_health()
    except Exception:
        return {"status": "UNKNOWN"}


def _get_radar_rows(venue: str = "alpha", limit: int = 500) -> list:
    """Direct call to radar scan."""
    try:
        from radar_v11.spot_engine import scan_spot
        rows = scan_spot(venue=venue, limit=limit)
        return [r.model_dump(mode="json") for r in rows]
    except Exception:
        return []


async def build_global_snapshot(timeframe: str = "15m") -> dict:
    """Global snapshot — BTC labs + radar aggregate + market pulse + health."""
    labs_raw = await _fetch_json(f"{NODE_URL}/api/v10/exchange/labs/v3/all?symbol=BTCUSDT&timeframe={timeframe}")

    radar = _get_radar_selfcheck()
    board = _get_market_board()
    health = _get_health()

    return _pack_snapshot(labs_raw, radar, board, health, symbol="BTCUSDT", timeframe=timeframe)


async def build_asset_snapshot(symbol: str, timeframe: str = "15m") -> dict:
    """Per-asset snapshot — symbol-specific labs + find row in radar scan."""
    labs_raw = await _fetch_json(f"{NODE_URL}/api/v10/exchange/labs/v3/all?symbol={symbol}&timeframe={timeframe}")

    radar = _get_radar_selfcheck()
    board = _get_market_board()
    health = _get_health()

    # Find this symbol's row in radar
    all_rows = _get_radar_rows("alpha", 500)
    asset_row = None
    for row in all_rows:
        if row.get("symbol") == symbol:
            asset_row = row
            break
    if not asset_row:
        main_rows = _get_radar_rows("main", 500)
        for row in main_rows:
            if row.get("symbol") == symbol:
                asset_row = row
                break

    snap = _pack_snapshot(labs_raw, radar, board, health, symbol=symbol, timeframe=timeframe)
    snap["assetRow"] = asset_row
    return snap


async def build_universe_snapshot(timeframe: str = "15m") -> dict:
    """Universe snapshot — aggregate all radar rows + global labs."""
    labs_raw = await _fetch_json(f"{NODE_URL}/api/v10/exchange/labs/v3/all?symbol=BTCUSDT&timeframe={timeframe}")

    radar = _get_radar_selfcheck()
    board = _get_market_board()
    health = _get_health()
    all_rows = _get_radar_rows("alpha", 500)

    snap = _pack_snapshot(labs_raw, radar, board, health, symbol="UNIVERSE", timeframe=timeframe)
    snap["allRows"] = all_rows
    return snap


def _pack_snapshot(labs_raw, radar_data, board_data, health_data, symbol: str, timeframe: str) -> dict:
    labs = {}
    labs_summary = {}
    if labs_raw and labs_raw.get("ok"):
        snap = labs_raw.get("snapshot", {})
        labs = snap.get("labs", {})
        labs_summary = labs_raw.get("summary", {})

    # Radar selfcheck format
    radar = {}
    if radar_data and radar_data.get("ok"):
        radar = {
            "coverage": radar_data.get("coverage", {}),
            "spot": radar_data.get("spot", {}),
            "divergence": radar_data.get("divergence", {}),
        }

    # Market board
    pulse = board_data.get("pulse", {}) if board_data else {}

    # Health
    health = {}
    if health_data:
        health = {
            "status": health_data.get("status", "UNKNOWN"),
            "services": health_data.get("services", {}),
        }

    return {
        "labs": labs,
        "labsSummary": labs_summary,
        "radar": radar,
        "pulse": pulse,
        "health": health,
        "symbol": symbol,
        "timeframe": timeframe,
        "ts": int(time.time()),
    }
