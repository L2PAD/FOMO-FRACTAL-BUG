"""On-Chain Intelligence module — Mobile/MiniApp `/api/mobile/intel/onchain`.

Previous version used fake formulas like:
    netflow = -change7d * supply * 0.00001
    txCount = max(10, round(30 + change7d * 3))
    lthPct  = round(70 + change30d * 0.1, 0)

These were **derivations from price change**, not real on-chain data.
Replaced with real Infura RPC + DefiLlama signals.  Where Light Mode
cannot answer (e.g. address-labelled exchange netflow, long-term holder
ratio), we return `null` + honest `degraded: true` and let the UI
render '—' instead of fabricating a value.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


def _classify_state(net_inflow_usd, change7d):
    """ACCUMULATION/DISTRIBUTION/NEUTRAL from real bridge netflow ⊕
    7-day price change.  Both signals are real, no derivation."""
    if net_inflow_usd is None:
        # Light Mode without bridge data — derive only from price
        if change7d > 2:
            return "ACCUMULATION"
        if change7d < -2:
            return "DISTRIBUTION"
        return "NEUTRAL"
    if net_inflow_usd < 0 and change7d > 0:
        return "ACCUMULATION"  # bridge outflow + price up = accumulation
    if net_inflow_usd > 0 and change7d < 0:
        return "DISTRIBUTION"  # bridge inflow + price down = distribution
    return "NEUTRAL"


async def build_onchain_intel_async(features: dict) -> dict:
    """Real on-chain intel using onchain_lite (Infura) + DefiLlama."""
    key = features.get('asset', 'BTC')
    change7d = float(features.get('change7d', 0) or 0)

    # ── REAL on-chain pulls (parallel) ─────────────────────────────
    summary = whales = flows = activity = None
    try:
        from onchain_lite.service import (
            get_summary, get_whales, get_flows, get_activity,
        )
        summary, whales, flows, activity = await asyncio.gather(
            get_summary(chain="ethereum"),
            get_whales(chain="ethereum"),
            get_flows(chain="ethereum"),
            get_activity(chain="ethereum"),
            return_exceptions=True,
        )
    except Exception as e:  # service paused / disabled
        logger.warning("onchain_lite unavailable: %s", e)
        summary = whales = flows = activity = None

    def _safe(d):
        return d if isinstance(d, dict) else {}

    summary = _safe(summary)
    whales = _safe(whales)
    flows = _safe(flows)
    activity = _safe(activity)

    # ── Bridge net flow (REAL DefiLlama if available) ──────────────
    bridge_block = flows.get("bridge") or {}
    bridge_netflow_usd = bridge_block.get("netflowUsd")
    bridge_available = bridge_block.get("available", False)

    # ── Whales — REAL from Infura latest block ─────────────────────
    whale_count_block = whales.get("largeTransfersInBlock")
    whale_volume_block_usd = whales.get("totalWhaleVolumeBlock")
    whale_window = whales.get("windowType", "unavailable")
    whales_real = whale_count_block is not None

    # ── Network activity — REAL from Infura ────────────────────────
    block_height = summary.get("blockHeight")
    gas_price = summary.get("gasPrice")
    tps = summary.get("tps")
    pending = summary.get("pendingTxCount")
    network_real = block_height is not None

    # ── State classification (REAL bridge + price) ─────────────────
    state = _classify_state(bridge_netflow_usd, change7d)

    # ── Compose response (preserves UI contract) ────────────────────
    exchange_flows = {
        # netflow now in USD (bridge), not in BTC.  UI label still
        # works ("Exchange Netflow") — we honestly disclose the source.
        "netflow":   bridge_netflow_usd if bridge_available else None,
        "unit":      "usd",
        "trend":     (
            "outflow" if (bridge_netflow_usd is not None and bridge_netflow_usd < 0)
            else "inflow" if (bridge_netflow_usd is not None and bridge_netflow_usd > 0)
            else "unknown"
        ),
        "available": bridge_available,
        "source":    bridge_block.get("source") or "defillama_bridges_unavailable",
        "interpretation": (
            f"Bridge netflow on Ethereum: ${bridge_netflow_usd:,.0f} "
            f"({'outflow — accumulation behavior' if bridge_netflow_usd < 0 else 'inflow — potential sell pressure'})"
            if bridge_available and bridge_netflow_usd is not None
            else "Bridge data unavailable. CEX exchange netflow needs the indexer (address labels) — Light Mode cannot label."
        ),
    }

    whales_block = {
        "txCount":     whale_count_block if whales_real else None,
        "volumeUsd":   whale_volume_block_usd,
        "windowType":  whale_window,  # 'single_block' in Light Mode
        "trend":       "increasing" if whale_count_block and whale_count_block > 5 else "decreasing",
        "available":   whales_real,
        "source":      whales.get("provider", "unavailable"),
        "interpretation": (
            f"{whale_count_block} whale transfers (>$100K) in latest Ethereum block. "
            f"Run the indexer for a true 24h window."
            if whales_real and whale_count_block
            else f"No whale transfers (>$100K) detected in the latest block — quiet period."
            if whales_real
            else "Whale data unavailable — Infura connection issue."
        ),
    }

    # ── Stablecoin supply on chain (proxy for 'supply') ──────────────
    sc_block = flows.get("stablecoin") or {}
    sc_total_usd = sc_block.get("totalSupplyUsd") if sc_block.get("available") else None

    supply_block = {
        "stablecoinSupplyUsd": sc_total_usd,
        "available":  sc_block.get("available", False),
        "source":     sc_block.get("source", "unavailable"),
        # legacy fields — null in Light Mode (no address book = can't compute)
        "onExchangesPct": None,
        "deltaPct":       None,
        "interpretation": (
            f"Stablecoin supply on Ethereum: ${sc_total_usd:,.0f}. "
            f"Per-exchange supply ratio needs the indexer."
            if sc_total_usd
            else "Stablecoin supply data temporarily unavailable."
        ),
    }

    # ── Long-term holders — NOT POSSIBLE in Light Mode ──────────────
    holders_block = {
        "lthPct":     None,
        "trend":      "unavailable",
        "available":  False,
        "source":     "indexer_required",
        "interpretation": (
            "LTH cohort analysis requires UTXO age tracking — only available "
            "with the full indexer (mode=indexer).  Light Mode is honest "
            "about not knowing this."
        ),
    }

    # ── Network activity — REAL from Infura ─────────────────────────
    activity_block = {
        "blockHeight":          block_height,
        "gasPriceGwei":         gas_price,
        "tps":                  tps,
        "pendingTxCount":       pending,
        # legacy fields kept for UI compat — null since they need a
        # historic baseline that Light Mode doesn't index
        "activeAddressesPct":   None,
        "txPct":                None,
        "available":            network_real,
        "source":               summary.get("provider", "unavailable"),
        "interpretation": (
            f"Ethereum block #{block_height}, gas {gas_price} gwei, "
            f"{tps} TPS, {pending} pending tx. Live from Infura."
            if network_real
            else "Network data unavailable — Infura connection issue."
        ),
    }

    # ── Aggregated confidence (real-signals weight) ─────────────────
    signals_real = sum([
        bridge_available, whales_real, network_real,
        sc_block.get("available", False),
    ])
    # Confidence floor 0.3 if only price-derived; bonus per real signal
    confidence = round(0.3 + min(signals_real, 4) * 0.15, 2)

    interpretation_lines = []
    if network_real:
        interpretation_lines.append(
            f"Network healthy: block #{block_height}, {tps} TPS, {gas_price} gwei gas"
        )
    if whales_real and whale_count_block:
        interpretation_lines.append(
            f"{whale_count_block} whale tx (>$100K) in latest block"
        )
    if bridge_available and bridge_netflow_usd is not None:
        flow_word = "outflow" if bridge_netflow_usd < 0 else "inflow"
        interpretation_lines.append(
            f"Bridge {flow_word}: ${abs(bridge_netflow_usd):,.0f}"
        )
    if sc_total_usd:
        interpretation_lines.append(
            f"Stablecoin supply on Ethereum: ${sc_total_usd / 1e9:.1f}B"
        )
    interpretation_lines.append(f"7d price trend: {change7d:+.1f}%")
    if not interpretation_lines:
        interpretation_lines = ["On-chain data temporarily unavailable"]

    return {
        "asset":        key,
        "state":        state,
        "confidence":   confidence,
        "mode":         "light_mode_infura",  # explicit source label
        "exchangeFlows": exchange_flows,
        "whales":        whales_block,
        "supply":        supply_block,
        "holders":       holders_block,
        "activity":      activity_block,
        "interpretation": interpretation_lines,
        "signal": {
            "strength":  "STRONG" if signals_real >= 3 else "MODERATE" if signals_real >= 2 else "WEAK",
            "direction": "BULLISH" if state == "ACCUMULATION"
                         else "BEARISH" if state == "DISTRIBUTION" else "NEUTRAL",
        },
        "degraded": signals_real < 3,
    }


def build_onchain_intel(features: dict) -> dict:
    """Sync wrapper for compatibility with existing callers."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already inside an event loop → schedule and wait
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as ex:
                fut = ex.submit(asyncio.run, build_onchain_intel_async(features))
                return fut.result(timeout=15)
        return asyncio.run(build_onchain_intel_async(features))
    except Exception as e:
        logger.error("build_onchain_intel failed: %s", e)
        # Honest empty fallback — never fabricate
        return {
            'asset': features.get('asset', 'BTC'),
            'state': 'NEUTRAL',
            'confidence': 0.0,
            'mode': 'error',
            'error': str(e)[:120],
            'exchangeFlows': {'netflow': None, 'trend': 'unknown', 'available': False},
            'whales': {'txCount': None, 'trend': 'unknown', 'available': False},
            'supply': {'onExchangesPct': None, 'deltaPct': None, 'available': False},
            'holders': {'lthPct': None, 'trend': 'unknown', 'available': False},
            'activity': {'activeAddressesPct': None, 'txPct': None, 'available': False},
            'interpretation': ['On-chain pipeline error — try again shortly'],
            'signal': {'strength': 'WEAK', 'direction': 'NEUTRAL'},
            'degraded': True,
        }
