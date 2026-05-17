"""
CEX Intelligence Engine — v2.0
================================
Exchange Market Intelligence: pressure, stablecoin power, inventory,
largest transfers, smart wallet warnings, pump/dump setup.

Reads directly from MongoDB collections:
- onchain_v2_erc20_logs
- onchain_v2_address_labels
- onchain_v2_token_prices
- token_registry
- cex_entities
"""

import os
import time
from typing import Optional
from pymongo import MongoClient, DESCENDING

_client: Optional[MongoClient] = None
_cache: dict = {}
CACHE_TTL = 120  # 2 min


def get_db():
    """Stage A-3: explicit DB resolution.

    Previously this used `_client.get_default_database()`, which requires
    the DB name encoded in the connection URI.  Our MONGO_URL is bare
    (`mongodb://localhost:27017`) so the call raised
    'No default database defined' every tick.  Resolving via DB_NAME env
    var with a safe fallback matches the rest of the app.
    """
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
    return _client[os.environ.get("DB_NAME", "test_database")]


def cache_get(k):
    e = _cache.get(k)
    if e and time.time() - e[1] < CACHE_TTL:
        return e[0]
    return None


def cache_set(k, v):
    _cache[k] = (v, time.time())


# ── Stablecoin addresses ──
STABLES = {
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", 6, 1.0),
    "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", 6, 1.0),
    "0x6b175474e89094c44da98b954eedeac495271d0f": ("DAI", 18, 1.0),
}


def _load_prices(db) -> dict:
    """Load token prices: address -> (symbol, decimals, usd_price)"""
    prices = {}
    for doc in db["onchain_v2_token_prices"].find({}):
        addr = str(doc.get("token") or doc.get("address") or "").lower()
        if addr:
            prices[addr] = (doc.get("symbol", ""), doc.get("decimals", 18), doc.get("priceUsd", 0))

    for doc in db["token_registry"].find({}):
        addr = str(doc.get("address", "")).lower()
        if addr and addr not in prices:
            prices[addr] = (doc.get("symbol", "UNKNOWN"), doc.get("decimals", 18), doc.get("priceUsd", 0))

    for addr, (sym, dec, px) in STABLES.items():
        if addr not in prices:
            prices[addr] = (sym, dec, px)
        elif not prices[addr][2]:
            prices[addr] = (prices[addr][0] or sym, prices[addr][1], px)

    return prices


def _parse_value(raw, decimals: int) -> float:
    if not raw:
        return 0
    s = str(raw)
    try:
        if len(s) <= 15:
            return int(s) / (10 ** decimals)
        if len(s) <= decimals:
            return float("0." + s.zfill(decimals))
        return float(s[:len(s) - decimals] + "." + s[len(s) - decimals:])
    except (ValueError, OverflowError):
        return 0


def _fmt_usd(n: float) -> str:
    a = abs(n)
    if a >= 1e9:
        return f"${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"${a / 1e3:.1f}K"
    return f"${a:.0f}"


