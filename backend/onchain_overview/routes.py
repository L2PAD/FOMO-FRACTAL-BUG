"""
On-Chain Overview Dashboard API v2
====================================
All endpoints support ?window=24h|7d|30d (default: 30d)

GET /api/onchain-overview/summary        — Network stats + 24h volume
GET /api/onchain-overview/entities       — Top entities by USD volume
GET /api/onchain-overview/exchange-flows — Exchange flows in USD
GET /api/onchain-overview/smart-money    — Smart money with labels & volume
GET /api/onchain-overview/token-flows    — Token distribution by USD volume
GET /api/onchain-overview/clusters       — Cluster activity with volume
GET /api/onchain-overview/transfers      — Largest individual transfers (NEW)
GET /api/onchain-overview/signals        — Human-readable signals
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from datetime import datetime, timezone, timedelta
import os, time

from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/api/onchain-overview", tags=["onchain-overview"])

_client = None


def _get_db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return _client[os.environ.get("DB_NAME", "intelligence_engine")]


def _ts_cutoff(window: str) -> int:
    hours = {"24h": 24, "7d": 168, "30d": 720}.get(window, 720)
    return int(time.time()) - hours * 3600


def _ser(doc):
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = [_ser(i) if isinstance(i, dict) else (i.isoformat() if isinstance(i, datetime) else i) for i in v]
        elif isinstance(v, dict):
            out[k] = _ser(v)
        else:
            out[k] = v
    return out


async def _get_eth_price(db) -> float:
    """Get ETH price from token_prices (use WETH as proxy)."""
    for tok in ["ETH", "WETH"]:
        doc = await db.token_prices.find_one({"token": tok}, {"_id": 0})
        if doc and doc.get("price_usd"):
            return doc["price_usd"]
    return 2100.0  # fallback


async def _get_price_map(db) -> dict:
    """Build token_symbol -> price_usd map."""
    prices = {}
    async for doc in db.token_prices.find({}, {"_id": 0}):
        prices[doc["token"]] = doc.get("price_usd", 0)
    # ETH alias
    if "ETH" not in prices and "WETH" in prices:
        prices["ETH"] = prices["WETH"]
    return prices


def _fmt_usd(v: float) -> str:
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 1e9:
        return f"{sign}${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}${a / 1e3:.1f}K"
    return f"{sign}${a:.0f}"


# ═══════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════

@router.get("/summary")
async def overview_summary(window: str = Query("30d")):
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        eth_price = await _get_eth_price(db)

        wallet_total = await db.wallet_registry.count_documents({})
        cluster_total = await db.wallet_clusters.count_documents({})
        smart_money_total = await db.wallet_scores.count_documents({})

        # Activity within window
        ea_count = await db.entity_activity.count_documents({"timestamp": {"$gte": cutoff}})
        tt_count = await db.token_transfers.count_documents({"timestamp": {"$gte": cutoff}})
        large_count = await db.entity_activity.count_documents({"value_eth": {"$gte": 10}, "timestamp": {"$gte": cutoff}})
        signals_count = await db.discovery_signals.count_documents({})

        # Volume in USD (entity_activity native + token_transfers ERC20)
        ea_vol_pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total_eth": {"$sum": "$value_eth"}}},
        ]
        ea_vol = 0
        async for doc in db.entity_activity.aggregate(ea_vol_pipeline):
            ea_vol = doc["total_eth"] * eth_price

        prices = await _get_price_map(db)
        tt_vol = 0
        async for doc in db.token_transfers.find({"timestamp": {"$gte": cutoff}}, {"_id": 0, "token_symbol": 1, "amount": 1}):
            p = prices.get(doc.get("token_symbol", ""), 0)
            tt_vol += doc.get("amount", 0) * p

        total_volume_usd = ea_vol + tt_vol

        # Wallet type breakdown
        type_pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        wallet_types = {}
        async for doc in db.wallet_registry.aggregate(type_pipeline):
            if doc["_id"]:
                wallet_types[doc["_id"]] = doc["count"]

        return JSONResponse(content={
            "ok": True,
            "active_wallets": wallet_total,
            "clusters_detected": cluster_total,
            "smart_money_wallets": smart_money_total,
            "large_transfers": large_count,
            "transfers_count": ea_count + tt_count,
            "volume_usd": round(total_volume_usd, 2),
            "volume_usd_fmt": _fmt_usd(total_volume_usd),
            "signals": signals_count,
            "wallet_types": wallet_types,
            "window": window,
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# TOP ENTITIES (USD volume)
# ═══════════════════════════════════════════

@router.get("/entities")
async def overview_entities(limit: int = Query(15), window: str = Query("30d")):
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        eth_price = await _get_eth_price(db)

        pipeline = [
            {"$match": {"entity": {"$ne": ""}, "timestamp": {"$gte": cutoff}}},
            {"$group": {
                "_id": "$entity",
                "tx_count": {"$sum": 1},
                "total_value_eth": {"$sum": "$value_eth"},
                "entity_type": {"$first": "$entity_type"},
                "last_seen": {"$max": "$timestamp"},
            }},
            {"$sort": {"total_value_eth": -1}},
            {"$limit": limit},
        ]
        entities = []
        # Preload address labels for wallet lookups
        entity_wallets = {}
        async for lbl in db.onchain_v2_address_labels.find(
            {"chainId": 1, "labelType": "EXCHANGE"},
            {"_id": 0, "address": 1, "name": 1}
        ):
            name = (lbl.get("name") or "").split(" ")[0]
            if name:
                if name not in entity_wallets:
                    entity_wallets[name] = []
                addr = lbl.get("address", "")
                if addr and len(entity_wallets[name]) < 5:
                    entity_wallets[name].append(addr.lower())

        async for doc in db.entity_activity.aggregate(pipeline):
            vol_usd = doc["total_value_eth"] * eth_price
            ent_name = doc["_id"]
            entities.append({
                "entity": ent_name,
                "tx_count": doc["tx_count"],
                "volume_usd": round(vol_usd, 2),
                "volume_usd_fmt": _fmt_usd(vol_usd),
                "entity_type": doc.get("entity_type", ""),
                "last_seen": doc.get("last_seen"),
                "wallet_addresses": entity_wallets.get(ent_name, [])[:5],
            })

        return JSONResponse(content={"ok": True, "entities": entities})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# EXCHANGE FLOWS (USD)
# ═══════════════════════════════════════════

@router.get("/exchange-flows")
async def overview_exchange_flows(window: str = Query("30d")):
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        eth_price = await _get_eth_price(db)

        # Inflows
        inflow_pipeline = [
            {"$match": {"entity_type": "exchange", "role": "receiver", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$entity", "inflow_eth": {"$sum": "$value_eth"}, "inflow_count": {"$sum": 1}}},
        ]
        inflows = {}
        async for doc in db.entity_activity.aggregate(inflow_pipeline):
            usd = doc["inflow_eth"] * eth_price
            inflows[doc["_id"]] = {"inflow_usd": round(usd, 2), "inflow_count": doc["inflow_count"]}

        # Outflows
        outflow_pipeline = [
            {"$match": {"entity_type": "exchange", "role": "sender", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$entity", "outflow_eth": {"$sum": "$value_eth"}, "outflow_count": {"$sum": 1}}},
        ]
        outflows = {}
        async for doc in db.entity_activity.aggregate(outflow_pipeline):
            usd = doc["outflow_eth"] * eth_price
            outflows[doc["_id"]] = {"outflow_usd": round(usd, 2), "outflow_count": doc["outflow_count"]}

        all_exchanges = set(list(inflows.keys()) + list(outflows.keys()))
        flows = []
        total_in = 0
        total_out = 0
        for ex in all_exchanges:
            inf = inflows.get(ex, {"inflow_usd": 0, "inflow_count": 0})
            out = outflows.get(ex, {"outflow_usd": 0, "outflow_count": 0})
            net = round(inf["inflow_usd"] - out["outflow_usd"], 2)
            total_in += inf["inflow_usd"]
            total_out += out["outflow_usd"]
            flows.append({
                "entity": ex,
                "inflow_usd": inf["inflow_usd"],
                "inflow_fmt": _fmt_usd(inf["inflow_usd"]),
                "outflow_usd": out["outflow_usd"],
                "outflow_fmt": _fmt_usd(out["outflow_usd"]),
                "net_usd": net,
                "net_fmt": _fmt_usd(net),
                "tx_count": inf["inflow_count"] + out["outflow_count"],
            })
        flows.sort(key=lambda x: abs(x["net_usd"]), reverse=True)

        return JSONResponse(content={
            "ok": True,
            "flows": flows,
            "totals": {
                "inflow_usd": round(total_in, 2),
                "inflow_fmt": _fmt_usd(total_in),
                "outflow_usd": round(total_out, 2),
                "outflow_fmt": _fmt_usd(total_out),
                "net_usd": round(total_in - total_out, 2),
                "net_fmt": _fmt_usd(total_in - total_out),
            },
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# SMART MONEY (human labels, volume, last activity)
# ═══════════════════════════════════════════

WALLET_TYPE_LABELS = {
    "exchange": "Exchange Wallet",
    "active_wallet": "Smart Money Wallet",
    "whale": "Whale",
    "bridge": "Bridge",
    "fund": "Fund Wallet",
    "protocol": "Protocol",
    "multi_exchange_user": "Multi-Exchange",
}

@router.get("/smart-money")
async def overview_smart_money(limit: int = Query(20), window: str = Query("30d")):
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        eth_price = await _get_eth_price(db)

        scores = await db.wallet_scores.find(
            {}, {"_id": 0}
        ).sort("smart_money_score", -1).limit(limit).to_list(limit)

        result = []
        for s in scores:
            addr = s["wallet"]

            # Registry info
            reg = await db.wallet_registry.find_one(
                {"address": addr}, {"_id": 0, "label": 1, "type": 1, "entity": 1}
            )
            wtype = reg.get("type", "active_wallet") if reg else "active_wallet"
            label = WALLET_TYPE_LABELS.get(wtype, "Wallet")
            entity = reg.get("entity", "") if reg else ""

            # Volume from entity_activity (counterparty)
            vol_pipeline = [
                {"$match": {"counterparty_addr": addr, "timestamp": {"$gte": cutoff}}},
                {"$group": {"_id": None, "vol": {"$sum": "$value_eth"}, "count": {"$sum": 1}, "last": {"$max": "$timestamp"}}},
            ]
            vol_usd = 0
            tx_count = 0
            last_ts = 0
            async for doc in db.entity_activity.aggregate(vol_pipeline):
                vol_usd = doc["vol"] * eth_price
                tx_count = doc["count"]
                last_ts = doc.get("last", 0)

            # Fallback: indexed_transactions
            if vol_usd == 0:
                it_pipeline = [
                    {"$match": {"$or": [{"from_addr": addr}, {"to_addr": addr}], "timestamp": {"$gte": cutoff}}},
                    {"$group": {"_id": None, "vol": {"$sum": "$value_eth"}, "count": {"$sum": 1}, "last": {"$max": "$timestamp"}}},
                ]
                async for doc in db.indexed_transactions.aggregate(it_pipeline):
                    vol_usd = doc["vol"] * eth_price
                    tx_count = doc["count"]
                    last_ts = doc.get("last", 0) or last_ts
            now = int(time.time())
            if last_ts > 0:
                diff = now - last_ts
                if diff < 3600:
                    last_ago = f"{diff // 60}m ago"
                elif diff < 86400:
                    last_ago = f"{diff // 3600}h ago"
                else:
                    last_ago = f"{diff // 86400}d ago"
            else:
                last_ago = ""

            if "updated_at" in s and isinstance(s["updated_at"], datetime):
                s["updated_at"] = s["updated_at"].isoformat()

            result.append({
                "wallet": addr,
                "score": s["smart_money_score"],
                "label": label,
                "entity": entity,
                "wallet_type": wtype,
                "volume_usd": round(vol_usd, 2),
                "volume_fmt": _fmt_usd(vol_usd),
                "tx_count": tx_count,
                "last_activity": last_ago,
                "interaction_score": s.get("interaction_score", 0),
                "early_entry": s.get("early_entry", 0),
                "dex_activity": s.get("dex_activity", 0),
            })

        return JSONResponse(content={"ok": True, "wallets": result, "count": len(result)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# TOKEN FLOWS (proper USD aggregation)
# ═══════════════════════════════════════════

@router.get("/token-flows")
async def overview_token_flows(window: str = Query("30d")):
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        prices = await _get_price_map(db)

        # ERC20 from token_transfers
        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {
                "_id": "$token_symbol",
                "transfer_count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"},
            }},
            {"$sort": {"total_amount": -1}},
            {"$limit": 15},
        ]
        tokens = []
        async for doc in db.token_transfers.aggregate(pipeline):
            sym = doc["_id"]
            p = prices.get(sym, 0)
            vol_usd = doc["total_amount"] * p
            tokens.append({
                "token": sym,
                "transfer_count": doc["transfer_count"],
                "volume_usd": round(vol_usd, 2),
                "volume_fmt": _fmt_usd(vol_usd),
                "price_usd": p,
            })

        # Native ETH from entity_activity
        eth_price = await _get_eth_price(db)
        ea_pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}, "value_eth": {"$gt": 0}}},
            {"$group": {
                "_id": None,
                "tx_count": {"$sum": 1},
                "total_eth": {"$sum": "$value_eth"},
            }},
        ]
        eth_entry = None
        async for doc in db.entity_activity.aggregate(ea_pipeline):
            vol = doc["total_eth"] * eth_price
            eth_entry = {
                "token": "ETH (native)",
                "transfer_count": doc["tx_count"],
                "volume_usd": round(vol, 2),
                "volume_fmt": _fmt_usd(vol),
                "price_usd": eth_price,
            }

        all_tokens = tokens[:]
        if eth_entry:
            all_tokens.append(eth_entry)
        all_tokens.sort(key=lambda x: x["volume_usd"], reverse=True)

        return JSONResponse(content={"ok": True, "tokens": all_tokens})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# CLUSTERS (with volume)
# ═══════════════════════════════════════════

@router.get("/clusters")
async def overview_clusters(limit: int = Query(15), window: str = Query("30d")):
    try:
        db = _get_db()
        eth_price = await _get_eth_price(db)

        clusters = await db.wallet_clusters.find(
            {}, {"_id": 0}
        ).sort("cluster_score", -1).limit(limit).to_list(limit)

        # Build human-readable names
        type_counters: dict = {}
        result = []
        for c in clusters:
            vol_usd = round(c.get("total_value_eth", 0) * eth_price, 2)
            wallets_list = c.get("wallets", [])
            ctype = c.get("cluster_type", "unknown")
            type_label = ctype.replace("_cluster", "").replace("_", " ").title()

            # Generate human name: "Fund Cluster #1", "Exchange Cluster #2"
            type_counters[ctype] = type_counters.get(ctype, 0) + 1
            human_name = f"{type_label} Cluster #{type_counters[ctype]}"

            result.append({
                "cluster_id": c.get("cluster_id"),
                "cluster_name": human_name,
                "cluster_type": ctype,
                "cluster_score": c.get("cluster_score", 0),
                "wallet_count": c.get("wallet_count", len(wallets_list)),
                "total_tx_count": c.get("total_tx_count", 0),
                "volume_usd": vol_usd,
                "volume_fmt": _fmt_usd(vol_usd),
                "wallets": wallets_list[:20],
            })

        return JSONResponse(content={"ok": True, "clusters": result, "count": len(result)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# LARGE TRANSFERS (NEW)
# ═══════════════════════════════════════════

@router.get("/transfers")
async def overview_transfers(limit: int = Query(15), window: str = Query("30d")):
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        prices = await _get_price_map(db)
        eth_price = await _get_eth_price(db)

        # ERC20 large transfers
        transfers_raw = await db.token_transfers.find(
            {"timestamp": {"$gte": cutoff}}, {"_id": 0}
        ).sort("amount", -1).limit(50).to_list(50)

        transfers = []
        for t in transfers_raw:
            sym = t.get("token_symbol", "")
            p = prices.get(sym, 0)
            usd = t.get("amount", 0) * p
            from_label = t.get("from_entity") or "Unknown"
            to_label = t.get("to_entity") or "Unknown"
            tx_type = t.get("tx_type", "transfer")

            # Friendly type
            type_label = {
                "exchange_deposit": "Deposit",
                "exchange_withdrawal": "Withdrawal",
                "whale_transfer": "Whale Transfer",
                "inter_exchange": "Inter-Exchange",
            }.get(tx_type, "Transfer")

            # Relative time
            ts = t.get("timestamp", 0)
            now = int(time.time())
            diff = now - ts if ts else 0
            if diff < 3600:
                ago = f"{max(diff // 60, 1)}m ago"
            elif diff < 86400:
                ago = f"{diff // 3600}h ago"
            else:
                ago = f"{diff // 86400}d ago"

            transfers.append({
                "token": sym,
                "amount": round(t.get("amount", 0), 2),
                "usd_value": round(usd, 2),
                "usd_fmt": _fmt_usd(usd),
                "from_label": from_label if from_label and from_label != "Unknown" else (f"{t.get('from_addr','')[:6]}...{t.get('from_addr','')[-4:]}" if len(t.get("from_addr","")) > 10 else from_label),
                "to_label": to_label if to_label and to_label != "Unknown" else (f"{t.get('to_addr','')[:6]}...{t.get('to_addr','')[-4:]}" if len(t.get("to_addr","")) > 10 else to_label),
                "from_addr": t.get("from_addr", ""),
                "to_addr": t.get("to_addr", ""),
                "tx_type": type_label,
                "chain": t.get("chain", ""),
                "time_ago": ago,
                "explorer_url": t.get("explorer_url", ""),
            })

        # Also include large native transfers from entity_activity
        ea_large = await db.entity_activity.find(
            {"value_eth": {"$gte": 10}, "timestamp": {"$gte": cutoff}},
            {"_id": 0}
        ).sort("value_eth", -1).limit(20).to_list(20)

        for e in ea_large:
            usd = e["value_eth"] * eth_price
            ts = e.get("timestamp", 0)
            now = int(time.time())
            diff = now - ts if ts else 0
            if diff < 3600:
                ago = f"{max(diff // 60, 1)}m ago"
            elif diff < 86400:
                ago = f"{diff // 3600}h ago"
            else:
                ago = f"{diff // 86400}d ago"

            is_recv = e.get("role") == "receiver"
            cp_addr = e.get("counterparty_addr", "")
            main_addr = e.get("address", "")
            cp_entity = e.get("counterparty_entity", "")
            main_entity = e.get("entity", "")

            from_entity = cp_entity if is_recv else main_entity
            to_entity = main_entity if is_recv else cp_entity
            from_a = cp_addr if is_recv else main_addr
            to_a = main_addr if is_recv else cp_addr

            transfers.append({
                "token": "ETH",
                "amount": round(e["value_eth"], 4),
                "usd_value": round(usd, 2),
                "usd_fmt": _fmt_usd(usd),
                "from_label": from_entity or (f"{from_a[:6]}...{from_a[-4:]}" if len(from_a) > 10 else "Unknown"),
                "to_label": to_entity or (f"{to_a[:6]}...{to_a[-4:]}" if len(to_a) > 10 else "Unknown"),
                "from_addr": from_a,
                "to_addr": to_a,
                "tx_type": e.get("tx_type", "Transfer").replace("_", " ").title(),
                "chain": e.get("chain", ""),
                "time_ago": ago,
                "explorer_url": e.get("explorer_url", ""),
            })

        # Sort by USD value
        transfers.sort(key=lambda x: x["usd_value"], reverse=True)

        return JSONResponse(content={"ok": True, "transfers": transfers[:limit]})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# SIGNALS (human-readable)
# ═══════════════════════════════════════════

@router.get("/signals")
async def overview_signals(limit: int = Query(20)):
    """Key Signals — multi-source intelligence signals computed from on-chain data."""
    try:
        db = _get_db()
        eth_price = await _get_eth_price(db)
        cutoff_30d = _ts_cutoff("30d")
        generated: list = []

        # ── 1. Exchange Flow Pressure Signal ──
        inflow_total = 0
        outflow_total = 0
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "role": "receiver", "timestamp": {"$gte": cutoff_30d}}},
            {"$group": {"_id": None, "total": {"$sum": "$value_eth"}}},
        ]):
            inflow_total = doc["total"]
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "role": "sender", "timestamp": {"$gte": cutoff_30d}}},
            {"$group": {"_id": None, "total": {"$sum": "$value_eth"}}},
        ]):
            outflow_total = doc["total"]

        net_flow = inflow_total - outflow_total
        net_usd = net_flow * eth_price
        if abs(net_flow) > 10:
            if net_flow > 0:
                severity = "EXTREME" if net_flow > 500 else "STRONG" if net_flow > 100 else "MODERATE"
                score = min(98, 60 + int(net_flow / 50))
                generated.append({
                    "id": "sig_exchange_inflow", "title": "Exchange Net Inflow Detected",
                    "description": f"Net {_fmt_usd(net_usd)} flowing into exchanges — potential selling pressure.",
                    "score": score, "severity": severity, "chain": "ethereum",
                    "signal_type": "CEX_INFLOW", "direction": "bearish",
                })
            else:
                severity = "EXTREME" if abs(net_flow) > 500 else "STRONG" if abs(net_flow) > 100 else "MODERATE"
                score = min(98, 60 + int(abs(net_flow) / 50))
                generated.append({
                    "id": "sig_exchange_outflow", "title": "Exchange Net Outflow Signal",
                    "description": f"Net {_fmt_usd(abs(net_usd))} leaving exchanges — accumulation signal.",
                    "score": score, "severity": severity, "chain": "ethereum",
                    "signal_type": "CEX_OUTFLOW", "direction": "bullish",
                })

        # ── 2. Top Exchange Dominance Signal ──
        top_exchanges = []
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "timestamp": {"$gte": cutoff_30d}}},
            {"$group": {"_id": "$entity", "vol_eth": {"$sum": "$value_eth"}}},
            {"$sort": {"vol_eth": -1}}, {"$limit": 1},
        ]):
            top_exchanges.append(doc)
        if top_exchanges:
            ex = top_exchanges[0]
            vol = ex["vol_eth"] * eth_price
            generated.append({
                "id": "sig_exchange_dominance", "title": f"{ex['_id']} Flow Dominance",
                "description": f"{ex['_id']} leads with {_fmt_usd(vol)} volume — dominant exchange activity.",
                "score": 75, "severity": "STRONG", "chain": "ethereum",
                "signal_type": "EXCHANGE_DOMINANCE", "direction": "neutral",
            })

        # ── 3. Smart Money Activity Level Signal ──
        sm_total = await db.wallet_scores.count_documents({})
        sm_high = await db.wallet_scores.count_documents({"smart_money_score": {"$gte": 0.4}})
        if sm_high > 0:
            ratio = sm_high / max(sm_total, 1)
            severity = "EXTREME" if ratio > 0.5 else "STRONG" if ratio > 0.3 else "MODERATE"
            generated.append({
                "id": "sig_smart_money", "title": "Smart Money Wallets Active",
                "description": f"{sm_high} high-score wallets detected out of {sm_total} tracked — institutional activity.",
                "score": min(95, 50 + sm_high * 2), "severity": severity, "chain": "ethereum",
                "signal_type": "SMART_MONEY_ACTIVITY", "direction": "bullish",
            })

        # ── 4. Cluster Coordination Signal ──
        active_clusters = await db.wallet_clusters.count_documents({"cluster_score": {"$gte": 0.3}})
        if active_clusters > 0:
            severity = "EXTREME" if active_clusters > 15 else "STRONG" if active_clusters > 5 else "MODERATE"
            generated.append({
                "id": "sig_cluster_coord", "title": "Cluster Coordination Detected",
                "description": f"{active_clusters} wallet clusters showing coordinated behavior patterns.",
                "score": min(95, 55 + active_clusters * 3), "severity": severity, "chain": "ethereum",
                "signal_type": "CLUSTER_COORDINATION", "direction": "neutral",
            })

        # ── 5. Large Transfer Alert ──
        largest = await db.entity_activity.find_one(
            {"value_eth": {"$gte": 10}, "timestamp": {"$gte": cutoff_30d}},
            {"_id": 0, "entity": 1, "value_eth": 1, "counterparty_entity": 1},
            sort=[("value_eth", -1)],
        )
        if largest:
            val = largest["value_eth"] * eth_price
            entity_name = largest.get("entity") or largest.get("counterparty_entity") or "Unknown"
            generated.append({
                "id": "sig_whale_transfer", "title": f"Whale Transfer — {entity_name}",
                "description": f"Large transfer of {_fmt_usd(val)} detected involving {entity_name}.",
                "score": min(96, 65 + int(largest["value_eth"] / 100)),
                "severity": "EXTREME" if largest["value_eth"] > 1000 else "STRONG",
                "chain": "ethereum",
                "signal_type": "WHALE_TRANSFER", "direction": "neutral",
            })

        # ── 6. Existing discovery_signals (cluster activity etc.) ──
        cluster_name_map = {}
        type_counters: dict = {}
        async for cl in db.wallet_clusters.find({}, {"_id": 0, "cluster_id": 1, "cluster_type": 1}).sort("cluster_score", -1):
            cid = cl.get("cluster_id", "")
            ctype = cl.get("cluster_type", "unknown")
            type_label = ctype.replace("_cluster", "").replace("_", " ").title()
            type_counters[ctype] = type_counters.get(ctype, 0) + 1
            cluster_name_map[cid] = f"{type_label} Cluster #{type_counters[ctype]}"

        discovery = await db.discovery_signals.find({}, {"_id": 0}).sort("score", -1).limit(limit).to_list(limit)
        for s in discovery:
            sig_type = s.get("signal_type", "")
            entity = s.get("entity", "")
            detail = s.get("detail", "")
            cluster_id = s.get("cluster_id", "")
            cluster_name = cluster_name_map.get(cluster_id, "")

            if sig_type == "CLUSTER_ACTIVITY":
                title = f"{cluster_name or 'Cluster'} Activity"
                wallet_count = s.get("wallet_count", 0)
                description = f"{cluster_name} — {wallet_count} wallets coordinating" if cluster_name else detail
            elif sig_type == "SMART_MONEY_ACCUMULATION":
                title = "Smart Money Accumulation"
                description = detail
            elif sig_type == "CEX_OUTFLOW":
                title = f"Exchange Outflow — {entity}"
                description = detail
            else:
                title = sig_type.replace("_", " ").title()
                description = detail

            display_entity = entity
            if entity and entity.startswith("Cluster ") and entity.replace("Cluster ", "") in cluster_name_map:
                display_entity = cluster_name_map[entity.replace("Cluster ", "")]

            generated.append(_ser({
                "id": s.get("id", ""),
                "title": title,
                "description": description or f"Activity for {display_entity}",
                "score": s.get("score", 0),
                "severity": s.get("severity", "MODERATE"),
                "chain": s.get("chain", ""),
                "signal_type": sig_type,
                "direction": s.get("direction", ""),
            }))

        # Sort by score descending, deduplicate by title, limit
        seen_titles = set()
        final = []
        for sig in sorted(generated, key=lambda x: x.get("score", 0), reverse=True):
            t = sig["title"]
            if t not in seen_titles:
                seen_titles.add(t)
                final.append(sig)
            if len(final) >= limit:
                break

        return JSONResponse(content={"ok": True, "signals": final, "count": len(final)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# MARKET CONTEXT ENGINE (NEW)
# ═══════════════════════════════════════════

@router.get("/context")
async def overview_context(window: str = Query("30d")):
    """Market Context — computed market status from on-chain data."""
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        eth_price = await _get_eth_price(db)

        # 1. Exchange Net Flow → Market Bias
        inflow_total = 0
        outflow_total = 0
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "role": "receiver", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total": {"$sum": "$value_eth"}}},
        ]):
            inflow_total = doc["total"]
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "role": "sender", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total": {"$sum": "$value_eth"}}},
        ]):
            outflow_total = doc["total"]

        net_flow = inflow_total - outflow_total
        net_flow_usd = net_flow * eth_price
        if abs(net_flow) < 10:
            bias = "Neutral"
        elif net_flow > 0:
            bias = "Selling Pressure" if net_flow > 100 else "Mild Sell"
        else:
            bias = "Accumulation" if abs(net_flow) > 100 else "Mild Buy"

        # 2. Liquidity Direction
        total_volume_eth = inflow_total + outflow_total
        if total_volume_eth > 5000:
            liquidity = "Expanding"
        elif total_volume_eth > 1000:
            liquidity = "Stable"
        else:
            liquidity = "Contracting"

        # 3. Exchange Pressure
        if inflow_total > 0 and outflow_total > 0:
            ratio = inflow_total / max(outflow_total, 0.01)
            if ratio > 1.5:
                exchange_pressure = "High"
            elif ratio > 1.1:
                exchange_pressure = "Moderate"
            elif ratio < 0.7:
                exchange_pressure = "Low (Outflow)"
            else:
                exchange_pressure = "Low"
        else:
            exchange_pressure = "Low"

        # 4. Smart Money Activity
        sm_count = await db.wallet_scores.count_documents({})
        high_score_count = await db.wallet_scores.count_documents({"smart_money_score": {"$gte": 0.4}})
        if high_score_count > 20:
            sm_activity = "Very Active"
        elif high_score_count > 10:
            sm_activity = "Active"
        elif high_score_count > 5:
            sm_activity = "Moderate"
        else:
            sm_activity = "Low"

        # 5. Cluster Activity
        active_clusters = await db.wallet_clusters.count_documents({"cluster_score": {"$gte": 0.3}})
        if active_clusters > 15:
            cluster_status = "High Activity"
        elif active_clusters > 5:
            cluster_status = "Moderate"
        else:
            cluster_status = "Low"

        # Signal severity distribution
        extreme_count = await db.discovery_signals.count_documents({"severity": "EXTREME"})
        strong_count = await db.discovery_signals.count_documents({"severity": "STRONG"})

        return JSONResponse(content={
            "ok": True,
            "market_bias": bias,
            "liquidity_direction": liquidity,
            "exchange_pressure": exchange_pressure,
            "smart_money_activity": sm_activity,
            "cluster_activity": cluster_status,
            "metrics": {
                "net_flow_usd": round(net_flow_usd, 2),
                "net_flow_fmt": _fmt_usd(net_flow_usd),
                "total_volume_eth": round(total_volume_eth, 2),
                "active_clusters": active_clusters,
                "high_score_wallets": high_score_count,
                "extreme_signals": extreme_count,
                "strong_signals": strong_count,
            },
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# MARKET STORY (narrative)
# ═══════════════════════════════════════════

@router.get("/story")
async def overview_story(window: str = Query("30d")):
    """Market Story — auto-generated narrative from on-chain signals."""
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        eth_price = await _get_eth_price(db)

        # Gather key data points
        # 1. Net exchange flow
        inflow_eth = 0
        outflow_eth = 0
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "role": "receiver", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total": {"$sum": "$value_eth"}}},
        ]):
            inflow_eth = doc["total"]
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "role": "sender", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total": {"$sum": "$value_eth"}}},
        ]):
            outflow_eth = doc["total"]

        net_flow = inflow_eth - outflow_eth
        net_usd = net_flow * eth_price

        # 2. Top exchange by net flow
        top_exchange_pipeline = [
            {"$match": {"entity_type": "exchange", "timestamp": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"entity": "$entity", "role": "$role"},
                "vol": {"$sum": "$value_eth"},
            }},
        ]
        ex_data = {}
        async for doc in db.entity_activity.aggregate(top_exchange_pipeline):
            ent = doc["_id"]["entity"]
            role = doc["_id"]["role"]
            if ent not in ex_data:
                ex_data[ent] = {"in": 0, "out": 0}
            if role == "receiver":
                ex_data[ent]["in"] = doc["vol"]
            else:
                ex_data[ent]["out"] = doc["vol"]

        top_inflow_ex = max(ex_data.items(), key=lambda x: x[1]["in"], default=("Unknown", {"in": 0}))
        top_outflow_ex = max(ex_data.items(), key=lambda x: x[1]["out"], default=("Unknown", {"out": 0}))

        # 3. Largest transfer
        largest = await db.entity_activity.find_one(
            {"timestamp": {"$gte": cutoff}},
            {"_id": 0, "entity": 1, "value_eth": 1, "role": 1},
            sort=[("value_eth", -1)],
        )

        # 4. Smart money count
        sm_active = await db.wallet_scores.count_documents({"smart_money_score": {"$gte": 0.35}})

        # 5. Active clusters
        active_clusters = await db.wallet_clusters.count_documents({"cluster_score": {"$gte": 0.3}})

        # Build story
        lines = []

        # Flow direction
        if net_flow > 50:
            lines.append(f"Net exchange inflow of {_fmt_usd(net_usd)} indicates selling pressure — funds are moving to exchanges.")
        elif net_flow < -50:
            lines.append(f"Net exchange outflow of {_fmt_usd(abs(net_usd))} suggests accumulation — funds are leaving exchanges.")
        else:
            lines.append("Exchange flows are balanced — no strong directional pressure detected.")

        # Top exchange
        if top_inflow_ex[1]["in"] > 100:
            lines.append(f"{top_inflow_ex[0]} leads inflow with {_fmt_usd(top_inflow_ex[1]['in'] * eth_price)}.")

        # Largest transfer
        if largest and largest["value_eth"] > 10:
            val = _fmt_usd(largest["value_eth"] * eth_price)
            lines.append(f"Largest single transfer: {val} ETH involving {largest.get('entity', 'unknown entity')}.")

        # Smart money
        if sm_active > 15:
            lines.append(f"{sm_active} smart money wallets are actively trading — high institutional activity.")
        elif sm_active > 5:
            lines.append(f"{sm_active} smart money wallets show moderate activity.")

        # Clusters
        if active_clusters > 10:
            lines.append(f"{active_clusters} wallet clusters detected with significant coordination patterns.")
        elif active_clusters > 3:
            lines.append(f"{active_clusters} active wallet clusters detected.")

        # Conclusion
        if net_flow < -50 and sm_active > 10:
            lines.append("Market posture: accumulation signals forming with active smart money.")
        elif net_flow > 50:
            lines.append("Market posture: distribution phase — monitor for potential corrections.")
        else:
            lines.append("Market posture: neutral consolidation with no dominant trend.")

        return JSONResponse(content={
            "ok": True,
            "story": " ".join(lines),
            "sentences": lines,
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# ACTIVITY TIMELINE (time-series buckets)
# ═══════════════════════════════════════════

@router.get("/timeline")
async def overview_timeline(window: str = Query("7d")):
    """Activity timeline — transfers, volume, signals bucketed by time."""
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        eth_price = await _get_eth_price(db)

        # Determine bucket size
        hours_map = {"24h": 24, "7d": 168, "30d": 720}
        total_hours = hours_map.get(window, 168)
        if total_hours <= 24:
            bucket_hours = 1
        elif total_hours <= 168:
            bucket_hours = 6
        else:
            bucket_hours = 24
        bucket_secs = bucket_hours * 3600
        now_ts = int(time.time())

        # Build empty buckets
        buckets = []
        t = cutoff
        while t < now_ts:
            buckets.append({
                "ts": t,
                "label": datetime.fromtimestamp(t, tz=timezone.utc).strftime("%m/%d %H:%M") if bucket_hours < 24
                         else datetime.fromtimestamp(t, tz=timezone.utc).strftime("%m/%d"),
                "transfers": 0,
                "volume_usd": 0.0,
                "signals": 0,
            })
            t += bucket_secs

        def bucket_idx(ts_val):
            idx = (ts_val - cutoff) // bucket_secs
            return max(0, min(idx, len(buckets) - 1))

        # Fill transfers + volume from entity_activity
        ea_pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"$subtract": ["$timestamp", {"$mod": ["$timestamp", bucket_secs]}]},
                "count": {"$sum": 1},
                "vol_eth": {"$sum": "$value_eth"},
            }},
        ]
        async for doc in db.entity_activity.aggregate(ea_pipeline):
            idx = bucket_idx(doc["_id"])
            if 0 <= idx < len(buckets):
                buckets[idx]["transfers"] += doc["count"]
                buckets[idx]["volume_usd"] += doc["vol_eth"] * eth_price

        # Fill transfers from token_transfers
        tt_pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"$subtract": ["$timestamp", {"$mod": ["$timestamp", bucket_secs]}]},
                "count": {"$sum": 1},
            }},
        ]
        async for doc in db.token_transfers.aggregate(tt_pipeline):
            idx = bucket_idx(doc["_id"])
            if 0 <= idx < len(buckets):
                buckets[idx]["transfers"] += doc["count"]

        # Fill signals from discovery_signals (use timestamp if available)
        async for sig in db.discovery_signals.find({}, {"_id": 0, "timestamp": 1}):
            ts = sig.get("timestamp")
            if isinstance(ts, datetime):
                ts = int(ts.timestamp())
            elif isinstance(ts, str):
                try:
                    ts = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
                except Exception:
                    continue
            if ts and ts >= cutoff:
                idx = bucket_idx(ts)
                if 0 <= idx < len(buckets):
                    buckets[idx]["signals"] += 1

        # Format volume + filter out empty buckets
        for b in buckets:
            b["volume_usd"] = round(b["volume_usd"], 2)
            b["volume_fmt"] = _fmt_usd(b["volume_usd"])

        # Only return buckets with data (sparse data looks empty otherwise)
        filled = [b for b in buckets if b["transfers"] > 0 or b["volume_usd"] > 0 or b["signals"] > 0]
        # If very few data points, keep all for context; otherwise filter
        result_buckets = filled if len(filled) >= 2 else buckets

        return JSONResponse(content={
            "ok": True,
            "buckets": result_buckets,
            "bucket_hours": bucket_hours,
            "window": window,
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# WHALE MONITOR
# ═══════════════════════════════════════════

@router.get("/whales")
async def overview_whales(window: str = Query("30d"), limit: int = Query(10)):
    """Whale Monitor — largest transactions, whale wallets, exchange deposits/withdrawals."""
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        eth_price = await _get_eth_price(db)
        prices = await _get_price_map(db)
        now_ts = int(time.time())

        def _ago(ts):
            if not ts:
                return ""
            diff = now_ts - ts
            if diff < 3600:
                return f"{max(diff // 60, 1)}m ago"
            if diff < 86400:
                return f"{diff // 3600}h ago"
            return f"{diff // 86400}d ago"

        # 1. Largest ETH transactions
        top_txs = []
        async for doc in db.entity_activity.find(
            {"value_eth": {"$gte": 1}, "timestamp": {"$gte": cutoff}},
            {"_id": 0}
        ).sort("value_eth", -1).limit(limit):
            usd = doc["value_eth"] * eth_price
            is_sender = doc.get("role") == "sender"
            from_addr = doc.get("address", "") if is_sender else doc.get("counterparty_addr", "")
            to_addr = doc.get("address", "") if not is_sender else doc.get("counterparty_addr", "")
            from_label = doc.get("entity", "") if is_sender else doc.get("counterparty_entity", "")
            to_label = doc.get("entity", "") if not is_sender else doc.get("counterparty_entity", "")
            top_txs.append({
                "token": "ETH",
                "amount_fmt": f"{doc['value_eth']:.2f} ETH",
                "usd_value": round(usd, 2),
                "usd_fmt": _fmt_usd(usd),
                "from_label": from_label or (f"{from_addr[:6]}...{from_addr[-4:]}" if len(from_addr) > 10 else "Unknown"),
                "to_label": to_label or (f"{to_addr[:6]}...{to_addr[-4:]}" if len(to_addr) > 10 else "Unknown"),
                "from_addr": from_addr,
                "to_addr": to_addr,
                "chain": doc.get("chain", "ethereum"),
                "time_ago": _ago(doc.get("timestamp")),
                "tx_type": doc.get("tx_type", "transfer"),
            })

        # Also include large ERC20 transfers
        async for doc in db.token_transfers.find(
            {"timestamp": {"$gte": cutoff}}, {"_id": 0}
        ).sort("amount", -1).limit(limit):
            sym = doc.get("token_symbol", "")
            p = prices.get(sym, 0)
            usd = doc.get("amount", 0) * p
            if usd < 1000:
                continue
            top_txs.append({
                "token": sym,
                "amount_fmt": f"{doc.get('amount', 0):,.2f} {sym}",
                "usd_value": round(usd, 2),
                "usd_fmt": _fmt_usd(usd),
                "from_label": doc.get("from_entity") or (f"{doc.get('from','')[:6]}...{doc.get('from','')[-4:]}" if len(doc.get("from","")) > 10 else "Unknown"),
                "to_label": doc.get("to_entity") or (f"{doc.get('to','')[:6]}...{doc.get('to','')[-4:]}" if len(doc.get("to","")) > 10 else "Unknown"),
                "from_addr": doc.get("from", ""),
                "to_addr": doc.get("to", ""),
                "chain": doc.get("chain", "ethereum"),
                "time_ago": _ago(doc.get("timestamp")),
                "tx_type": doc.get("tx_type", "transfer"),
            })

        top_txs.sort(key=lambda x: x["usd_value"], reverse=True)
        top_txs = top_txs[:limit]

        # 2. Top whale wallets (high value, non-exchange)
        whale_wallets = []
        async for doc in db.entity_activity.aggregate([
            {"$match": {"timestamp": {"$gte": cutoff}, "value_eth": {"$gte": 10}}},
            {"$group": {
                "_id": "$counterparty_addr",
                "total_eth": {"$sum": "$value_eth"},
                "tx_count": {"$sum": 1},
                "last_seen": {"$max": "$timestamp"},
                "entity": {"$first": "$counterparty_entity"},
            }},
            {"$match": {"_id": {"$ne": ""}}},
            {"$sort": {"total_eth": -1}},
            {"$limit": limit},
        ]):
            vol_usd = doc["total_eth"] * eth_price
            addr = doc["_id"] or ""
            whale_wallets.append({
                "address": addr,
                "short_addr": f"{addr[:6]}...{addr[-4:]}" if len(addr) > 10 else addr,
                "entity": doc.get("entity") or "",
                "volume_usd": round(vol_usd, 2),
                "volume_fmt": _fmt_usd(vol_usd),
                "tx_count": doc["tx_count"],
                "last_seen": _ago(doc.get("last_seen")),
            })

        # 3. Exchange deposits & withdrawals summary
        deposits = []
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "role": "receiver", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$entity", "total_eth": {"$sum": "$value_eth"}, "count": {"$sum": 1}}},
            {"$sort": {"total_eth": -1}},
            {"$limit": 5},
        ]):
            usd = doc["total_eth"] * eth_price
            deposits.append({"exchange": doc["_id"], "usd_fmt": _fmt_usd(usd), "usd_value": round(usd, 2), "count": doc["count"]})

        withdrawals = []
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "role": "sender", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$entity", "total_eth": {"$sum": "$value_eth"}, "count": {"$sum": 1}}},
            {"$sort": {"total_eth": -1}},
            {"$limit": 5},
        ]):
            usd = doc["total_eth"] * eth_price
            withdrawals.append({"exchange": doc["_id"], "usd_fmt": _fmt_usd(usd), "usd_value": round(usd, 2), "count": doc["count"]})

        return JSONResponse(content={
            "ok": True,
            "top_transactions": top_txs,
            "whale_wallets": whale_wallets,
            "deposits": deposits,
            "withdrawals": withdrawals,
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ═══════════════════════════════════════════
# LIQUIDITY RADAR
# ═══════════════════════════════════════════

@router.get("/radar")
async def overview_radar(window: str = Query("30d")):
    """Liquidity Radar — concentration by exchange, chain, token."""
    try:
        db = _get_db()
        cutoff = _ts_cutoff(window)
        eth_price = await _get_eth_price(db)
        prices = await _get_price_map(db)

        # 1. By Exchange (entity_activity)
        by_exchange = []
        async for doc in db.entity_activity.aggregate([
            {"$match": {"entity_type": "exchange", "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$entity", "vol_eth": {"$sum": "$value_eth"}, "tx_count": {"$sum": 1}}},
            {"$sort": {"vol_eth": -1}},
            {"$limit": 8},
        ]):
            usd = doc["vol_eth"] * eth_price
            by_exchange.append({"name": doc["_id"], "volume_usd": round(usd, 2), "volume_fmt": _fmt_usd(usd), "tx_count": doc["tx_count"]})

        total_exchange_usd = sum(e["volume_usd"] for e in by_exchange) or 1
        for e in by_exchange:
            e["share_pct"] = round(e["volume_usd"] / total_exchange_usd * 100, 1)

        # 2. By Chain (entity_activity + token_transfers)
        by_chain = {}
        async for doc in db.entity_activity.aggregate([
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$chain", "vol_eth": {"$sum": "$value_eth"}, "tx_count": {"$sum": 1}}},
        ]):
            ch = doc["_id"] or "ethereum"
            by_chain[ch] = {"volume_usd": doc["vol_eth"] * eth_price, "tx_count": doc["tx_count"]}

        async for doc in db.token_transfers.aggregate([
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$chain", "count": {"$sum": 1}}},
        ]):
            ch = doc["_id"] or "ethereum"
            if ch not in by_chain:
                by_chain[ch] = {"volume_usd": 0, "tx_count": 0}
            by_chain[ch]["tx_count"] += doc["count"]

        chains_list = []
        total_chain_usd = sum(v["volume_usd"] for v in by_chain.values()) or 1
        for ch, data in sorted(by_chain.items(), key=lambda x: x[1]["volume_usd"], reverse=True):
            chains_list.append({
                "chain": ch,
                "volume_usd": round(data["volume_usd"], 2),
                "volume_fmt": _fmt_usd(data["volume_usd"]),
                "tx_count": data["tx_count"],
                "share_pct": round(data["volume_usd"] / total_chain_usd * 100, 1),
            })

        # 3. By Token (token_transfers + native ETH)
        by_token = []
        async for doc in db.token_transfers.aggregate([
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$token_symbol", "total_amount": {"$sum": "$amount"}, "tx_count": {"$sum": 1}}},
            {"$sort": {"total_amount": -1}},
            {"$limit": 8},
        ]):
            sym = doc["_id"]
            p = prices.get(sym, 0)
            usd = doc["total_amount"] * p
            by_token.append({"token": sym, "volume_usd": round(usd, 2), "volume_fmt": _fmt_usd(usd), "tx_count": doc["tx_count"]})

        # Add native ETH
        ea_eth_pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}, "value_eth": {"$gt": 0}}},
            {"$group": {"_id": None, "total": {"$sum": "$value_eth"}, "count": {"$sum": 1}}},
        ]
        async for doc in db.entity_activity.aggregate(ea_eth_pipeline):
            usd = doc["total"] * eth_price
            by_token.append({"token": "ETH (native)", "volume_usd": round(usd, 2), "volume_fmt": _fmt_usd(usd), "tx_count": doc["count"]})

        by_token.sort(key=lambda x: x["volume_usd"], reverse=True)
        total_token_usd = sum(t["volume_usd"] for t in by_token) or 1
        for t in by_token:
            t["share_pct"] = round(t["volume_usd"] / total_token_usd * 100, 1)

        return JSONResponse(content={
            "ok": True,
            "by_exchange": by_exchange,
            "by_chain": chains_list,
            "by_token": by_token[:8],
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
