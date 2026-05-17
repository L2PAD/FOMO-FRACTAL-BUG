"""
Smart Money Radar Service
==========================
Sprint 1.2+: Discovery engine for early smart-money activity.

Detects:
  - EARLY_ACCUMULATION: wallets accumulating before price moves
  - EARLY_DISTRIBUTION: wallets distributing/exiting
  - SMART_WALLET_DETECTED: new high-score wallets
  - CLUSTER_ACTIVITY: synchronized buying/selling by wallet groups

Each event has:
  - signal_class: wallet | market | cluster
  - impact_score: 0-100, how big this signal is for the market
  - signal_severity: LOW | MEDIUM | HIGH | CRITICAL
"""

from pymongo import MongoClient, DESCENDING
from bson.codec_options import CodecOptions, DatetimeConversion
from datetime import datetime, timezone
import os
import math
import time
from typing import Optional
from collections import defaultdict

_client: Optional[MongoClient] = None
_db = None
_codec_opts = CodecOptions(datetime_conversion=DatetimeConversion.DATETIME_CLAMP)

# ── In-memory cache (TTL 30s) ──
_cache: dict = {}
_CACHE_TTL = 30

def cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None

def cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": time.time()}


def get_db():
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL")
        _client = MongoClient(mongo_url)
        _db = _client["intelligence_engine"]
    return _db


def _col(name: str):
    return get_db().get_collection(name, codec_options=_codec_opts)


# ── Scoring helpers ──────────────────────────────────────────────

def _timing_score(entity_flow: dict) -> float:
    net = entity_flow.get("netUsd", 0)
    dex = abs(entity_flow.get("dexUsd", 0))
    cex = abs(entity_flow.get("cexUsd", 0))
    trades = entity_flow.get("trades", 0) or 1
    vol = abs(net)
    dex_ratio = dex / (dex + cex + 1)
    avg_trade = vol / trades if trades > 0 else 0
    size_score = min(5, avg_trade / 200_000)
    score = dex_ratio * 8 + size_score
    if trades >= 10:
        score += 2
    return round(min(15, max(-10, score)), 1)


def _confidence_score(edge: float, timing: float, flow_usd: float, cluster_bonus: float = 0) -> int:
    w = min(35, (edge / 100) * 35)
    t = min(30, max(0, (timing + 10) / 25 * 30))
    f = min(20, (min(abs(flow_usd), 10_000_000) / 10_000_000) * 20)
    c = min(15, cluster_bonus)
    return max(5, min(95, int(w + t + f + c)))


def _impact_score(flow_usd: float, edge: float, cluster_weight: float = 0) -> int:
    vol_component = min(40, (math.log10(max(abs(flow_usd), 1)) / 8) * 40)
    wallet_component = min(35, (edge / 100) * 35)
    cluster_component = min(25, cluster_weight)
    return max(0, min(100, int(vol_component + wallet_component + cluster_component)))


def _severity(impact: int, confidence: int) -> str:
    if impact >= 75 and confidence >= 65:
        return "CRITICAL"
    if impact >= 55 or confidence >= 60:
        return "HIGH"
    if impact >= 35 or confidence >= 40:
        return "MEDIUM"
    return "LOW"


def _signal_class(event_type: str, wallet_count: int = 1) -> str:
    if event_type == "cluster_activity":
        return "market" if wallet_count >= 20 else "cluster"
    return "wallet"


def _build_reasons(event_type: str, entity: dict, timing: float, tokens: list) -> list:
    reasons = []
    edge = entity.get("edgeScore", 0)
    if edge >= 60:
        reasons.append("high structural edge score")
    elif edge >= 40:
        reasons.append("notable structural edge score")
    if timing >= 8:
        reasons.append("strong early entry timing")
    elif timing >= 4:
        reasons.append("favorable entry timing")
    net = abs(entity.get("netUsd", 0) or entity.get("netAbsUsd", 0))
    if net >= 5_000_000:
        reasons.append("very large capital movement")
    elif net >= 1_000_000:
        reasons.append("significant capital movement")
    trades = entity.get("trades", 0)
    if trades >= 50:
        reasons.append("high trade frequency")
    dex = abs(entity.get("dexUsd", 0))
    cex = abs(entity.get("cexUsd", 0))
    if dex > cex * 2:
        reasons.append("DEX-concentrated activity")
    if tokens:
        top = tokens[0].get("tokenSymbol", "")
        if top:
            reasons.append(f"concentrated in {top}")
    if event_type == "cluster_activity":
        reasons.append("synchronized wallet group detected")
    if event_type == "smart_wallet_detected":
        reasons.append("newly identified high-score wallet")
    return reasons[:5]


