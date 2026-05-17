"""
Entity Signal Enrichment
========================
Generates on-chain signals from entity_activity and indexed_transactions.
Produces standardized signals with: chain, tx_hash, from_entity, to_entity,
tx_type, drivers, cluster_score, signal_strength.

Pipeline: entity_activity → classify → score → signal
"""

import os
import hashlib
import time
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

from .drivers import (
    CEX_INFLOW, CEX_OUTFLOW, EXCHANGE_REBALANCE,
    WHALE_TRANSFER, WHALE_ACCUMULATION, WHALE_DISTRIBUTION,
    FUND_ACTIVITY, MM_ACTIVITY, SMART_MONEY_FLOW,
    CLUSTER_ACTIVITY, ENTITY_SPIKE, CROSS_EXCHANGE_FLOW,
    CHAIN_EXPLORERS, CHAIN_LABELS,
)

_client = None
ALLOWED_CHAINS = {"ethereum", "arbitrum", "optimism", "base"}

# Thresholds
WHALE_THRESHOLD_ETH = 10.0
SIGNIFICANT_THRESHOLD_ETH = 1.0
ENTITY_SPIKE_THRESHOLD = 5  # tx in 10 min window


def _get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGO_URL"])
    return _client[os.environ.get("DB_NAME", "intelligence_engine")]


def _get_token_price(db, symbol: str) -> float:
    """Get cached USD price for a token symbol."""
    try:
        price_doc = db.token_prices.find_one({"token": symbol}, {"_id": 0, "price_usd": 1})
        return price_doc.get("price_usd", 0) if price_doc else 0
    except Exception:
        return 0


def _get_wallet_label(db, addr: str) -> dict:
    """Get wallet label and score from discovery collections."""
    try:
        reg = db.wallet_registry.find_one({"address": addr.lower()}, {"_id": 0, "label": 1, "type": 1, "entity": 1})
        score_doc = db.wallet_scores.find_one({"wallet": addr.lower()}, {"_id": 0, "smart_money_score": 1})
        cluster_doc = db.wallet_clusters.find_one({"wallets": addr.lower()}, {"_id": 0, "cluster_id": 1, "cluster_type": 1})
        return {
            "wallet_label": reg.get("label", "") if reg else "",
            "wallet_type": reg.get("type", "") if reg else "",
            "smart_money_score": score_doc.get("smart_money_score", 0) if score_doc else 0,
            "cluster_id": cluster_doc.get("cluster_id", "") if cluster_doc else "",
            "cluster_type": cluster_doc.get("cluster_type", "") if cluster_doc else "",
        }
    except Exception:
        return {"wallet_label": "", "wallet_type": "", "smart_money_score": 0, "cluster_id": "", "cluster_type": ""}


def _signal_id(prefix: str, chain: str, detail: str) -> str:
    raw = f"entity_{prefix}_{chain}_{detail}"
    return "esig_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _severity(score: int) -> str:
    if score >= 75:
        return "EXTREME"
    if score >= 60:
        return "STRONG"
    if score >= 40:
        return "WATCH"
    return "WEAK"


def _explorer_tx(chain: str, tx_hash: str) -> str:
    base = CHAIN_EXPLORERS.get(chain, "https://etherscan.io")
    return f"{base}/tx/{tx_hash}" if tx_hash else ""


def _explorer_addr(chain: str, addr: str) -> str:
    base = CHAIN_EXPLORERS.get(chain, "https://etherscan.io")
    return f"{base}/address/{addr}" if addr else ""


def _cluster_score(tx_count: int, total_value: float, time_density: float) -> float:
    """
    cluster_score = 0.4 * normalized_tx_size + 0.3 * entity_activity + 0.3 * cluster_density
    """
    norm_value = min(total_value / 1000, 1.0)  # normalize to 1000 ETH
    norm_count = min(tx_count / 20, 1.0)  # normalize to 20 tx
    return round(0.4 * norm_value + 0.3 * norm_count + 0.3 * time_density, 3)


