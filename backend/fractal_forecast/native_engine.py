"""
Fractal Native Engine (v1) — P1 SIGNAL HYGIENE
================================================
Python-native fractal forecast engine that REPLACES the Node :8003
sidecar dependency.  Honest cycle / recurrence / macro-analog logic —
NOT a TA wrapper.

Design contract:
    * Fractal looks at:  recurrence · structural similarity · macro
      pattern analogs · regime echoes · cycle position.
    * Fractal NEVER reads decision_history as a primary source.
    * Output identity:  source = "fractal_native_v1"
    * No network to :8003.  Uses yfinance public historical data and
      computes everything in-process.

Algorithm (per asset · per horizon):

    1.  Pull daily close history (~6 years) via yfinance for the asset
        and for DXY + SPX as macro regime anchors.

    2.  Build the CURRENT window: log returns of the last N days
        (N = 120 daily bars).

    3.  Slide the same length window backwards through history.  For
        each historical window compute cosine similarity to the current
        window's normalized return vector.  This is a recurrence /
        self-similarity scan — NOT pattern recognition.

    4.  Compute macro regime tags for the CURRENT window:
            - DXY slope sign over last 60d:  +1 / 0 / -1
            - SPX drawdown bucket vs 252d high:
                ≥ 95% high   → 'spx_near_high'
                85-95%       → 'spx_mid'
                70-85%       → 'spx_correction'
                < 70%        → 'spx_bear'
        Tag each historical analog with its own regime.

    5.  Rank analogs by similarity, then prefer analogs whose macro
        regime tags match the current regime.  If enough matched
        analogs exist (≥ 5), use only them; otherwise fall back to top
        similarity unfiltered.  We never invent a regime match — we
        record `regimeMatchUsed: True/False`.

    6.  For each of the top K = 15 selected analogs, look at the FORWARD
        return over `horizon_days` (clipped to ±50% to avoid one
        catastrophic analog dominating).

    7.  Aggregate the K forward returns:
            - expectedReturn   = median forward return
            - direction        = UP / DOWN / NEUTRAL based on
                                 sign and magnitude of median
            - confidence       = scaled by:
                                  (a) share of analogs agreeing
                                      with median direction
                                  (b) similarity quality of analogs
                                  (c) sample size penalty if < K

    8.  Return one document per horizon with full transparency:
        analogCount, regimeMatchUsed, avgSimilarity, dominantRegime,
        modelVersion = "fractal_native_v1".

We deliberately keep the engine LEGIBLE — every step is observable and
auditable.  It is honest fractal territory; no RSI, no MACD, no
support / resistance heuristics.  Those belong in TA, not Fractal.
"""

from __future__ import annotations

import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


logger = logging.getLogger("fractal_native_engine")

# ── Tunables (honest, auditable) ─────────────────────────────────────
WINDOW_DAYS         = 120   # length of the "current" window
TOP_K_ANALOGS       = 15    # how many historical analogs we summarize over
MIN_REGIME_ANALOGS  = 5     # need ≥ this many matched analogs to use regime filter
HISTORY_YEARS       = 6     # how far back we pull
NEUTRAL_BAND_PCT    = 0.015 # |median forward return| ≤ this → NEUTRAL
ANALOG_RETURN_CLIP  = 0.50  # clip each analog forward return to ±50%

YFINANCE_TICKERS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "SPX": "^GSPC",
    # DXY: use the ICE futures spot symbol; `DX=F` and `^DXY` are
    # frequently unavailable / delisted in yfinance.
    "DXY": "DX-Y.NYB",
    # ── P1-D.2 · Production universe expansion ─────────────────────
    # Yahoo's default `<SYM>-USD` mapping works for most majors; ARB
    # is special-cased because the bare ARB-USD ticker points to an
    # unrelated asset (yields ~$0.00075). For tokens younger than
    # `WINDOW_DAYS + 365` days the engine will return `degraded` with
    # reason `asset_history_unavailable` — this is the honest
    # behaviour requested by the operator.
    "DOGE": "DOGE-USD",
    "LINK": "LINK-USD",
    "AVAX": "AVAX-USD",
    "ARB":  "ARB11841-USD",
    "OP":   "OP-USD",
    "ADA":  "ADA-USD",
    "BNB":  "BNB-USD",
    "XRP":  "XRP-USD",
}