def get_cex_context(chain_id: int = 1, window: str = "7d") -> dict:
    ck = f"cex_ctx:{chain_id}:{window}"
    cached = cache_get(ck)
    if cached:
        return cached

    db = get_db()
    prices = _load_prices(db)

    # 1. Load exchange addresses
    labels = list(db["onchain_v2_address_labels"].find(
        {"chainId": chain_id, "labelType": "EXCHANGE"}
    ))
    exchange_addrs = {}  # addr -> {entityId, name, addressType}
    entity_names = {}    # entityId -> entityName
    entity_addr_sets = {}  # entityId -> set(addrs) for internal filter

    for lab in labels:
        addr = str(lab.get("address", "")).lower()
        eid = str(lab.get("entityId", ""))
        if not addr or not eid:
            continue
        exchange_addrs[addr] = {
            "entityId": eid,
            "name": lab.get("name", eid),
            "addressType": lab.get("addressType", "unknown"),
        }
        entity_names[eid] = lab.get("name", eid).split(" ")[0]
        if eid not in entity_addr_sets:
            entity_addr_sets[eid] = set()
        entity_addr_sets[eid].add(addr)

    # Also load entity names from cex_entities
    for ent in db["cex_entities"].find({}):
        eid = ent.get("entityId", "")
        if eid:
            entity_names[eid] = ent.get("entityName", eid)

    all_addrs = list(exchange_addrs.keys())

    # 2. Time window
    window_ms = {"24h": 86400_000, "7d": 604800_000, "30d": 2592000_000}.get(window, 604800_000)
    cutoff = int(time.time() * 1000) - window_ms

    # 3. Query ERC20 logs
    in_logs = list(db["onchain_v2_erc20_logs"].find(
        {"to": {"$in": all_addrs}, "indexedAt": {"$gte": cutoff}}
    ))
    out_logs = list(db["onchain_v2_erc20_logs"].find(
        {"from": {"$in": all_addrs}, "indexedAt": {"$gte": cutoff}}
    ))

    # 4. Aggregate per exchange
    exchange_data = {}  # entityId -> {in_usd, out_usd, tx_count, tokens_in, tokens_out}

    def get_ex(eid):
        if eid not in exchange_data:
            exchange_data[eid] = {
                "entityId": eid,
                "entityName": entity_names.get(eid, eid),
                "inflow_usd": 0, "outflow_usd": 0, "tx_count": 0,
                "tokens_in": {}, "tokens_out": {},
                "largest_in": [], "largest_out": [],
            }
        return exchange_data[eid]

    # Stablecoin tracker
    stable_inflow = {"USDT": 0, "USDC": 0, "DAI": 0}
    stable_outflow = {"USDT": 0, "USDC": 0, "DAI": 0}

    # Largest transfers
    all_transfers = []

    # Process IN logs (deposits to exchanges)
    for log in in_logs:
        to_addr = str(log.get("to", "")).lower()
        from_addr = str(log.get("from", "")).lower()
        ex_info = exchange_addrs.get(to_addr)
        if not ex_info:
            continue
        eid = ex_info["entityId"]
        # Internal filter
        if from_addr in (entity_addr_sets.get(eid) or set()):
            continue
        token_addr = str(log.get("tokenAddress", "")).lower()
        px_info = prices.get(token_addr)
        if not px_info:
            continue
        sym, dec, px = px_info
        amount = _parse_value(log.get("value", "0"), dec)
        usd = amount * px
        if usd <= 0 or not (0 < usd < 1e15):
            continue

        ex = get_ex(eid)
        ex["inflow_usd"] += usd
        ex["tx_count"] += 1
        ex["tokens_in"][sym] = ex["tokens_in"].get(sym, 0) + usd

        if sym in stable_inflow:
            stable_inflow[sym] += usd

        all_transfers.append({
            "direction": "deposit",
            "token": sym, "usd": usd,
            "exchange": entity_names.get(eid, eid),
            "from": from_addr, "to": to_addr,
            "token_address": token_addr,
            "tx_hash": str(log.get("transactionHash", "")),
        })

    # Process OUT logs (withdrawals from exchanges)
    for log in out_logs:
        from_addr = str(log.get("from", "")).lower()
        to_addr = str(log.get("to", "")).lower()
        ex_info = exchange_addrs.get(from_addr)
        if not ex_info:
            continue
        eid = ex_info["entityId"]
        if to_addr in (entity_addr_sets.get(eid) or set()):
            continue
        token_addr = str(log.get("tokenAddress", "")).lower()
        px_info = prices.get(token_addr)
        if not px_info:
            continue
        sym, dec, px = px_info
        amount = _parse_value(log.get("value", "0"), dec)
        usd = amount * px
        if usd <= 0 or not (0 < usd < 1e15):
            continue

        ex = get_ex(eid)
        ex["outflow_usd"] += usd
        ex["tx_count"] += 1
        ex["tokens_out"][sym] = ex["tokens_out"].get(sym, 0) + usd

        if sym in stable_outflow:
            stable_outflow[sym] += usd

        all_transfers.append({
            "direction": "withdrawal",
            "token": sym, "usd": usd,
            "exchange": entity_names.get(eid, eid),
            "from": from_addr, "to": to_addr,
            "token_address": token_addr,
            "tx_hash": str(log.get("transactionHash", "")),
        })

    # 5. Compute aggregates
    total_inflow = sum(e["inflow_usd"] for e in exchange_data.values())
    total_outflow = sum(e["outflow_usd"] for e in exchange_data.values())
    net_flow = total_inflow - total_outflow
    total_volume = total_inflow + total_outflow

    # Separate stablecoin vs token deposits for liquidity map
    stable_addrs = set(STABLES.keys())
    token_deposits = 0  # non-stablecoin deposits (sell supply)
    for t in all_transfers:
        if t["direction"] == "deposit":
            tok_addr = t.get("token_address", "")
            if tok_addr not in stable_addrs:
                token_deposits += t["usd"]

    # Market bias
    if total_outflow > total_inflow * 1.2:
        market_bias = "bullish"
    elif total_inflow > total_outflow * 1.2:
        market_bias = "bearish"
    else:
        market_bias = "neutral"

    # ── Hero: Drivers & Offsetting Factors ──
    hero_drivers = []
    offsetting = []

    if total_inflow > total_outflow:
        hero_drivers.append("Exchange deposits exceed withdrawals")
    elif total_outflow > total_inflow:
        hero_drivers.append("Exchange withdrawals exceed deposits")

    # Find dominant exchange
    dom_ex = max(exchange_data.values(), key=lambda e: e["inflow_usd"] + e["outflow_usd"]) if exchange_data else None
    if dom_ex:
        dom_vol = dom_ex["inflow_usd"] + dom_ex["outflow_usd"]
        dom_share = (dom_vol / total_volume * 100) if total_volume > 0 else 0
        if dom_share > 40:
            hero_drivers.append(f"{dom_ex['entityName']} dominates exchange flow ({dom_share:.0f}%)")

    total_stable_in_all = sum(stable_inflow.values())
    total_stable_out_all = sum(stable_outflow.values())

    if total_stable_in_all > total_stable_out_all * 1.3:
        if market_bias == "bearish":
            offsetting.append("Stablecoin inflow remains positive")
        else:
            hero_drivers.append(f"Stablecoin inflow +{_fmt_usd(total_stable_in_all)}")
    elif total_stable_out_all > total_stable_in_all * 1.3:
        if market_bias == "bullish":
            offsetting.append("Stablecoin outflow rising")
        else:
            hero_drivers.append("Stablecoin capital leaving exchanges")

    # Check if any major token has opposite flow
    for ex in exchange_data.values():
        for tok, amt in ex.get("tokens_out", {}).items():
            if tok and tok not in ("USDT", "USDC", "DAI") and amt > total_outflow * 0.2:
                offsetting.append(f"{tok} withdrawals rising")
                break
        if offsetting and len(offsetting) >= 2:
            break

    # ── Hero: 3 Indicators ──
    sell_pressure_pct = min(100, int((total_inflow / max(total_volume, 1)) * 100))
    liquidity_pct = min(100, int((total_stable_in_all / max(total_volume, 1)) * 100))
    active_exchanges = sum(1 for e in exchange_data.values() if e["tx_count"] > 0)
    conf_pct = min(100, max(10, int(min(active_exchanges / 5, 1) * 40 + min(total_volume / 100000, 1) * 40 + min(len(all_transfers) / 100, 1) * 20)))

    # Collect top transactions per exchange
    exchange_top_txs = {}  # entityId -> list of top tx
    for t in sorted(all_transfers, key=lambda x: x["usd"], reverse=True):
        ex_name = t["exchange"]
        if ex_name not in exchange_top_txs:
            exchange_top_txs[ex_name] = []
        if len(exchange_top_txs[ex_name]) < 3:
            exchange_top_txs[ex_name].append({
                "direction": t["direction"],
                "token": t["token"],
                "usd_fmt": _fmt_usd(t["usd"]),
                "from_address": t.get("from", ""),
                "to_address": t.get("to", ""),
                "tx_hash": t.get("tx_hash", ""),
            })

    # Top exchange flows (sorted by absolute net) — with behavior labels
    exchanges_sorted = sorted(exchange_data.values(), key=lambda e: abs(e["inflow_usd"] - e["outflow_usd"]), reverse=True)
    top_exchanges = []
    for ex in exchanges_sorted[:10]:
        net = ex["inflow_usd"] - ex["outflow_usd"]
        ex_vol = ex["inflow_usd"] + ex["outflow_usd"]
        mkt_share = (ex_vol / total_volume * 100) if total_volume > 0 else 0

        # Dominant direction
        if ex["inflow_usd"] > ex["outflow_usd"] * 1.3:
            dominant_dir = "Deposits dominant"
        elif ex["outflow_usd"] > ex["inflow_usd"] * 1.3:
            dominant_dir = "Withdrawals dominant"
        else:
            dominant_dir = "Balanced"

        # Behavior label
        if ex["inflow_usd"] > ex["outflow_usd"] * 1.5:
            behavior = "Distribution"
        elif ex["outflow_usd"] > ex["inflow_usd"] * 1.5:
            behavior = "Accumulation"
        elif abs(net) < ex_vol * 0.1 and ex["tx_count"] > 20:
            behavior = "Inventory Rebalance"
        else:
            behavior = "Neutral"

        top_exchanges.append({
            "entityId": ex["entityId"],
            "entityName": ex["entityName"],
            "inflow_usd": round(ex["inflow_usd"], 2),
            "outflow_usd": round(ex["outflow_usd"], 2),
            "net_usd": round(net, 2),
            "net_fmt": ("+" if net >= 0 else "") + _fmt_usd(net),
            "tx_count": ex["tx_count"],
            "market_share": round(mkt_share, 1),
            "dominant_direction": dominant_dir,
            "behavior_label": behavior,
            "top_tokens_in": sorted(ex["tokens_in"].items(), key=lambda x: x[1], reverse=True)[:3],
            "top_tokens_out": sorted(ex["tokens_out"].items(), key=lambda x: x[1], reverse=True)[:3],
            "top_transactions": exchange_top_txs.get(ex["entityName"], []),
            "wallet_addresses": sorted(entity_addr_sets.get(ex["entityId"], set()))[:5],
        })

    # Stablecoin power
    total_stable_in = total_stable_in_all
    total_stable_out = total_stable_out_all
    stablecoin_power = {
        "usdt_in": round(stable_inflow["USDT"], 2),
        "usdc_in": round(stable_inflow["USDC"], 2),
        "dai_in": round(stable_inflow["DAI"], 2),
        "total_in": round(total_stable_in, 2),
        "usdt_out": round(stable_outflow["USDT"], 2),
        "usdc_out": round(stable_outflow["USDC"], 2),
        "dai_out": round(stable_outflow["DAI"], 2),
        "total_out": round(total_stable_out, 2),
        "net_power": round(total_stable_in - total_stable_out, 2),
        "bias": "buying_power" if total_stable_in > total_stable_out else "selling_power",
    }

    # ── Top wallets per stablecoin ──
    _swv = {"USDT": {}, "USDC": {}, "DAI": {}}
    for t in all_transfers:
        if t["token"] in _swv:
            w = t.get("from", "") if t["direction"] == "deposit" else t.get("to", "")
            if w and w not in exchange_addrs:
                _swv[t["token"]][w] = _swv[t["token"]].get(w, 0) + t["usd"]
    for sym in ("USDT", "USDC", "DAI"):
        stablecoin_power[f"{sym.lower()}_top_wallets"] = [
            {"wallet": w, "usd_fmt": _fmt_usd(v)}
            for w, v in sorted(_swv[sym].items(), key=lambda x: x[1], reverse=True)[:5]
        ]

    # Largest transfers — with impact labels + significance (Sprint A)
    largest = sorted(all_transfers, key=lambda t: t["usd"], reverse=True)[:10]
    largest_clean = []
    for t in largest:
        tok = t["token"] if t["token"] else "ERC20"
        is_stable = tok in ("USDT", "USDC", "DAI")
        if t["direction"] == "deposit":
            if is_stable:
                impact = "BUY LIQUIDITY"
            else:
                impact = "SELL PRESSURE"
        else:  # withdrawal
            if is_stable:
                impact = "CAPITAL EXIT"
            else:
                impact = "ACCUMULATION"
        # Significance based on % of total volume
        vol_share = (t["usd"] / max(total_volume, 1)) * 100
        if vol_share >= 5:
            significance = "HIGH"
        elif vol_share >= 1:
            significance = "MEDIUM"
        else:
            significance = "LOW"
        largest_clean.append({
            "direction": t["direction"],
            "token": tok,
            "usd": round(t["usd"], 2),
            "usd_fmt": _fmt_usd(t["usd"]),
            "exchange": t["exchange"],
            "impact_label": impact,
            "significance": significance,
            "volume_share": round(vol_share, 1),
            "from_address": t.get("from", ""),
            "to_address": t.get("to", ""),
            "tx_hash": t.get("tx_hash", ""),
        })

    # Exchange rotation (exchange -> exchange transfers)
    # Detect when a withdrawal from one exchange goes to deposit at another
    out_by_to = {}
    for log in out_logs:
        to_addr = str(log.get("to", "")).lower()
        if to_addr in exchange_addrs:
            from_addr = str(log.get("from", "")).lower()
            from_ex = exchange_addrs.get(from_addr)
            to_ex = exchange_addrs.get(to_addr)
            if from_ex and to_ex and from_ex["entityId"] != to_ex["entityId"]:
                token_addr = str(log.get("tokenAddress", "")).lower()
                px_info = prices.get(token_addr)
                if px_info:
                    sym, dec, px = px_info
                    amount = _parse_value(log.get("value", "0"), dec)
                    usd = amount * px
                    if usd > 0:
                        key = f"{from_ex['entityId']}|{to_ex['entityId']}"
                        if key not in out_by_to:
                            out_by_to[key] = {
                                "from_exchange": entity_names.get(from_ex["entityId"], from_ex["entityId"]),
                                "to_exchange": entity_names.get(to_ex["entityId"], to_ex["entityId"]),
                                "total_usd": 0, "count": 0, "tokens": {},
                            }
                        out_by_to[key]["total_usd"] += usd
                        out_by_to[key]["count"] += 1
                        out_by_to[key]["tokens"][sym] = out_by_to[key]["tokens"].get(sym, 0) + usd

    exchange_rotation = sorted(out_by_to.values(), key=lambda r: r["total_usd"], reverse=True)[:5]
    for r in exchange_rotation:
        r["total_usd"] = round(r["total_usd"], 2)
        r["total_fmt"] = _fmt_usd(r["total_usd"])
        r["top_token"] = max(r["tokens"].items(), key=lambda x: x[1])[0] if r["tokens"] else ""
        del r["tokens"]

    # Rotation fallback: if no rotation in current window, check 30d
    rotation_fallback = []
    if not exchange_rotation and window != "30d":
        fallback_ms = 2592000_000  # 30d
        fallback_cutoff = int(time.time() * 1000) - fallback_ms
        fb_out = list(db["onchain_v2_erc20_logs"].find(
            {"from": {"$in": all_addrs}, "indexedAt": {"$gte": fallback_cutoff}},
        ).limit(5000))
        fb_rot = {}
        for log in fb_out:
            to_a = str(log.get("to", "")).lower()
            from_a = str(log.get("from", "")).lower()
            if to_a in exchange_addrs:
                fe = exchange_addrs.get(from_a)
                te = exchange_addrs.get(to_a)
                if fe and te and fe["entityId"] != te["entityId"]:
                    ta = str(log.get("tokenAddress", "")).lower()
                    pi = prices.get(ta)
                    if pi:
                        s, d, p = pi
                        a = _parse_value(log.get("value", "0"), d)
                        u = a * p
                        if u > 0:
                            k = f"{fe['entityId']}|{te['entityId']}"
                            if k not in fb_rot:
                                fb_rot[k] = {
                                    "from_exchange": entity_names.get(fe["entityId"], fe["entityId"]),
                                    "to_exchange": entity_names.get(te["entityId"], te["entityId"]),
                                    "total_usd": 0, "top_token": s, "count": 0,
                                }
                            fb_rot[k]["total_usd"] += u
                            fb_rot[k]["count"] += 1
        rotation_fallback = sorted(fb_rot.values(), key=lambda r: r["total_usd"], reverse=True)[:3]
        for r in rotation_fallback:
            r["total_usd"] = round(r["total_usd"], 2)
            r["total_fmt"] = _fmt_usd(r["total_usd"])
            r["time_ago"] = "30d"

    # 6. Pump/Dump setup (rule-based)
    # Use smart money data from token intelligence
    try:
        from smart_money_radar.brain import get_brain_signals
        from smart_money_radar.narrative import get_narrative
        brain = get_brain_signals(chain_id=chain_id, window=window, limit=10)
        get_narrative(chain_id=chain_id, window=window)
    except Exception:
        brain = []

    # Compute setup scores per token
    pump_setups = []
    for token_score in brain[:5]:
        tok = token_score["token"]
        alpha = token_score["alpha_score"]
        signal = token_score["signal"]
        timing = token_score.get("avg_timing", 0)
        net_flow_sm = token_score.get("net_flow_usd", 0)

        # Exchange supply score: if token is being withdrawn → bullish
        tok_deposits = sum(ex.get("tokens_in", {}).get(tok, 0) for ex in exchange_data.values())
        tok_withdrawals = sum(ex.get("tokens_out", {}).get(tok, 0) for ex in exchange_data.values())
        supply_score = 50
        if tok_withdrawals > tok_deposits * 1.5:
            supply_score = 80
        elif tok_withdrawals > tok_deposits:
            supply_score = 65
        elif tok_deposits > tok_withdrawals * 1.5:
            supply_score = 20
        elif tok_deposits > tok_withdrawals:
            supply_score = 35

        # Smart flow score
        smart_flow_score = min(100, max(0, alpha))

        # Stablecoin score
        stable_score = 50
        if total_stable_in > total_stable_out * 1.5:
            stable_score = 80
        elif total_stable_in > total_stable_out:
            stable_score = 65

        # Timing score
        timing_score = min(100, max(0, timing * 10))

        # Regime score
        regime_score = 50
        if signal in ("strong_bullish", "bullish"):
            regime_score = 80
        elif signal in ("strong_bearish", "bearish"):
            regime_score = 20

        pump_pct = int(
            smart_flow_score * 0.25 +
            supply_score * 0.20 +
            stable_score * 0.15 +
            timing_score * 0.15 +
            regime_score * 0.15 +
            50 * 0.10  # absorption placeholder
        )
        dump_pct = max(5, 100 - pump_pct)

        drivers = []
        if smart_flow_score >= 60:
            drivers.append(f"Smart flow {'+' if net_flow_sm >= 0 else ''}{_fmt_usd(net_flow_sm)}")
        if supply_score >= 65:
            drivers.append("Exchange withdrawals dominate")
        elif supply_score <= 35:
            drivers.append("Exchange deposits rising")
        if stable_score >= 65:
            drivers.append(f"Stablecoin power {_fmt_usd(total_stable_in)}")
        if timing_score >= 50:
            drivers.append(f"Lead time +{timing:.1f}h")
        if regime_score >= 65:
            drivers.append(f"Signal: {signal}")
        elif regime_score <= 35:
            drivers.append(f"Distribution signal: {signal}")

        # Confidence band (Sprint A): +-spread based on data quality
        component_variance = max(abs(smart_flow_score - 50), abs(supply_score - 50), abs(regime_score - 50))
        if active_exchanges >= 5 and len(all_transfers) >= 50:
            conf_spread = max(5, int(component_variance * 0.15))
            conf_level = "high"
        elif active_exchanges >= 3 and len(all_transfers) >= 20:
            conf_spread = max(8, int(component_variance * 0.25))
            conf_level = "moderate"
        else:
            conf_spread = max(12, int(component_variance * 0.35))
            conf_level = "low"

        # Top transactions for this token (fall back to overall if no match)
        pump_txs = []
        for t in sorted(all_transfers, key=lambda x: x["usd"], reverse=True):
            if t["token"] == tok and len(pump_txs) < 3:
                pump_txs.append({
                    "direction": t["direction"],
                    "usd_fmt": _fmt_usd(t["usd"]),
                    "from_address": t.get("from", ""),
                    "to_address": t.get("to", ""),
                    "tx_hash": t.get("tx_hash", ""),
                    "exchange": t["exchange"],
                })
        # If no token-specific txs, use overall top ones
        if not pump_txs:
            for t in sorted(all_transfers, key=lambda x: x["usd"], reverse=True)[:3]:
                pump_txs.append({
                    "direction": t["direction"],
                    "token": t["token"],
                    "usd_fmt": _fmt_usd(t["usd"]),
                    "from_address": t.get("from", ""),
                    "to_address": t.get("to", ""),
                    "tx_hash": t.get("tx_hash", ""),
                    "exchange": t["exchange"],
                })

        pump_setups.append({
            "token": tok,
            "pump_probability": min(95, pump_pct),
            "dump_risk": min(95, dump_pct),
            "drivers": drivers[:5],
            "confidence_band": {
                "low": max(5, min(95, pump_pct - conf_spread)),
                "high": max(5, min(95, pump_pct + conf_spread)),
                "spread": conf_spread,
                "level": conf_level,
            },
            "components": {
                "smart_flow": smart_flow_score,
                "exchange_supply": supply_score,
                "stablecoin": stable_score,
                "timing": timing_score,
                "regime": regime_score,
            },
            "top_transactions": pump_txs,
        })

    # Confidence
    confidence = "high" if total_inflow + total_outflow > 10000 else "moderate" if total_inflow + total_outflow > 1000 else "low"

    # ── Hero: Dominant Venue & Dominant Asset (Sprint A Polish) ──
    hero_dominant_venue = None
    if dom_ex:
        dom_vol = dom_ex["inflow_usd"] + dom_ex["outflow_usd"]
        dom_share_h = (dom_vol / total_volume * 100) if total_volume > 0 else 0
        dom_net = dom_ex["inflow_usd"] - dom_ex["outflow_usd"]
        hero_dominant_venue = {
            "exchange": dom_ex["entityName"],
            "volume_fmt": _fmt_usd(dom_vol),
            "share": round(dom_share_h, 1),
            "net_fmt": ("+" if dom_net >= 0 else "") + _fmt_usd(dom_net),
            "bias": "sell_pressure" if dom_net > 0 else "accumulation" if dom_net < 0 else "neutral",
        }

    # Dominant asset by volume
    all_token_volumes = {}
    _token_deps = {}
    _token_withs = {}
    for t in all_transfers:
        tok = t["token"] or "ERC20"
        if tok in ("USDT", "USDC", "DAI"):
            continue
        all_token_volumes[tok] = all_token_volumes.get(tok, 0) + t["usd"]
        if t["direction"] == "deposit":
            _token_deps[tok] = _token_deps.get(tok, 0) + t["usd"]
        else:
            _token_withs[tok] = _token_withs.get(tok, 0) + t["usd"]
    hero_dominant_asset = None
    if all_token_volumes:
        top_tok = max(all_token_volumes.items(), key=lambda x: x[1])
        tok_deps = _token_deps.get(top_tok[0], 0)
        tok_withs = _token_withs.get(top_tok[0], 0)
        tok_net = tok_deps - tok_withs
        hero_dominant_asset = {
            "token": top_tok[0],
            "volume_fmt": _fmt_usd(top_tok[1]),
            "share": round((top_tok[1] / max(total_volume, 1)) * 100, 1),
            "net_fmt": ("+" if tok_net >= 0 else "") + _fmt_usd(tok_net),
            "bias": "sell_pressure" if tok_net > 0 else "accumulation" if tok_net < 0 else "neutral",
        }

    # Build narrative
    narrative_lines = []
    if market_bias == "bullish":
        narrative_lines.append("Exchange withdrawals exceed deposits — bullish liquidity signal.")
    elif market_bias == "bearish":
        narrative_lines.append("Exchange deposits exceed withdrawals — potential sell pressure building.")
    else:
        narrative_lines.append("Exchange flows balanced — neutral market pressure.")

    if total_stable_in > total_stable_out:
        narrative_lines.append(f"Stablecoin inflows of {_fmt_usd(total_stable_in)} suggest fresh buying power entering exchanges.")
    elif total_stable_out > total_stable_in:
        narrative_lines.append(f"Stablecoin outflows of {_fmt_usd(total_stable_out)} — capital leaving exchange environment.")

    if exchange_rotation:
        r = exchange_rotation[0]
        narrative_lines.append(f"Inter-exchange rotation detected: {r['from_exchange']} → {r['to_exchange']} ({r['total_fmt']}).")

    active_exchanges_final = sum(1 for e in exchange_data.values() if e["tx_count"] > 0)
    narrative_lines.append(f"{active_exchanges_final} exchanges active with {len(in_logs) + len(out_logs)} total transfers.")

    # ── Market Liquidity Map ──
    buy_power = total_stable_in  # stablecoin inflow = buy power
    sell_supply = token_deposits  # non-stablecoin deposits = sell supply
    net_liq = buy_power - sell_supply
    liq_bias = "bullish" if net_liq > 0 else "bearish"
    # Interpretation text (Sprint A Polish)
    if net_liq > 0 and buy_power > sell_supply * 2:
        liq_interpretation = "Strong buy-side liquidity dominance — stablecoin inflow far exceeds token deposit pressure"
    elif net_liq > 0:
        liq_interpretation = "Moderate buy-side advantage — fresh capital entering outpaces sell supply"
    elif net_liq < 0 and sell_supply > buy_power * 2:
        liq_interpretation = "Heavy sell-side pressure — token deposits overwhelm available buy liquidity"
    elif net_liq < 0:
        liq_interpretation = "Sell supply slightly exceeds buy power — watch for increasing deposit pressure"
    else:
        liq_interpretation = "Balanced liquidity — buy power and sell supply roughly matched"
    market_liquidity = {
        "buy_power": round(buy_power, 2),
        "buy_power_fmt": f"+{_fmt_usd(buy_power)}",
        "sell_supply": round(sell_supply, 2),
        "sell_supply_fmt": f"+{_fmt_usd(sell_supply)}",
        "net_liquidity": round(net_liq, 2),
        "net_liquidity_fmt": ("+" if net_liq >= 0 else "-") + _fmt_usd(abs(net_liq)),
        "bias": liq_bias,
        "interpretation": liq_interpretation,
    }

    # ══════════════════════════════════════════════════════════
    # Sprint B Engine 1: EXCHANGE INVENTORY
    # ══════════════════════════════════════════════════════════
    # Track net inventory change per token across all exchanges
    # inventory_delta = deposits - withdrawals (positive = inventory growing = bearish)
    token_in_total = {}   # sym -> total deposit USD
    token_out_total = {}  # sym -> total withdrawal USD
    for t in all_transfers:
        sym = t["token"] or "ERC20"
        if sym in ("USDT", "USDC", "DAI"):
            continue
        if t["direction"] == "deposit":
            token_in_total[sym] = token_in_total.get(sym, 0) + t["usd"]
        else:
            token_out_total[sym] = token_out_total.get(sym, 0) + t["usd"]

    # Build inventory per token (top tokens by volume)
    all_tokens_vol = {}
    for sym in set(list(token_in_total.keys()) + list(token_out_total.keys())):
        inv = token_in_total.get(sym, 0)
        outv = token_out_total.get(sym, 0)
        all_tokens_vol[sym] = inv + outv

    top_inv_tokens = sorted(all_tokens_vol.items(), key=lambda x: x[1], reverse=True)[:8]

    exchange_inventory = []
    for sym, vol in top_inv_tokens:
        deps = token_in_total.get(sym, 0)
        withs = token_out_total.get(sym, 0)
        delta = deps - withs  # positive = inventory growing
        delta_pct = (delta / max(vol, 1)) * 100

        if delta > 0 and delta_pct > 20:
            state = "growing"
            interpretation = "Supply entering exchanges"
        elif delta < 0 and abs(delta_pct) > 20:
            state = "shrinking"
            interpretation = "Supply leaving exchanges"
        else:
            state = "stable"
            interpretation = "Balanced flow"

        # Per-exchange breakdown for this token + top transfers
        per_exchange = []
        token_top_txs = []
        for t in sorted(all_transfers, key=lambda x: x["usd"], reverse=True):
            if (t["token"] == sym or (sym == "ERC20" and not t["token"])):
                if len(token_top_txs) < 3:
                    token_top_txs.append({
                        "direction": t["direction"],
                        "usd_fmt": _fmt_usd(t["usd"]),
                        "from_address": t.get("from", ""),
                        "to_address": t.get("to", ""),
                        "tx_hash": t.get("tx_hash", ""),
                        "exchange": t["exchange"],
                    })
        for ex in exchange_data.values():
            ex_in = ex["tokens_in"].get(sym, 0) + (ex["tokens_in"].get("", 0) if sym == "ERC20" else 0)
            ex_out = ex["tokens_out"].get(sym, 0) + (ex["tokens_out"].get("", 0) if sym == "ERC20" else 0)
            if ex_in > 0 or ex_out > 0:
                per_exchange.append({
                    "exchange": ex["entityName"],
                    "deposits": round(ex_in, 2),
                    "withdrawals": round(ex_out, 2),
                    "net": round(ex_in - ex_out, 2),
                    "net_fmt": _fmt_usd(ex_in - ex_out),
                })
        per_exchange.sort(key=lambda x: abs(x["net"]), reverse=True)

        exchange_inventory.append({
            "token": sym,
            "deposits": round(deps, 2),
            "deposits_fmt": _fmt_usd(deps),
            "withdrawals": round(withs, 2),
            "withdrawals_fmt": _fmt_usd(withs),
            "net_change": round(delta, 2),
            "net_change_fmt": ("+" if delta >= 0 else "") + _fmt_usd(delta),
            "change_pct": round(delta_pct, 1),
            "state": state,
            "interpretation": interpretation,
            "per_exchange": per_exchange[:4],
            "top_transactions": token_top_txs,
        })

    # ══════════════════════════════════════════════════════════
    # Sprint B Engine 2: FLOW TYPE CLASSIFICATION
    # ══════════════════════════════════════════════════════════
    flow_counts = {"distribution": 0, "accumulation": 0, "liquidity_provision": 0, "market_making": 0}
    flow_usd = {"distribution": 0, "accumulation": 0, "liquidity_provision": 0, "market_making": 0}
    flow_top_txs = {"distribution": [], "accumulation": [], "liquidity_provision": [], "market_making": []}

    for t in sorted(all_transfers, key=lambda x: x["usd"], reverse=True):
        tok = t["token"]
        is_stable = tok in ("USDT", "USDC", "DAI")
        from_addr = t.get("from", "")
        to_addr = t.get("to", "")
        from_is_cex = from_addr in exchange_addrs
        to_is_cex = to_addr in exchange_addrs

        if from_is_cex and to_is_cex:
            ftype = "market_making"
        elif to_is_cex and is_stable:
            ftype = "liquidity_provision"
        elif to_is_cex and not is_stable:
            ftype = "distribution"
        elif from_is_cex and not is_stable:
            ftype = "accumulation"
        elif from_is_cex and is_stable:
            ftype = "distribution"
        else:
            ftype = "distribution"

        flow_counts[ftype] += 1
        flow_usd[ftype] += t["usd"]

        if len(flow_top_txs[ftype]) < 3:
            flow_top_txs[ftype].append({
                "direction": t["direction"],
                "token": t["token"],
                "usd_fmt": _fmt_usd(t["usd"]),
                "from_address": t.get("from", ""),
                "to_address": t.get("to", ""),
                "tx_hash": t.get("tx_hash", ""),
                "exchange": t["exchange"],
            })

    total_classified = sum(flow_usd.values())
    flow_labels = {
        "distribution": "Distribution",
        "accumulation": "Accumulation",
        "liquidity_provision": "Liquidity Provision",
        "market_making": "Market Making",
    }

    flow_composition = []
    for ftype in ["distribution", "accumulation", "liquidity_provision", "market_making"]:
        pct = (flow_usd[ftype] / max(total_classified, 1)) * 100
        flow_composition.append({
            "type": ftype,
            "label": flow_labels[ftype],
            "usd": round(flow_usd[ftype], 2),
            "usd_fmt": _fmt_usd(flow_usd[ftype]),
            "percentage": round(pct, 1),
            "tx_count": flow_counts[ftype],
            "top_transactions": flow_top_txs.get(ftype, []),
        })
    flow_composition.sort(key=lambda x: x["usd"], reverse=True)

    # Dominant flow
    dominant_flow = flow_composition[0] if flow_composition else None
    if dominant_flow:
        if dominant_flow["type"] == "distribution":
            flow_interpretation = "Sell pressure building"
        elif dominant_flow["type"] == "accumulation":
            flow_interpretation = "Long-term accumulation dominant"
        elif dominant_flow["type"] == "liquidity_provision":
            flow_interpretation = "Fresh buying power entering"
        else:
            flow_interpretation = "Liquidity rebalancing active"
    else:
        flow_interpretation = "Insufficient flow data"

    flow_classification = {
        "composition": flow_composition,
        "dominant_type": dominant_flow["type"] if dominant_flow else "neutral",
        "dominant_label": dominant_flow["label"] if dominant_flow else "Neutral",
        "dominant_pct": dominant_flow["percentage"] if dominant_flow else 0,
        "interpretation": flow_interpretation,
        "total_classified": round(total_classified, 2),
        "total_classified_fmt": _fmt_usd(total_classified),
    }

    # ══════════════════════════════════════════════════════════
    # Sprint B Engine 3: LIQUIDITY SHOCK DETECTOR
    # ══════════════════════════════════════════════════════════
    # Formula: shock_score = stablecoin_inflow + token_withdrawals - token_deposits
    token_withdrawals_total = sum(token_out_total.values())
    token_deposits_total = sum(token_in_total.values())

    shock_buy = total_stable_in + token_withdrawals_total
    shock_sell = token_deposits_total + total_stable_out
    shock_net = shock_buy - shock_sell
    shock_total = shock_buy + shock_sell

    # Shock ratio: how imbalanced
    if shock_total > 0:
        shock_ratio = shock_net / shock_total  # -1 to +1
    else:
        shock_ratio = 0

    # 5 states
    if shock_ratio > 0.4:
        shock_state = "strong_bullish_shock"
        shock_label = "Strong Bullish Shock"
        shock_interpretation = "Massive buy-side liquidity imbalance — potential breakout"
    elif shock_ratio > 0.15:
        shock_state = "bullish_imbalance"
        shock_label = "Bullish Liquidity Imbalance"
        shock_interpretation = "Liquidity balance favors upside"
    elif shock_ratio > -0.15:
        shock_state = "neutral"
        shock_label = "Neutral Liquidity"
        shock_interpretation = "Buy and sell pressure roughly balanced"
    elif shock_ratio > -0.4:
        shock_state = "bearish_imbalance"
        shock_label = "Bearish Liquidity Imbalance"
        shock_interpretation = "Sell supply exceeds buy power"
    else:
        shock_state = "strong_bearish_shock"
        shock_label = "Strong Bearish Shock"
        shock_interpretation = "Massive sell-side pressure — potential breakdown"

    # Shock drivers
    shock_drivers = []
    if total_stable_in > total_stable_out * 1.2:
        shock_drivers.append(f"Stablecoin inflow {_fmt_usd(total_stable_in)}")
    if token_withdrawals_total > token_deposits_total * 1.2:
        shock_drivers.append(f"Token withdrawals {_fmt_usd(token_withdrawals_total)}")
    if token_deposits_total > token_withdrawals_total * 1.2:
        shock_drivers.append(f"Token deposits rising {_fmt_usd(token_deposits_total)}")
    if total_stable_out > total_stable_in * 1.2:
        shock_drivers.append(f"Stablecoin outflow {_fmt_usd(total_stable_out)}")

    # Per-exchange contribution to shock
    shock_exchanges = []
    for ex in exchanges_sorted[:5]:
        ex_stable_in = sum(ex["tokens_in"].get(s, 0) for s in ("USDT", "USDC", "DAI"))
        ex_token_out = sum(v for k, v in ex["tokens_out"].items() if k not in ("USDT", "USDC", "DAI"))
        ex_token_in = sum(v for k, v in ex["tokens_in"].items() if k not in ("USDT", "USDC", "DAI"))
        ex_buy = ex_stable_in + ex_token_out
        ex_sell = ex_token_in
        ex_contribution = ex_buy - ex_sell
        if abs(ex_contribution) > 100:
            dominant_factor = "stablecoin inflow" if ex_stable_in > ex_token_out else "token withdrawals" if ex_token_out > ex_stable_in else "mixed"
            if ex_contribution < 0:
                dominant_factor = "token deposits"
            # Collect wallet addresses for this exchange
            eid = ex["entityId"]
            ex_wallets = sorted(entity_addr_sets.get(eid, set()))[:5]
            shock_exchanges.append({
                "exchange": ex["entityName"],
                "contribution": round(ex_contribution, 2),
                "contribution_fmt": ("+" if ex_contribution >= 0 else "") + _fmt_usd(ex_contribution),
                "dominant_factor": dominant_factor,
                "wallet_addresses": ex_wallets,
            })
    shock_exchanges.sort(key=lambda x: abs(x["contribution"]), reverse=True)

    liquidity_shock = {
        "state": shock_state,
        "label": shock_label,
        "buy_power": round(shock_buy, 2),
        "buy_power_fmt": _fmt_usd(shock_buy),
        "sell_supply": round(shock_sell, 2),
        "sell_supply_fmt": _fmt_usd(shock_sell),
        "net": round(shock_net, 2),
        "net_fmt": ("+" if shock_net >= 0 else "-") + _fmt_usd(abs(shock_net)),
        "ratio": round(shock_ratio, 3),
        "interpretation": shock_interpretation,
        "drivers": shock_drivers[:4],
        "exchange_drivers": shock_exchanges[:4],
    }

    # ══════════════════════════════════════════════════════════
    # Sprint C Engine 1: EXCHANGE BEHAVIOR MAP
    # ══════════════════════════════════════════════════════════
    # X axis: stable_ratio (0..1) → 0=asset-focused, 1=stablecoin-focused
    # Y axis: buy_score (-1..1) → -1=sell pressure, +1=buy pressure
    # Quadrants: top-left=Accumulation, top-right=Liquidity Hub,
    #            bottom-left=Neutral, bottom-right=Distribution
    behavior_map_points = []
    for ex in exchanges_sorted[:10]:
        ex_vol = ex["inflow_usd"] + ex["outflow_usd"]
        if ex_vol < 100 or ex["tx_count"] < 2:
            continue
        # Y: buy score = (withdrawals - deposits) / total
        buy_score = (ex["outflow_usd"] - ex["inflow_usd"]) / ex_vol  # -1 to +1
        # X: stablecoin ratio among this exchange's flows
        ex_stable_in = sum(ex["tokens_in"].get(s, 0) for s in ("USDT", "USDC", "DAI"))
        ex_stable_out = sum(ex["tokens_out"].get(s, 0) for s in ("USDT", "USDC", "DAI"))
        ex_stable_total = ex_stable_in + ex_stable_out
        stable_ratio = ex_stable_total / max(ex_vol, 1)  # 0 to 1

        # Quadrant classification
        if buy_score > 0.1 and stable_ratio < 0.5:
            quadrant = "accumulation"
        elif buy_score > 0.1 and stable_ratio >= 0.5:
            quadrant = "liquidity_hub"
        elif buy_score < -0.1 and stable_ratio >= 0.3:
            quadrant = "distribution"
        else:
            quadrant = "neutral"

        quadrant_labels = {
            "accumulation": "Accumulation",
            "liquidity_hub": "Liquidity Hub",
            "distribution": "Distribution",
            "neutral": "Neutral",
        }

        behavior_map_points.append({
            "exchange": ex["entityName"],
            "entity_id": ex["entityId"],
            "x": round(stable_ratio, 3),      # 0..1
            "y": round(buy_score, 3),          # -1..+1
            "volume": round(ex_vol, 2),
            "volume_fmt": _fmt_usd(ex_vol),
            "quadrant": quadrant,
            "quadrant_label": quadrant_labels[quadrant],
            "net_flow_fmt": ("+" if ex["outflow_usd"] >= ex["inflow_usd"] else "") + _fmt_usd(ex["outflow_usd"] - ex["inflow_usd"]),
        })

    # Find dominant exchange
    dominant_venue = behavior_map_points[0] if behavior_map_points else None
    behavior_map = {
        "points": behavior_map_points,
        "dominant_venue": {
            "exchange": dominant_venue["exchange"],
            "quadrant_label": dominant_venue["quadrant_label"],
            "volume_fmt": dominant_venue["volume_fmt"],
            "share": round((dominant_venue["volume"] / max(total_volume, 1)) * 100, 1),
        } if dominant_venue else None,
        "quadrant_summary": {},
    }
    # Summarize quadrant counts
    for q in ("accumulation", "distribution", "liquidity_hub", "neutral"):
        pts = [p for p in behavior_map_points if p["quadrant"] == q]
        behavior_map["quadrant_summary"][q] = {
            "count": len(pts),
            "total_volume": round(sum(p["volume"] for p in pts), 2),
            "exchanges": [p["exchange"] for p in pts],
        }

    # ══════════════════════════════════════════════════════════
    # Sprint C Engine 2: EXCHANGE LIQUIDITY ENGINE
    # ══════════════════════════════════════════════════════════
    # Per-token: buy_power (stablecoins + withdrawals) vs sell_supply (deposits)
    # Combines Stablecoin Power + Inventory + Shock into per-token view
    liquidity_tokens = []
    # Get all non-stablecoin tokens with volume
    for sym, vol in top_inv_tokens:
        deps = token_in_total.get(sym, 0)
        withs = token_out_total.get(sym, 0)
        # Buy power for this token: its withdrawals (supply removal)
        # Sell supply: its deposits
        # Also add proportional stablecoin power
        token_vol_share = vol / max(total_volume, 1)
        allocated_stable = total_stable_in * token_vol_share

        token_buy_power = withs + allocated_stable
        token_sell_supply = deps
        token_net = token_buy_power - token_sell_supply

        token_total_liq = token_buy_power + token_sell_supply
        if token_total_liq > 0:
            buy_pct = round((token_buy_power / token_total_liq) * 100, 1)
        else:
            buy_pct = 50.0

        if token_net > token_total_liq * 0.2:
            liq_state = "bullish_imbalance"
            liq_interpretation = "Liquidity favors upside"
        elif token_net < -token_total_liq * 0.2:
            liq_state = "bearish_imbalance"
            liq_interpretation = "Sell pressure dominant"
        else:
            liq_state = "neutral"
            liq_interpretation = "Balanced liquidity"

        liquidity_tokens.append({
            "token": sym,
            "buy_power": round(token_buy_power, 2),
            "buy_power_fmt": _fmt_usd(token_buy_power),
            "sell_supply": round(token_sell_supply, 2),
            "sell_supply_fmt": _fmt_usd(token_sell_supply),
            "net_liquidity": round(token_net, 2),
            "net_liquidity_fmt": ("+" if token_net >= 0 else "-") + _fmt_usd(abs(token_net)),
            "buy_pct": buy_pct,
            "state": liq_state,
            "interpretation": liq_interpretation,
        })

    liquidity_engine = {
        "tokens": liquidity_tokens,
        "aggregate": {
            "total_buy_power": round(shock_buy, 2),
            "total_buy_power_fmt": _fmt_usd(shock_buy),
            "total_sell_supply": round(shock_sell, 2),
            "total_sell_supply_fmt": _fmt_usd(shock_sell),
            "net": round(shock_net, 2),
            "net_fmt": ("+" if shock_net >= 0 else "-") + _fmt_usd(abs(shock_net)),
            "state": shock_state,
        },
    }

    # ── Top transactions for exchange pressure ──
    _ep_deposit_txs = []
    _ep_withdrawal_txs = []
    for t in sorted(all_transfers, key=lambda x: x["usd"], reverse=True):
        if t["direction"] == "deposit" and len(_ep_deposit_txs) < 3:
            _ep_deposit_txs.append({
                "usd_fmt": _fmt_usd(t["usd"]), "token": t["token"],
                "from_address": t.get("from", ""), "to_address": t.get("to", ""),
                "tx_hash": t.get("tx_hash", ""), "exchange": t["exchange"],
            })
        elif t["direction"] == "withdrawal" and len(_ep_withdrawal_txs) < 3:
            _ep_withdrawal_txs.append({
                "usd_fmt": _fmt_usd(t["usd"]), "token": t["token"],
                "from_address": t.get("from", ""), "to_address": t.get("to", ""),
                "tx_hash": t.get("tx_hash", ""), "exchange": t["exchange"],
            })

    result = {
        "market_bias": market_bias,
        "confidence": confidence,
        "narrative_lines": narrative_lines[:4],

        # v2.1 Hero enhancements
        "drivers": hero_drivers[:4],
        "offsetting_factors": offsetting[:3],
        "indicators": {
            "sell_pressure": sell_pressure_pct,
            "liquidity": liquidity_pct,
            "confidence": conf_pct,
        },
        "dominant_venue": hero_dominant_venue,
        "dominant_asset": hero_dominant_asset,

        "exchange_pressure": {
            "deposits": round(total_inflow, 2),
            "deposits_fmt": _fmt_usd(total_inflow),
            "withdrawals": round(total_outflow, 2),
            "withdrawals_fmt": _fmt_usd(total_outflow),
            "net_flow": round(net_flow, 2),
            "net_fmt": ("+" if net_flow >= 0 else "") + _fmt_usd(net_flow),
            "bias": market_bias,
            "active_exchanges": active_exchanges_final,
            "total_transfers": len(in_logs) + len(out_logs),
            "top_deposit_txs": _ep_deposit_txs,
            "top_withdrawal_txs": _ep_withdrawal_txs,
        },

        "stablecoin_power": stablecoin_power,
        "market_liquidity": market_liquidity,
        "exchange_inventory": exchange_inventory,
        "flow_classification": flow_classification,
        "liquidity_shock": liquidity_shock,
        "behavior_map": behavior_map,
        "liquidity_engine": liquidity_engine,
        "top_exchanges": top_exchanges,
        "largest_transfers": largest_clean,
        "exchange_rotation": exchange_rotation,
        "rotation_fallback": rotation_fallback,
        "pump_setups": pump_setups,
    }

    cache_set(ck, result)
    return result