def generate_entity_signals(chain_filter: str = None, lookback_minutes: int = 1440) -> list:
    """
    Generate on-chain entity signals from recent entity_activity.
    Returns standardized signal list compatible with signals_v3.
    """
    db = _get_db()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=lookback_minutes)
    cutoff_iso = cutoff.isoformat()

    signals = []

    # Query entity activity from the lookback window (use indexed_at ISO string)
    query = {"indexed_at": {"$gte": cutoff_iso}}
    if chain_filter and chain_filter in ALLOWED_CHAINS:
        query["chain"] = chain_filter

    # Aggregate by entity + chain
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": {"entity": "$entity", "chain": "$chain", "entity_type": "$entity_type"},
            "tx_count": {"$sum": 1},
            "total_value": {"$sum": "$value_eth"},
            "deposit_count": {"$sum": {"$cond": [{"$eq": ["$role", "receiver"]}, 1, 0]}},
            "withdrawal_count": {"$sum": {"$cond": [{"$eq": ["$role", "sender"]}, 1, 0]}},
            "deposit_value": {"$sum": {"$cond": [{"$eq": ["$role", "receiver"]}, "$value_eth", 0]}},
            "withdrawal_value": {"$sum": {"$cond": [{"$eq": ["$role", "sender"]}, "$value_eth", 0]}},
            "last_tx": {"$last": "$tx_hash"},
            "last_counterparty": {"$last": "$counterparty_addr"},
            "last_counterparty_entity": {"$last": "$counterparty_entity"},
            "last_timestamp": {"$max": "$timestamp"},
            "first_timestamp": {"$min": "$timestamp"},
        }},
        {"$sort": {"total_value": -1}},
        {"$limit": 30},
    ]

    entity_aggs = list(db.entity_activity.aggregate(pipeline))

    for agg in entity_aggs:
        entity_name = agg["_id"]["entity"]
        chain = agg["_id"]["chain"]
        entity_type = agg["_id"]["entity_type"]

        if not entity_name or chain not in ALLOWED_CHAINS:
            continue

        tx_count = agg["tx_count"]
        total_value = agg["total_value"]
        deposit_count = agg["deposit_count"]
        withdrawal_count = agg["withdrawal_count"]
        deposit_value = agg["deposit_value"]
        withdrawal_value = agg["withdrawal_value"]

        # Skip insignificant activity
        if total_value < SIGNIFICANT_THRESHOLD_ETH and tx_count < 3:
            continue

        # Calculate time density (tx per minute in window)
        time_span = max(agg.get("last_timestamp", 0) - agg.get("first_timestamp", 0), 1)
        time_density = min(tx_count / max(time_span / 60, 1), 1.0)

        cs = _cluster_score(tx_count, total_value, time_density)
        chain_label = CHAIN_LABELS.get(chain, "ETH")
        explorer_tx = _explorer_tx(chain, agg.get("last_tx", ""))
        last_counterparty = agg.get("last_counterparty", "")
        last_cp_entity = agg.get("last_counterparty_entity", "")

        # ─── Classify and create signal ───

        if entity_type == "exchange":
            # Exchange-specific signals
            net_flow = deposit_value - withdrawal_value

            if withdrawal_value > deposit_value and withdrawal_value >= WHALE_THRESHOLD_ETH:
                # Major exchange outflow = bullish
                score = min(round(
                    30 + withdrawal_value / 100 * 20 + tx_count * 2 + cs * 30
                ), 95)
                drivers_list = [CEX_OUTFLOW]
                if tx_count >= ENTITY_SPIKE_THRESHOLD:
                    drivers_list.append(ENTITY_SPIKE)

                signals.append(_build_signal(
                    sig_type="CEX_OUTFLOW",
                    entity=entity_name, chain=chain, chain_label=chain_label,
                    direction="BULLISH",
                    score=score, cs=cs,
                    tx_hash=agg.get("last_tx", ""),
                    from_entity=entity_name, to_entity=last_cp_entity or "Unknown",
                    from_addr="", to_addr=last_counterparty,
                    entity_type=entity_type,
                    tx_type="exchange_withdrawal",
                    drivers=drivers_list,
                    amount=withdrawal_value,
                    tx_count=tx_count,
                    detail=f"{entity_name} outflow: {withdrawal_value:.1f} ETH ({withdrawal_count} tx) on {chain_label}",
                    explorer_url=explorer_tx,
                ))

            elif deposit_value > withdrawal_value and deposit_value >= WHALE_THRESHOLD_ETH:
                # Major exchange inflow = bearish
                score = min(round(
                    30 + deposit_value / 100 * 20 + tx_count * 2 + cs * 30
                ), 95)
                drivers_list = [CEX_INFLOW]
                if tx_count >= ENTITY_SPIKE_THRESHOLD:
                    drivers_list.append(ENTITY_SPIKE)

                signals.append(_build_signal(
                    sig_type="CEX_INFLOW",
                    entity=entity_name, chain=chain, chain_label=chain_label,
                    direction="BEARISH",
                    score=score, cs=cs,
                    tx_hash=agg.get("last_tx", ""),
                    from_entity=last_cp_entity or "Unknown", to_entity=entity_name,
                    from_addr=last_counterparty, to_addr="",
                    entity_type=entity_type,
                    tx_type="exchange_deposit",
                    drivers=drivers_list,
                    amount=deposit_value,
                    tx_count=tx_count,
                    detail=f"{entity_name} inflow: {deposit_value:.1f} ETH ({deposit_count} tx) on {chain_label}",
                    explorer_url=explorer_tx,
                ))

            elif tx_count >= ENTITY_SPIKE_THRESHOLD:
                # Exchange activity spike
                score = min(round(25 + tx_count * 3 + cs * 20), 80)
                signals.append(_build_signal(
                    sig_type="EXCHANGE_ACTIVITY",
                    entity=entity_name, chain=chain, chain_label=chain_label,
                    direction="NEUTRAL",
                    score=score, cs=cs,
                    tx_hash=agg.get("last_tx", ""),
                    from_entity=entity_name, to_entity="",
                    from_addr="", to_addr="",
                    entity_type=entity_type,
                    tx_type="exchange_rebalance",
                    drivers=[EXCHANGE_REBALANCE, ENTITY_SPIKE],
                    amount=total_value,
                    tx_count=tx_count,
                    detail=f"{entity_name} activity spike: {tx_count} tx ({total_value:.1f} ETH) on {chain_label}",
                    explorer_url=explorer_tx,
                ))

        elif entity_type in ("fund", "vc"):
            # Fund activity = smart money
            score = min(round(40 + total_value / 50 * 20 + cs * 30), 95)
            direction = "BULLISH" if withdrawal_count > deposit_count else "BEARISH"
            drivers_list = [FUND_ACTIVITY, SMART_MONEY_FLOW]

            signals.append(_build_signal(
                sig_type="SMART_MONEY_ACTIVITY",
                entity=entity_name, chain=chain, chain_label=chain_label,
                direction=direction,
                score=score, cs=cs,
                tx_hash=agg.get("last_tx", ""),
                from_entity=entity_name if withdrawal_count > deposit_count else last_cp_entity or "Unknown",
                to_entity=last_cp_entity or "Unknown" if withdrawal_count > deposit_count else entity_name,
                from_addr="", to_addr=last_counterparty,
                entity_type=entity_type,
                tx_type="fund_activity",
                drivers=drivers_list,
                amount=total_value,
                tx_count=tx_count,
                detail=f"{entity_name} activity: {total_value:.1f} ETH ({tx_count} tx) on {chain_label}",
                explorer_url=explorer_tx,
            ))

        elif entity_type == "market_maker":
            # Market maker activity
            score = min(round(35 + total_value / 50 * 15 + cs * 25), 90)
            signals.append(_build_signal(
                sig_type="MM_ACTIVITY",
                entity=entity_name, chain=chain, chain_label=chain_label,
                direction="NEUTRAL",
                score=score, cs=cs,
                tx_hash=agg.get("last_tx", ""),
                from_entity=entity_name, to_entity=last_cp_entity or "Unknown",
                from_addr="", to_addr=last_counterparty,
                entity_type=entity_type,
                tx_type="mm_activity",
                drivers=[MM_ACTIVITY],
                amount=total_value,
                tx_count=tx_count,
                detail=f"{entity_name}: {total_value:.1f} ETH ({tx_count} tx) on {chain_label}",
                explorer_url=explorer_tx,
            ))

    # ─── Whale signals from large unknown transfers ───
    whale_pipeline = [
        {"$match": {
            "indexed_at": {"$gte": cutoff_iso},
            "from_entity": "",
            "to_entity": "",
            "value_eth": {"$gte": WHALE_THRESHOLD_ETH},
            **({"chain": chain_filter} if chain_filter and chain_filter in ALLOWED_CHAINS else {}),
        }},
        {"$sort": {"value_eth": -1}},
        {"$limit": 10},
    ]
    whale_txs = list(db.indexed_transactions.aggregate(whale_pipeline))

    for wtx in whale_txs:
        chain = wtx.get("chain", "ethereum")
        value = wtx.get("value_eth", 0)
        chain_label = CHAIN_LABELS.get(chain, "ETH")
        tx_hash = wtx.get("hash", "")
        from_addr = wtx.get("from_addr", "")
        to_addr = wtx.get("to_addr", "")

        score = min(round(30 + value / 100 * 30), 90)
        signals.append(_build_signal(
            sig_type="WHALE_TRANSFER",
            entity=f"Whale ({from_addr[:8]}...)",
            chain=chain, chain_label=chain_label,
            direction="NEUTRAL",
            score=score, cs=0.5,
            tx_hash=tx_hash,
            from_entity="", to_entity="",
            from_addr=from_addr, to_addr=to_addr,
            entity_type="whale",
            tx_type="whale_transfer",
            drivers=[WHALE_TRANSFER],
            amount=value,
            tx_count=1,
            detail=f"Whale transfer: {value:.1f} ETH ({from_addr[:10]}... → {to_addr[:10]}...) on {chain_label}",
            explorer_url=_explorer_tx(chain, tx_hash),
        ))

    # ─── Token Transfer Signals (ERC20 large movements) ───
    token_pipeline = [
        {"$match": {
            "indexed_at": {"$gte": cutoff_iso},
            "amount": {"$gt": 0},
            **({"chain": chain_filter} if chain_filter and chain_filter in ALLOWED_CHAINS else {}),
        }},
        {"$group": {
            "_id": {"token_symbol": "$token_symbol", "chain": "$chain", "from_entity": "$from_entity", "to_entity": "$to_entity"},
            "tx_count": {"$sum": 1},
            "total_amount": {"$sum": "$amount"},
            "last_tx": {"$last": "$tx_hash"},
            "last_from": {"$last": "$from_addr"},
            "last_to": {"$last": "$to_addr"},
        }},
        {"$sort": {"total_amount": -1}},
        {"$limit": 20},
    ]

    try:
        token_aggs = list(db.token_transfers.aggregate(token_pipeline))
    except Exception:
        token_aggs = []

    for tagg in token_aggs:
        token_sym = tagg["_id"]["token_symbol"]
        chain = tagg["_id"]["chain"]
        from_ent = tagg["_id"].get("from_entity", "")
        to_ent = tagg["_id"].get("to_entity", "")
        total_amt = tagg["total_amount"]
        tx_count = tagg["tx_count"]
        chain_label = CHAIN_LABELS.get(chain, "ETH")
        tx_hash = tagg.get("last_tx", "")

        entity = from_ent or to_ent or f"Wallet ({tagg.get('last_from', '')[:8]}...)"
        entity_type = "exchange" if any(e in (from_ent + to_ent).lower() for e in ["binance", "coinbase", "okx", "bybit", "kraken", "gate"]) else "whale"

        # Format amount for display
        if total_amt >= 1_000_000:
            amt_str = f"{total_amt / 1_000_000:.1f}M {token_sym}"
        elif total_amt >= 1_000:
            amt_str = f"{total_amt / 1_000:.1f}k {token_sym}"
        else:
            amt_str = f"{total_amt:.1f} {token_sym}"

        # Determine signal type
        if from_ent and "exchange" in entity_type.lower():
            sig_type = "CEX_OUTFLOW"
            direction = "BULLISH"
            drivers = [CEX_OUTFLOW]
        elif to_ent and "exchange" in entity_type.lower():
            sig_type = "CEX_INFLOW"
            direction = "BEARISH"
            drivers = [CEX_INFLOW]
        else:
            sig_type = "TOKEN_TRANSFER"
            direction = "NEUTRAL"
            drivers = [WHALE_TRANSFER]

        score = min(round(40 + total_amt / 100_000 * 20 + tx_count * 2), 95)

        signals.append(_build_signal(
            sig_type=sig_type,
            entity=entity, chain=chain, chain_label=chain_label,
            direction=direction,
            score=score, cs=0.5,
            tx_hash=tx_hash,
            from_entity=from_ent, to_entity=to_ent,
            from_addr=tagg.get("last_from", ""), to_addr=tagg.get("last_to", ""),
            entity_type=entity_type,
            tx_type="token_transfer",
            drivers=drivers,
            amount=0,
            tx_count=tx_count,
            detail=f"{amt_str} ({tx_count} tx) on {chain_label}: {from_ent or '?'} → {to_ent or '?'}",
            explorer_url=_explorer_tx(chain, tx_hash),
            token_symbol=token_sym,
            token_amount=total_amt,
        ))

    # Sort by score
    signals.sort(key=lambda s: s["score"], reverse=True)
    return signals