# Macro anchors used for the regime tag.  These are SHARED across all
# asset forecasts (DXY trend, SPX drawdown) — they are the same macro
# regime the entire market lives inside.
MACRO_TICKERS = ("DXY", "SPX")


# ── Data fetch ───────────────────────────────────────────────────────
def _fetch_close_series_ccxt(asset: str) -> Optional["pd.Series"]:
    """P1-D.2 · CCXT cascade fallback for crypto close series.

    Used when yfinance fails to return enough history (rate-limit,
    delisted Yahoo ticker, geo-block, etc.). Returns None — never
    fabricates — and lets the caller mark the forecast as degraded.

    Only crypto tickers (not SPX/DXY) are eligible; macro anchors stay
    on yfinance because no CEX provides them.
    """
    if pd is None:
        return None
    if asset.upper() in ("SPX", "DXY"):
        return None
    try:
        import asyncio as _aio

        import ccxt.async_support as ccxt_async

        async def _fetch():
            # Coinbase has the longest crypto history we can reach freely.
            for venue, quote in (
                ("coinbase", "USD"),
                ("kraken",   "USD"),
                ("kucoin",   "USDT"),
                ("okx",      "USDT"),
            ):
                cls = getattr(ccxt_async, venue, None)
                if cls is None:
                    continue
                client = cls({"enableRateLimit": True, "timeout": 15_000})
                try:
                    sym = f"{asset.upper()}/{quote}"
                    # CCXT caps `limit` per venue (coinbase ~300). We loop
                    # backward using `since` for ~6yrs (≈2200 daily bars).
                    target = WINDOW_DAYS + 365 + 60  # small buffer
                    accumulated: list = []
                    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                    while len(accumulated) < target:
                        since_ms = end_ms - 300 * 86_400_000
                        batch = await client.fetch_ohlcv(sym, timeframe="1d", since=since_ms, limit=300)
                        if not batch:
                            break
                        # batch ascending; prepend to accumulated, dedup by ts
                        existing_ts = {row[0] for row in accumulated}
                        for row in batch:
                            if isinstance(row, list) and len(row) >= 5 and row[0] not in existing_ts:
                                accumulated.append(row)
                        # Move window further back
                        earliest = min(r[0] for r in batch)
                        if earliest >= end_ms - 1:
                            break  # no further history available
                        end_ms = earliest
                        if len(batch) < 100:
                            break  # venue exhausted
                    if accumulated and len(accumulated) >= 200:
                        accumulated.sort(key=lambda r: r[0])
                        return accumulated
                finally:
                    try:
                        await client.close()
                    except Exception:
                        pass
            return []

        try:
            ohlcv = _aio.run(_fetch())
        except RuntimeError:
            return None  # already in event loop — skip CCXT fallback
        if not ohlcv:
            return None
        # Build pandas Series indexed by date.
        idx = [datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc) for row in ohlcv]
        closes = [float(row[4]) for row in ohlcv if row[4] is not None]
        if len(closes) != len(idx):
            return None
        s = pd.Series(closes, index=pd.DatetimeIndex(idx))
        s = s[~s.index.duplicated(keep="last")].sort_index().dropna()
        return s if s.shape[0] >= 200 else None
    except Exception as e:
        logger.warning(f"[fractal_native] ccxt fallback failed for {asset}: {e}")
        return None