def _time_ago(dt) -> str:
    if not dt:
        return "unknown"
    if isinstance(dt, str):
        return dt
    try:
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt.year > 3000 or dt.year < 2000:
            return "recent"
        diff = (now - dt).total_seconds()
        if diff < 0:
            return "just now"
        if diff < 60:
            return f"{int(diff)}s ago"
        if diff < 3600:
            return f"{int(diff // 60)}m ago"
        if diff < 86400:
            return f"{int(diff // 3600)}h ago"
        return f"{int(diff // 86400)}d ago"
    except (ValueError, OverflowError, OSError):
        return "recent"


def _clean(name: str) -> str:
    return name.replace("_", " ") if name else name


def _fmt_usd(n: float) -> str:
    a = abs(n)
    if a >= 1e9:
        return f"${a / 1e9:.2f}B"
    if a >= 1e6:
        return f"${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"${a / 1e3:.0f}K"
    return f"${a:.0f}"


def _resolve_name(eid: str, entity_name: str, entity_type: str, labels_map: dict):
    # Known entity ID patterns
    known_ids = {
        "unknown:address": ("Smart wallet cluster", "smart_money"),
        "dex:market": ("DEX Market", "dex"),
        "whale:unknown": ("Whale wallet", "whale"),
        "uniswap-router": ("Uniswap Router", "protocol"),
        "uniswap-router-v3": ("Uniswap V3 Router", "protocol"),
    }
    if eid in known_ids:
        return known_ids[eid]

    if (not entity_name or entity_name.lower() == "unknown") and eid.startswith("0x"):
        lbl = labels_map.get(eid.lower(), {})
        entity_name = lbl.get("name", "")
        if lbl.get("labelType"):
            entity_type = lbl.get("type", entity_type)
    if not entity_name or entity_name.lower() == "unknown":
        # Capitalize non-hex IDs
        if not eid.startswith("0x") and ":" not in eid:
            return _clean(eid.replace("-", " ").title()), "exchange"
        t = entity_type.lower()
        if t in ("whale", "smart_money"):
            entity_name = "Smart wallet"
        elif t == "exchange":
            entity_name = eid.replace("_", " ").title() if not eid.startswith("0x") else "Exchange wallet"
        elif t in ("protocol", "dex"):
            entity_name = "Protocol contract"
        else:
            entity_name = "Active wallet"
    return _clean(entity_name), entity_type


# ── Main pipeline ────────────────────────────────────────────────

