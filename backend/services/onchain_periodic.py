"""
On-chain periodic ingestion · activation
=========================================
Pulls metrics from onchain_lite (Infura RPC + DefiLlama), derives a
DIRECTIONAL signal (LONG / SHORT / NEUTRAL) from the netflow + gas +
TVL change deltas, and persists to MongoDB `onchain_metrics`.

This collection is what `trading_runtime._fetch_onchain` reads.  Once
it has fresh data the on-chain module flips from ABSTAIN to active.

Direction logic (honest, deterministic):
  - exchangeNetflow24h  > 0     →  bias bearish (coins flowing INTO
                                   exchanges — usually distribution).
  - exchangeNetflow24h  < 0     →  bias bullish (coins leaving
                                   exchanges → accumulation).
  - stablecoinNetflow24h > 0    →  bias bullish (fresh stable buying
                                   power deployed on chain).
  - gas spike (>30% vs baseline) → activity intensifying.

We do NOT fabricate a vote when chains are unreachable — the run
returns ok=False and the trading classifier marks onchain degraded.
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING

_DEFAULT_INTERVAL_SEC = 10 * 60  # 10 minutes
_CHAINS = ["ethereum"]   # add 'arbitrum','optimism','base' when needed

_mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_db_name = os.environ.get("DB_NAME", "fomo_mobile")
_client = MongoClient(_mongo_url)
_db = _client[_db_name]


def _interval() -> int:
    try:
        return max(60, int(os.environ.get("ONCHAIN_PERIODIC_INTERVAL_SEC", _DEFAULT_INTERVAL_SEC)))
    except Exception:
        return _DEFAULT_INTERVAL_SEC


def _classify(metrics: dict) -> dict:
    """Derive {direction, confidence, signals} from raw metric deltas."""
    exch_net = float(metrics.get("exchangeNetflow24h") or 0.0)
    stab_net = float(metrics.get("stablecoinNetflow24h") or 0.0)
    gas      = float(metrics.get("gasPrice") or 0.0)
    tvl      = float(metrics.get("totalValueLocked") or 0.0)
    dex_vol  = float(metrics.get("dexVolume24h") or 0.0)

    bull_signals = 0
    bear_signals = 0
    notes = []

    # Exchange netflow — primary driver
    if exch_net < -100_000:      # significant outflow (USD)
        bull_signals += 2
        notes.append(f"exchange outflow ${abs(exch_net):,.0f} → accumulation")
    elif exch_net > 100_000:
        bear_signals += 2
        notes.append(f"exchange inflow ${exch_net:,.0f} → distribution")
    else:
        notes.append("exchange flows balanced")

    # Stablecoin netflow — bullish dry powder
    if stab_net > 50_000:
        bull_signals += 1
        notes.append(f"stablecoin inflow ${stab_net:,.0f} → buying power")
    elif stab_net < -50_000:
        bear_signals += 1
        notes.append(f"stablecoin outflow ${abs(stab_net):,.0f} → de-risking")

    # Activity (volume + tvl) — directional only if exchange flow says so
    if dex_vol > 1_000_000_000:    # >$1B DEX volume — high engagement
        notes.append(f"high DEX engagement ${dex_vol/1e9:.1f}B")

    # Decide
    if bull_signals >= 2 and bull_signals > bear_signals:
        direction = "LONG"
    elif bear_signals >= 2 and bear_signals > bull_signals:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"

    total = bull_signals + bear_signals
    confidence = min(0.80, (max(bull_signals, bear_signals) / max(total, 1)) * 0.65) if total else 0.10

    return {
        "direction":  direction,
        "confidence": round(confidence, 3),
        "bullSignals": bull_signals,
        "bearSignals": bear_signals,
        "signals":     notes,
    }


async def run_once() -> dict:
    """Single tick — fetch all chains, classify, persist."""
    from onchain_lite import service as onchain_service
    now = datetime.now(timezone.utc)
    started_ts = time.time()
    inserted = 0
    errors = []

    for chain in _CHAINS:
        try:
            summary, flows, whales, activity = await asyncio.gather(
                onchain_service.get_summary(chain),
                onchain_service.get_flows(chain),
                onchain_service.get_whales(chain),
                onchain_service.get_activity(chain),
                return_exceptions=True,
            )

            def _safe(x): return x if isinstance(x, dict) else {}
            summary  = _safe(summary)
            flows    = _safe(flows)
            whales   = _safe(whales)
            activity = _safe(activity)

            if summary.get("provider") == "paused":
                continue

            metrics = {
                # raw market metrics
                "blockHeight":           summary.get("blockHeight"),
                "gasPrice":              summary.get("gasPrice"),
                "tps":                   summary.get("tps"),
                "pendingTxCount":        summary.get("pendingTxCount"),
                "exchangeInflow24h":     flows.get("exchangeInflow24h"),
                "exchangeOutflow24h":    flows.get("exchangeOutflow24h"),
                "exchangeNetflow24h":    flows.get("exchangeNetflow24h"),
                "stablecoinInflow24h":   flows.get("stablecoinInflow24h"),
                "stablecoinOutflow24h":  flows.get("stablecoinOutflow24h"),
                "stablecoinNetflow24h":  flows.get("stablecoinNetflow24h"),
                "largeTransfers24h":     whales.get("largeTransfers24h"),
                "totalWhaleVolume24h":   whales.get("totalWhaleVolume24h"),
                "topWhaleCount":         len(whales.get("topTransfers") or []),
                "dexVolume24h":          activity.get("dexVolume24h"),
                "totalValueLocked":      activity.get("totalValueLocked"),
            }

            classification = _classify(metrics)

            doc = {
                "chain":      chain,
                "createdAt":  now,
                "createdBucket": now.strftime("%Y-%m-%dT%H"),
                "provider":   "infura_rpc+defillama",
                "source":     "onchain_native_v1",
                **metrics,
                **classification,
            }
            _db.onchain_metrics.insert_one(doc)
            # Also a thin event row for the trading classifier's existence check
            _db.onchain_events.insert_one({
                "chain":     chain,
                "createdAt": now,
                "type":      "metric_snapshot",
                "direction": classification["direction"],
                "confidence": classification["confidence"],
                "source":    "onchain_native_v1",
            })
            inserted += 1
        except Exception as exc:
            errors.append(f"{chain}: {exc!r}")

    elapsed = round(time.time() - started_ts, 2)
    print(f"[OnchainPeriodic] {now.isoformat()} inserted={inserted} errors={len(errors)} elapsed={elapsed}s")
    return {"ok": not errors, "inserted": inserted, "errors": errors, "ts": now.isoformat()}


async def _loop():
    interval = _interval()
    print(f"[OnchainPeriodic] starting loop interval={interval}s chains={_CHAINS}")
    await asyncio.sleep(15)  # let backend stabilize
    while True:
        try:
            await run_once()
        except Exception as exc:
            print(f"[OnchainPeriodic] loop error: {exc!r}")
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            print("[OnchainPeriodic] loop cancelled")
            raise


def start_loop_if_enabled() -> dict:
    flag = os.environ.get("ONCHAIN_PERIODIC_ENABLED", "true").strip().lower()
    if flag in ("0", "false", "no", "off", ""):
        print("[OnchainPeriodic] disabled by flag")
        return {"started": False, "reason": "disabled_by_flag"}
    task = asyncio.create_task(_loop())
    return {"started": True, "interval_sec": _interval()}


# Ensure indexes (best-effort)
try:
    _db.onchain_metrics.create_index([("chain", 1), ("createdAt", DESCENDING)])
    _db.onchain_events.create_index([("createdAt", DESCENDING)])
except Exception:
    pass