def _fetch_close_series(ticker_key: str) -> Optional["pd.Series"]:
    """Pull daily close history for `ticker_key` (one of YFINANCE_TICKERS).
    Returns None on any failure — caller treats this as DEGRADED, not an
    excuse to fabricate."""
    if yf is None or pd is None:
        return None
    sym = YFINANCE_TICKERS.get(ticker_key.upper())
    if not sym:
        return None
    yf_close: Optional["pd.Series"] = None
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=HISTORY_YEARS * 365 + 30)
        df = yf.download(
            sym,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if df is None or df.empty:
            yf_close = None
        else:
            # yfinance may return multi-index columns when threads=False on some versions;
            # collapse to single 'Close' series.
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    close = df[("Close", sym)] if ("Close", sym) in df.columns else df["Close"].iloc[:, 0]
                except Exception:
                    close = df["Close"]
            else:
                close = df["Close"]
            close = close.dropna()
            if close.shape[0] >= (WINDOW_DAYS + 365):
                return close
            # Less than minimum required — try CCXT fallback for crypto.
            yf_close = close if close.shape[0] > 0 else None
    except Exception as e:
        logger.warning(f"[fractal_native] yfinance fetch failed for {ticker_key}/{sym}: {e}")
        yf_close = None

    # P1-D.2 · CCXT cascade fallback (crypto only).  Returns None if
    # the venue cascade can't reach `WINDOW_DAYS + 365` either, which
    # is the honest "not enough history" signal for newer tokens.
    ccxt_close = _fetch_close_series_ccxt(ticker_key)
    if ccxt_close is not None and ccxt_close.shape[0] >= (WINDOW_DAYS + 365):
        return ccxt_close
    # Neither source had enough — surface the longer of the two for
    # diagnostic logs, but signal degraded to the caller.
    if yf_close is not None and ccxt_close is not None:
        return yf_close if yf_close.shape[0] >= ccxt_close.shape[0] else ccxt_close
    return yf_close if yf_close is not None else ccxt_close


# ── Recurrence kernel ────────────────────────────────────────────────
def _log_returns(close: "pd.Series") -> np.ndarray:
    """Daily log returns as 1-D numpy array."""
    if pd is None:
        return np.array([])
    arr = np.asarray(close.values, dtype=float)
    if arr.size < 2:
        return np.array([])
    lr = np.diff(np.log(np.maximum(arr, 1e-12)))
    return lr


def _normalize(v: np.ndarray) -> np.ndarray:
    """Z-score normalize so analogs aren't dominated by absolute magnitude."""
    if v.size == 0:
        return v
    mu = float(np.mean(v))
    sd = float(np.std(v))
    if sd < 1e-9:
        return v - mu
    return (v - mu) / sd


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ── Macro regime tagging ─────────────────────────────────────────────
def _regime_tag_for_index(close: "pd.Series", end_idx: int) -> dict:
    """Compute the macro regime tag at integer position `end_idx` (window
    end) within `close`.  Pure read — never mutates."""
    if pd is None:
        return {"dxyTrend": 0, "spxBucket": "unknown"}
    if end_idx < 252:
        return {"dxyTrend": 0, "spxBucket": "unknown"}
    # we DON'T have DXY/SPX per-row here — caller fills those.  This
    # function exists to keep the regime semantics central.
    return {}


def _macro_regime_now(spx_close, dxy_close) -> dict:
    """Current macro regime tag using last available data."""
    tag = {"dxyTrend": 0, "spxBucket": "unknown"}
    if pd is None:
        return tag
    # DXY trend: sign of slope over last 60d (simple linear fit)
    if dxy_close is not None and len(dxy_close) >= 60:
        last = np.asarray(dxy_close.values[-60:], dtype=float)
        x = np.arange(last.size, dtype=float)
        try:
            slope = float(np.polyfit(x, last, 1)[0])
        except Exception:
            slope = 0.0
        # threshold tied to typical DXY scale (~100)
        if slope > 0.02:
            tag["dxyTrend"] = 1
        elif slope < -0.02:
            tag["dxyTrend"] = -1
        else:
            tag["dxyTrend"] = 0
    # SPX drawdown bucket vs trailing 252d high
    if spx_close is not None and len(spx_close) >= 252:
        last = np.asarray(spx_close.values[-252:], dtype=float)
        ratio = float(last[-1] / np.max(last)) if np.max(last) > 0 else 1.0
        if ratio >= 0.95:
            tag["spxBucket"] = "spx_near_high"
        elif ratio >= 0.85:
            tag["spxBucket"] = "spx_mid"
        elif ratio >= 0.70:
            tag["spxBucket"] = "spx_correction"
        else:
            tag["spxBucket"] = "spx_bear"
    return tag


def _macro_regime_at(spx_close, dxy_close, idx: int) -> dict:
    """Regime tag AT integer index `idx` (treated as 'today' inside the
    analog history)."""
    tag = {"dxyTrend": 0, "spxBucket": "unknown"}
    if pd is None:
        return tag
    if dxy_close is not None and idx >= 60 and idx < len(dxy_close):
        last = np.asarray(dxy_close.values[idx - 60:idx], dtype=float)
        if last.size >= 30:
            x = np.arange(last.size, dtype=float)
            try:
                slope = float(np.polyfit(x, last, 1)[0])
            except Exception:
                slope = 0.0
            if slope > 0.02:
                tag["dxyTrend"] = 1
            elif slope < -0.02:
                tag["dxyTrend"] = -1
    if spx_close is not None and idx >= 252 and idx < len(spx_close):
        last = np.asarray(spx_close.values[idx - 252:idx], dtype=float)
        if last.size >= 200 and float(np.max(last)) > 0:
            ratio = float(last[-1] / np.max(last))
            if ratio >= 0.95:
                tag["spxBucket"] = "spx_near_high"
            elif ratio >= 0.85:
                tag["spxBucket"] = "spx_mid"
            elif ratio >= 0.70:
                tag["spxBucket"] = "spx_correction"
            else:
                tag["spxBucket"] = "spx_bear"
    return tag


# ── Core: find analogs and aggregate forward returns ─────────────────
def _find_analogs(
    asset_lr: np.ndarray,
    spx_close, dxy_close,
    asset_close,
) -> Tuple[List[dict], dict]:
    """Returns (top_analogs, current_regime).

    Each analog dict carries:
        idx_end    — integer position where the analog window ends
        sim        — cosine similarity to current window
        regime     — macro regime tag at idx_end
    """
    if asset_lr.size < WINDOW_DAYS + 365:
        return [], {"dxyTrend": 0, "spxBucket": "unknown"}

    # Current window: the last WINDOW_DAYS of log returns, normalized
    cur = _normalize(asset_lr[-WINDOW_DAYS:])

    # Slide windows.  Keep a "blackout" of 2× WINDOW_DAYS at the end so
    # analogs don't overlap with the present (avoids look-ahead leak).
    blackout_end = asset_lr.size - 2 * WINDOW_DAYS
    if blackout_end <= WINDOW_DAYS + 30:
        return [], {"dxyTrend": 0, "spxBucket": "unknown"}

    # Index alignment: asset_lr[i] is the log-return ENDING at
    # asset_close[i+1].  So an analog window ending at lr index `j`
    # corresponds to asset_close position `j+1`.
    candidates: List[dict] = []
    # Step every 5 days to bound compute; 6y ≈ 1500 trading days /5 = 300 windows
    step = 5
    for j in range(WINDOW_DAYS, blackout_end, step):
        win = asset_lr[j - WINDOW_DAYS:j]
        if win.size != WINDOW_DAYS:
            continue
        wn = _normalize(win)
        sim = _cosine(cur, wn)
        if not math.isfinite(sim):
            continue
        # corresponding asset_close position (window end + 1)
        close_idx = j + 1
        regime = _macro_regime_at(spx_close, dxy_close, close_idx)
        candidates.append({
            "idxEnd": int(j),
            "closeIdx": int(close_idx),
            "sim": float(sim),
            "regime": regime,
        })

    # Current regime
    cur_regime = _macro_regime_now(spx_close, dxy_close)

    # Sort by similarity desc, then optionally filter by regime match
    candidates.sort(key=lambda d: d["sim"], reverse=True)
    matched = [
        a for a in candidates
        if a["regime"].get("dxyTrend") == cur_regime.get("dxyTrend")
        and a["regime"].get("spxBucket") == cur_regime.get("spxBucket")
    ]
    if len(matched) >= MIN_REGIME_ANALOGS:
        top = matched[:TOP_K_ANALOGS]
        cur_regime["matchUsed"] = True
    else:
        top = candidates[:TOP_K_ANALOGS]
        cur_regime["matchUsed"] = False

    return top, cur_regime


def _aggregate_forward(
    analogs: List[dict],
    asset_close,
    horizon_days: int,
) -> dict:
    """For each analog, look at the forward return over horizon_days
    starting at the analog's close index.  Aggregate to direction +
    expected return + confidence."""
    if pd is None or asset_close is None or not analogs:
        return {
            "direction":      "NEUTRAL",
            "expectedReturn": 0.0,
            "confidence":     0.0,
            "analogCount":    0,
            "avgSimilarity":  0.0,
            "agreeShare":     0.0,
        }
    rets: List[float] = []
    sims: List[float] = []
    arr = np.asarray(asset_close.values, dtype=float)
    n = arr.size
    for a in analogs:
        ci = a["closeIdx"]
        ci_fwd = ci + horizon_days
        if ci_fwd >= n or ci <= 0:
            continue
        p0 = float(arr[ci])
        p1 = float(arr[ci_fwd])
        if p0 <= 0 or p1 <= 0:
            continue
        r = (p1 / p0) - 1.0
        # Clip extreme analog moves so one bear-market-bottom doesn't
        # dominate the median.
        r = max(-ANALOG_RETURN_CLIP, min(ANALOG_RETURN_CLIP, r))
        rets.append(r)
        sims.append(float(a["sim"]))

    if not rets:
        return {
            "direction":      "NEUTRAL",
            "expectedReturn": 0.0,
            "confidence":     0.0,
            "analogCount":    0,
            "avgSimilarity":  0.0,
            "agreeShare":     0.0,
        }

    rets_arr = np.asarray(rets, dtype=float)
    median_ret = float(np.median(rets_arr))
    avg_sim = float(np.mean(sims)) if sims else 0.0

    # Direction
    if median_ret > NEUTRAL_BAND_PCT:
        direction = "UP"
    elif median_ret < -NEUTRAL_BAND_PCT:
        direction = "DOWN"
    else:
        direction = "NEUTRAL"

    # Agreement share: % of analogs whose forward return sign matches
    # the median's sign.
    if direction == "UP":
        agree = float(np.mean(rets_arr > 0))
    elif direction == "DOWN":
        agree = float(np.mean(rets_arr < 0))
    else:
        # For NEUTRAL we just look at concentration around zero
        agree = float(np.mean(np.abs(rets_arr) <= NEUTRAL_BAND_PCT))

    # Confidence:
    #   base = agree share scaled by avg_sim (which is in [-1, 1])
    #   sample penalty: full at K analogs, linear down
    sim_scale = max(0.0, (avg_sim + 1.0) / 2.0)  # map [-1,1] → [0,1]
    sample_factor = min(1.0, len(rets) / float(TOP_K_ANALOGS))
    conf = agree * sim_scale * sample_factor
    # Cap to 0.85 — fractal alone never speaks at full conviction.
    conf = min(0.85, max(0.0, conf))

    return {
        "direction":      direction,
        "expectedReturn": round(median_ret, 4),
        "confidence":     round(conf, 4),
        "analogCount":    int(len(rets)),
        "avgSimilarity":  round(avg_sim, 4),
        "agreeShare":     round(agree, 4),
    }


# ── Public API ───────────────────────────────────────────────────────
def compute_native_forecast(asset: str, horizons_days: Dict[str, int]) -> dict:
    """Compute a full native fractal forecast for `asset` (e.g. 'BTC')
    across the given horizons.

    Returns:
        {
          "ok": bool,
          "asset": "BTC",
          "currentPrice": float,
          "currentRegime": {dxyTrend, spxBucket, matchUsed},
          "horizons": {
              "7D":   {direction, expectedReturn, confidence, analogCount, ...},
              "30D":  {...},
              ...
          },
          "modelVersion": "fractal_native_v1",
          "asOf": ISO,
          "source": "fractal_native_v1",
          "degraded": bool,
          "reason": str | None,
        }

    On any data-fetch failure → ok=False, degraded=True, reason=<str>.
    No silent fabrication.
    """
    asset = asset.upper()
    now = datetime.now(timezone.utc)
    if yf is None or pd is None:
        return {
            "ok": False, "degraded": True,
            "reason": "yfinance_or_pandas_unavailable",
            "asset": asset, "asOf": now.isoformat(),
            "modelVersion": "fractal_native_v1",
            "source": "fractal_native_v1",
            "horizons": {},
        }

    if asset not in YFINANCE_TICKERS:
        return {
            "ok": False, "degraded": True,
            "reason": f"unsupported_asset_{asset}",
            "asset": asset, "asOf": now.isoformat(),
            "modelVersion": "fractal_native_v1",
            "source": "fractal_native_v1",
            "horizons": {},
        }

    asset_close = _fetch_close_series(asset)
    if asset_close is None:
        return {
            "ok": False, "degraded": True,
            "reason": "asset_history_unavailable",
            "asset": asset, "asOf": now.isoformat(),
            "modelVersion": "fractal_native_v1",
            "source": "fractal_native_v1",
            "horizons": {},
        }

    spx_close = _fetch_close_series("SPX")
    dxy_close = _fetch_close_series("DXY")
    # Macro is OPTIONAL — engine still works without it, but we record
    # that regime filter wasn't used.
    spx_ok = spx_close is not None
    dxy_ok = dxy_close is not None

    asset_lr = _log_returns(asset_close)
    analogs, cur_regime = _find_analogs(asset_lr, spx_close, dxy_close, asset_close)

    if not analogs:
        return {
            "ok": False, "degraded": True,
            "reason": "insufficient_history_for_recurrence_scan",
            "asset": asset, "asOf": now.isoformat(),
            "modelVersion": "fractal_native_v1",
            "source": "fractal_native_v1",
            "horizons": {},
        }

    current_price = float(asset_close.values[-1])

    horizons_out: Dict[str, dict] = {}
    for hkey, hdays in horizons_days.items():
        agg = _aggregate_forward(analogs, asset_close, hdays)
        target_price = current_price * (1.0 + agg["expectedReturn"])
        horizons_out[hkey] = {
            "direction":       agg["direction"],
            "expectedReturn":  agg["expectedReturn"],
            "confidence":      agg["confidence"],
            "analogCount":     agg["analogCount"],
            "avgSimilarity":   agg["avgSimilarity"],
            "agreeShare":      agg["agreeShare"],
            "entryPrice":      round(current_price, 4),
            "targetPrice":     round(target_price, 4),
            "horizonDays":     int(hdays),
        }

    return {
        "ok": True,
        "degraded": False,
        "reason": None,
        "asset": asset,
        "currentPrice": round(current_price, 4),
        "currentRegime": {
            "dxyTrend":   cur_regime.get("dxyTrend", 0),
            "spxBucket":  cur_regime.get("spxBucket", "unknown"),
            "matchUsed":  bool(cur_regime.get("matchUsed", False)),
            "spxAvailable": spx_ok,
            "dxyAvailable": dxy_ok,
        },
        "horizons":      horizons_out,
        "modelVersion":  "fractal_native_v1",
        "source":        "fractal_native_v1",
        "asOf":          now.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────
# Public API: forward TRAJECTORY (daily curve) from analog cohort
# ─────────────────────────────────────────────────────────────────────
def compute_native_forward_trajectory(
    asset: str,
    horizon_days: int,
) -> dict:
    """Return the **daily median forward trajectory** built from the
    top-K historical analogs that match the current 120-day window.

    This is what powers the *curve* drawn on the Fractal overview chart:
    instead of linearly interpolating from entry → target, we replay the
    median normalized path of analog cohorts day by day.

    Returns:
        {
          "ok": bool,
          "asset": "BTC",
          "currentPrice": float,
          "horizonDays": int,
          "trajectory": [
              {"day": 0, "ratio": 1.0, "price": <currentPrice>},
              {"day": 1, "ratio": <median ratio>, "price": <px>},
              ...
              {"day": H, "ratio": ..., "price": <targetPrice>}
          ],
          "analogCount": int,
          "modelVersion": "fractal_native_v1",
          "source": "fractal_native_v1",
          "asOf": ISO,
        }

    On any failure → ok=False with degraded/reason fields and an empty
    trajectory.  No silent fabrication.
    """
    asset = asset.upper()
    now = datetime.now(timezone.utc)
    horizon_days = max(1, int(horizon_days))

    if yf is None or pd is None:
        return {
            "ok": False, "degraded": True,
            "reason": "yfinance_or_pandas_unavailable",
            "asset": asset, "horizonDays": horizon_days,
            "trajectory": [], "analogCount": 0,
            "modelVersion": "fractal_native_v1",
            "source": "fractal_native_v1",
            "asOf": now.isoformat(),
        }

    if asset not in YFINANCE_TICKERS:
        return {
            "ok": False, "degraded": True,
            "reason": f"unsupported_asset_{asset}",
            "asset": asset, "horizonDays": horizon_days,
            "trajectory": [], "analogCount": 0,
            "modelVersion": "fractal_native_v1",
            "source": "fractal_native_v1",
            "asOf": now.isoformat(),
        }

    asset_close = _fetch_close_series(asset)
    if asset_close is None:
        return {
            "ok": False, "degraded": True,
            "reason": "asset_history_unavailable",
            "asset": asset, "horizonDays": horizon_days,
            "trajectory": [], "analogCount": 0,
            "modelVersion": "fractal_native_v1",
            "source": "fractal_native_v1",
            "asOf": now.isoformat(),
        }

    spx_close = _fetch_close_series("SPX")
    dxy_close = _fetch_close_series("DXY")
    asset_lr = _log_returns(asset_close)
    analogs, _cur_regime = _find_analogs(asset_lr, spx_close, dxy_close, asset_close)

    if not analogs:
        return {
            "ok": False, "degraded": True,
            "reason": "no_analogs_found",
            "asset": asset, "horizonDays": horizon_days,
            "trajectory": [], "analogCount": 0,
            "modelVersion": "fractal_native_v1",
            "source": "fractal_native_v1",
            "asOf": now.isoformat(),
        }

    arr = np.asarray(asset_close.values, dtype=float)
    n = arr.size
    current_price = float(arr[-1])

    # Collect each analog's forward ratio path (length = horizon_days + 1).
    #   ratio[d] = close[closeIdx + d] / close[closeIdx]
    paths: List[np.ndarray] = []
    for a in analogs:
        ci = int(a.get("closeIdx") or 0)
        if ci <= 0 or ci + horizon_days >= n:
            continue
        base = float(arr[ci])
        if base <= 0:
            continue
        seg = arr[ci: ci + horizon_days + 1]
        if seg.size != horizon_days + 1:
            continue
        ratios = seg / base
        # Clip catastrophic single-analog moves so one outlier doesn't
        # dominate the median curve.
        ratios = np.clip(
            ratios,
            1.0 - ANALOG_RETURN_CLIP,
            1.0 + ANALOG_RETURN_CLIP,
        )
        paths.append(ratios.astype(float))

    if not paths:
        return {
            "ok": False, "degraded": True,
            "reason": "no_complete_analog_paths",
            "asset": asset, "horizonDays": horizon_days,
            "trajectory": [], "analogCount": 0,
            "modelVersion": "fractal_native_v1",
            "source": "fractal_native_v1",
            "asOf": now.isoformat(),
        }

    # Median across analogs at each forward day → preserves the
    # characteristic SHAPE of historical cohorts (curves, drawdowns,
    # mean-reversion bumps), not a straight line.
    stack = np.vstack(paths)        # shape: (K, H+1)
    median_curve = np.median(stack, axis=0)
    # Anchor day 0 to exactly 1.0 (entry).
    median_curve[0] = 1.0

    trajectory: List[dict] = []
    for d in range(horizon_days + 1):
        ratio = float(median_curve[d])
        trajectory.append({
            "day":   int(d),
            "ratio": round(ratio, 6),
            "price": round(current_price * ratio, 4),
        })

    return {
        "ok": True,
        "degraded": False,
        "reason": None,
        "asset": asset,
        "currentPrice": round(current_price, 4),
        "horizonDays":  horizon_days,
        "trajectory":   trajectory,
        "analogCount":  int(len(paths)),
        "modelVersion": "fractal_native_v1",
        "source":       "fractal_native_v1",
        "asOf":         now.isoformat(),
    }