def get_radar_events(chain_id: int = 1, window: str = "24h", sort_by: str = "confidence", limit: int = 20) -> list:
    ck = f"radar:{chain_id}:{window}:{sort_by}:{limit}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    events = []
    flows_col = _col("onchain_v2_entity_flows")
    scores_col = _col("onchainv2_actorscores")
    labels_col = _col("onchain_v2_address_labels")

    flows = list(flows_col.find({"chainId": chain_id, "window": window}, {"_id": 0}).sort("netUsd", DESCENDING).limit(200))

    latest_bucket = scores_col.find_one({"chainId": chain_id, "window": window}, sort=[("bucketTs", DESCENDING)])
    bts = latest_bucket["bucketTs"] if latest_bucket else None
    scores_map = {}
    if bts:
        for s in scores_col.find({"chainId": chain_id, "window": window, "bucketTs": bts}, {"_id": 0}):
            scores_map[s.get("entityId", "")] = s

    labels_map = {}
    for lbl in labels_col.find({"chainId": chain_id}, {"_id": 0}):
        a = lbl.get("address", "").lower()
        if a:
            labels_map[a] = lbl

    def _make_event(etype, eid, entity, score_data, flow_data, tokens, cluster_wallets=1, cluster_bonus=0):
        edge = score_data.get("edgeScore", 30)
        timing = _timing_score(flow_data) if flow_data else 5.0
        net = flow_data.get("netUsd", 0) if flow_data else 0
        conf = _confidence_score(edge, timing, net, cluster_bonus)
        impact = _impact_score(net, edge, cluster_bonus)
        sev = _severity(impact, conf)
        sc = _signal_class(etype, cluster_wallets)
        name, etype_res = _resolve_name(eid, entity.get("entityName") or score_data.get("entityName", ""),
                                         entity.get("entityType") or score_data.get("entityType", "unknown"), labels_map)
        top_token = tokens[0].get("tokenSymbol", "") if tokens else ""
        reasons = _build_reasons(etype, {**entity, **score_data, **flow_data}, timing, tokens)
        return {
            "event_type": etype,
            "signal_class": sc,
            "wallet": eid if eid.startswith("0x") else "",
            "entity": name,
            "entity_type": etype_res,
            "token": top_token,
            "net_flow_usd": round(net, 2),
            "confidence": conf,
            "timing_score": timing,
            "impact_score": impact,
            "signal_severity": sev,
            "last_activity": _time_ago(flow_data.get("updatedAt") or score_data.get("updatedAt")),
            "reason": reasons,
            "trades": flow_data.get("trades", 0) if flow_data else score_data.get("trades", 0),
            "cluster_wallets": cluster_wallets if etype == "cluster_activity" else None,
            "wallet_addresses": [eid] if eid.startswith("0x") else [],
        }

    # ── Early Accumulation ──
    for e in [f for f in flows if (f.get("netUsd", 0) or 0) > 100_000][:15]:
        eid = e.get("entityId", "")
        sd = scores_map.get(eid, {})
        ev = _make_event("early_accumulation", eid, e, sd, e, e.get("tokenBreakdown", []))
        if ev["confidence"] >= 25:
            events.append(ev)

    # ── Early Distribution ──
    dists = [f for f in flows if (f.get("netUsd", 0) or 0) < -100_000]
    dists.sort(key=lambda x: x.get("netUsd", 0))
    for e in dists[:10]:
        eid = e.get("entityId", "")
        sd = scores_map.get(eid, {})
        ev = _make_event("early_distribution", eid, e, sd, e, e.get("tokenBreakdown", []))
        if ev["confidence"] >= 25:
            events.append(ev)

    # ── Smart Wallet Detected ──
    high = [s for s in scores_map.values() if s.get("edgeScore", 0) >= 55]
    high.sort(key=lambda x: x.get("edgeScore", 0), reverse=True)
    for sd in high[:8]:
        eid = sd.get("entityId", "")
        fm = next((f for f in flows if f.get("entityId") == eid), {})
        ev = _make_event("smart_wallet_detected", eid, sd, sd, fm, fm.get("tokenBreakdown", []))
        if ev["confidence"] >= 30:
            events.append(ev)

    # ── Cluster Activity ──
    token_groups = defaultdict(list)
    for e in flows:
        for tk in e.get("tokenBreakdown", [])[:3]:
            sym = tk.get("tokenSymbol", "")
            if sym and abs(tk.get("netUsd", 0)) > 50_000:
                token_groups[sym].append({
                    "entityId": e.get("entityId", ""),
                    "entityName": e.get("entityName", ""),
                    "entityType": e.get("entityType", "unknown"),
                    "netUsd": tk.get("netUsd", 0),
                    "trades": e.get("trades", 0),
                    "updatedAt": e.get("updatedAt"),
                })

    for sym, group in token_groups.items():
        buyers = [g for g in group if g["netUsd"] > 0]
        sellers = [g for g in group if g["netUsd"] < 0]
        for verb, cw in [("accumulating", buyers), ("distributing", sellers)]:
            if len(cw) < 3:
                continue
            combined = sum(w["netUsd"] for w in cw)
            total_trades = sum(w.get("trades", 0) for w in cw)
            wc = len(cw)
            cb = min(15, wc * 3)
            edge_avg = 50
            impact = _impact_score(combined, edge_avg, cb)
            conf = _confidence_score(edge_avg, 5.0, combined, cb)
            sev = _severity(impact, conf)
            sc = _signal_class("cluster_activity", wc)
            events.append({
                "event_type": "cluster_activity",
                "signal_class": sc,
                "wallet": "",
                "entity": f"{wc} wallets {verb} {sym}",
                "entity_type": "cluster",
                "token": sym,
                "net_flow_usd": round(combined, 2),
                "confidence": conf,
                "timing_score": 5.0,
                "impact_score": impact,
                "signal_severity": sev,
                "last_activity": _time_ago(cw[0].get("updatedAt")) if cw else "unknown",
                "reason": [
                    f"{wc} wallets synchronized {verb}",
                    f"combined flow {'+'if combined > 0 else ''}{_fmt_usd(combined)}",
                    f"{total_trades} total trades",
                    "entity cluster correlation detected",
                ],
                "trades": total_trades,
                "cluster_wallets": wc,
                "wallet_addresses": [w["entityId"] for w in cw if w.get("entityId", "").startswith("0x")][:20],
            })

    # ── Sort ──
    if sort_by == "confidence":
        events.sort(key=lambda e: e["confidence"], reverse=True)
    elif sort_by == "net_flow":
        events.sort(key=lambda e: abs(e["net_flow_usd"]), reverse=True)
    elif sort_by == "impact":
        events.sort(key=lambda e: e["impact_score"], reverse=True)
    elif sort_by == "recency":
        def rk(e):
            la = e.get("last_activity", "")
            if "s ago" in la: return 0
            if "m ago" in la: return 1
            if "h ago" in la: return 2
            return 3
        events.sort(key=rk)

    seen = set()
    out = []
    for ev in events:
        key = (ev["entity"], ev["event_type"], ev["token"])
        if key not in seen:
            seen.add(key)
            out.append(ev)
    result = out[:limit]
    cache_set(ck, result)
    return result