def _build_signal(
    sig_type: str, entity: str, chain: str, chain_label: str,
    direction: str, score: int, cs: float,
    tx_hash: str, from_entity: str, to_entity: str,
    from_addr: str, to_addr: str,
    entity_type: str, tx_type: str,
    drivers: list, amount: float, tx_count: int,
    detail: str, explorer_url: str,
    token_symbol: str = "ETH", token_amount: float = 0,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    asset = token_symbol if token_symbol != "ETH" else "ETH"
    display_amount = token_amount if token_amount > 0 else amount
    db = _get_db()

    # Enrich with token price
    usd_value = 0
    if display_amount > 0:
        if token_symbol == "ETH":
            eth_price = _get_token_price(db, "WETH") or _get_token_price(db, "ETH")
            usd_value = round(display_amount * eth_price, 2) if eth_price else 0
        else:
            token_price = _get_token_price(db, token_symbol)
            usd_value = round(display_amount * token_price, 2) if token_price else 0

    # Enrich with wallet discovery data
    primary_addr = from_addr or to_addr
    wallet_info = _get_wallet_label(db, primary_addr) if primary_addr else {}

    return {
        "id": _signal_id(sig_type, chain, entity + tx_hash[:8]),
        "signal_type": sig_type,
        "source": "entity_intelligence",
        "asset": asset,
        "chain": chain,
        "chain_label": chain_label,
        "direction": direction,
        "score": score,
        "confidence": min(score + 10, 100),
        "severity": _severity(score),
        "status": "confirmed" if score >= 60 else "forming",
        "timeframe": "1-4h",
        "expected_move": "",
        "cluster_score": round(cs * 100),
        # ─── Entity fields ───
        "entity": entity,
        "entity_type": entity_type,
        "from_entity": from_entity,
        "to_entity": to_entity,
        "from_addr": from_addr,
        "to_addr": to_addr,
        "tx_hash": tx_hash,
        "tx_type": tx_type,
        "amount_eth": round(amount, 4),
        "token_symbol": token_symbol,
        "token_amount": round(display_amount, 4),
        "usd_value": usd_value,
        "tx_count": tx_count,
        # ─── Discovery fields ───
        "wallet_label": wallet_info.get("wallet_label", ""),
        "wallet_type": wallet_info.get("wallet_type", ""),
        "smart_money_score": wallet_info.get("smart_money_score", 0),
        "cluster_id": wallet_info.get("cluster_id", ""),
        "cluster_type": wallet_info.get("cluster_type", ""),
        # ─── Drivers ───
        "drivers": drivers,
        "driver_labels": [d.replace("_", " ").title() for d in drivers],
        # ─── Links ───
        "explorer_url": explorer_url,
        "explorer_from": _explorer_addr(chain, from_addr) if from_addr else "",
        "explorer_to": _explorer_addr(chain, to_addr) if to_addr else "",
        # ─── Meta ───
        "detail": detail,
        "timestamp": now,
        "age_min": 0,
        "freshness": 1.0,
        # ─── Standard signal fields ───
        "target": "",
        "risk": "MODERATE",
        "invalidation": {"type": "entity_reversal", "description": f"{entity} activity reversal", "level": ""},
        "alignment": {"engine_regime": "neutral_chop", "signal_direction": direction.lower(), "status": "neutral"},
        "quality": {"success_rate": 0, "avg_move": 0, "samples": 0},
        "provenance": {
            "source": "entity_intelligence",
            "detection": sig_type.lower(),
            "module": "entity_signal_enrichment",
        },
        "evidence": {
            "wallet": from_addr or to_addr,
            "tx_hash": tx_hash,
            "contract": "",
            "chain": chain,
            "explorer_url": explorer_url,
            "wallet_link": _explorer_addr(chain, from_addr or to_addr) if (from_addr or to_addr) else "",
            "tx_link": explorer_url,
        },
    }
