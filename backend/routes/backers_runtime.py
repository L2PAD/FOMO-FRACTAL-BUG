"""
Backers runtime adapter — wires the /api/backers* endpoints to REAL data
in fomo_mobile.{canonical_persons, funding_rounds, canonical_projects,
raw_funding(cryptorank)}.  Mounted BEFORE bakery_engine so it overrides
the legacy `connections_db` reads which return empty.

Shape produced matches what BakeryPage.jsx consumes:
    {ok, bakers:[…], decisions:[…], whyNow:[…], sync:{}, marketControl:{…},
     stats:{total, enter, follow, watch, avoid, exit}}
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pymongo import MongoClient, DESCENDING

router = APIRouter(prefix="/api/backers", tags=["backers-runtime"])

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "fomo_mobile")]

# Sector classification (token symbol → sector)
AI_TOKENS    = {"FET", "RNDR", "AGIX", "OCEAN", "TAO", "AKT", "WLD", "BITTENSOR"}
MEME_TOKENS  = {"WIF", "PEPE", "BONK", "DOGE", "SHIB", "FLOKI", "BRETT", "TRUMP"}
DEFI_TOKENS  = {"UNI", "AAVE", "MKR", "CRV", "COMP", "SNX", "SUSHI", "LINK"}
INFRA_TOKENS = {"OP", "ARB", "SUI", "SEI", "APT", "TIA", "MATIC", "AVAX", "ATOM"}
L1_TOKENS    = {"ETH", "SOL", "ADA", "BNB", "XRP", "DOT", "NEAR"}

SECTOR_MAP = {
    "AI": AI_TOKENS, "MEME": MEME_TOKENS, "DEFI": DEFI_TOKENS,
    "INFRA": INFRA_TOKENS, "L1": L1_TOKENS,
}


def _project_sector(tags: List[str]) -> str:
    tu = {t.upper() for t in (tags or []) if t}
    for sector, toks in SECTOR_MAP.items():
        if tu & toks:
            return sector
    return "OTHER"


# ─── /api/backers ────────────────────────────────────────────────────────────
@router.get("")
async def backers_list(
    limit: int = Query(50, ge=1, le=200),
    minRounds: int = Query(0, ge=0),
):
    """
    Build a real bakers list by aggregating investors across:
      1. funding_rounds (legacy curated)
      2. deep_projects.investors (rich per-project scrape from CryptoRank +
         ICODrops + DropsTab — the source of truth post deep-parser)
    Each investor becomes a 'baker'.  Their backed projects = portfolio.
    """
    inv_index: Dict[str, Dict[str, Any]] = {}

    # 1. Legacy funding_rounds
    for r in _db.funding_rounds.find({}, {"_id": 0}):
        investors = r.get("investors") or r.get("backers") or []
        project   = r.get("project") or r.get("name") or r.get("symbol") or "?"
        amount    = r.get("amount_usd") or r.get("amount") or 0
        round_t   = r.get("round") or r.get("type") or "Seed"
        date      = r.get("date") or r.get("closed_at") or r.get("createdAt")
        sector    = r.get("category") or r.get("sector") or "OTHER"

        if isinstance(investors, str):
            investors = [investors]
        for inv in investors:
            if not inv:
                continue
            name = (inv if isinstance(inv, str) else inv.get("name", "")) or ""
            name = name.strip()
            if not name:
                continue
            bucket = inv_index.setdefault(name, {
                "name":         name,
                "totalRounds":  0,
                "totalAmount":  0.0,
                "projects":     [],
                "sectors":      defaultdict(int),
                "lastActive":   None,
                "leadInCount":  0,
                "tiers":        defaultdict(int),
            })
            bucket["totalRounds"] += 1
            bucket["totalAmount"] += float(amount or 0)
            bucket["projects"].append({"name": project, "round": round_t, "amount": amount, "date": date})
            bucket["sectors"][sector] += 1
            if date:
                if not bucket["lastActive"] or str(date) > str(bucket["lastActive"]):
                    bucket["lastActive"] = date

    # 2. deep_projects.investors (the rich layer)
    for proj in _db.deep_projects.find({"investorCount": {"$gt": 0}}, {"_id": 0}):
        proj_name = proj.get("name") or proj.get("project_key") or "?"
        symbol = proj.get("symbol") or proj.get("project_key")
        tags = proj.get("tags") or []
        if proj.get("category"):
            tags = list(tags) + [proj["category"]]
        sector = _project_sector([symbol] + tags) if symbol else _project_sector(tags)
        # Pick a representative round amount (latest with raisedUsd)
        rounds = proj.get("rounds") or []
        proj_amount = 0
        latest_date = None
        for rnd in rounds:
            ra = rnd.get("raisedUsd") or 0
            if ra:
                proj_amount = max(proj_amount, int(ra))
            ds = rnd.get("startDate") or rnd.get("endDate")
            if ds and (not latest_date or str(ds) > str(latest_date)):
                latest_date = ds
        leads = {l.lower() for l in (proj.get("leadInvestors") or [])}

        for inv in proj.get("investors") or []:
            if not isinstance(inv, dict):
                continue
            name = (inv.get("name") or "").strip()
            if not name or len(name) < 2 or len(name) > 80:
                continue
            bucket = inv_index.setdefault(name, {
                "name":         name,
                "totalRounds":  0,
                "totalAmount":  0.0,
                "projects":     [],
                "sectors":      defaultdict(int),
                "lastActive":   None,
                "leadInCount":  0,
                "tiers":        defaultdict(int),
            })
            bucket["totalRounds"] += 1
            bucket["totalAmount"] += proj_amount  # rough — best signal available
            bucket["projects"].append({
                "name":   proj_name,
                "symbol": symbol,
                "source": proj.get("source"),
                "amount": proj_amount,
                "date":   latest_date,
                "tier":   inv.get("tier"),
            })
            bucket["sectors"][sector] += 1
            if inv.get("tier"):
                bucket["tiers"][inv["tier"]] += 1
            if name.lower() in leads or inv.get("isLead"):
                bucket["leadInCount"] += 1
            if latest_date and (not bucket["lastActive"] or str(latest_date) > str(bucket["lastActive"])):
                bucket["lastActive"] = latest_date

    # 3. deep_funds (DropsTab fund profiles with full Tier/ROI/portfolio)
    funds_index: Dict[str, Dict[str, Any]] = {}
    for fund in _db.deep_funds.find({}, {"_id": 0}):
        name = (fund.get("name") or "").strip()
        if not name:
            continue
        # Use this as authoritative source — overwrites less-rich entry
        b = inv_index.get(name) or {
            "name":         name,
            "totalRounds":  0,
            "totalAmount":  0.0,
            "projects":     [],
            "sectors":      defaultdict(int),
            "lastActive":   None,
            "leadInCount":  0,
            "tiers":        defaultdict(int),
        }
        b["totalRounds"] = max(b["totalRounds"], int(fund.get("totalInvestments") or 0))
        lead_count = fund.get("leadInvestments") or 0
        if isinstance(lead_count, list):
            lead_count = len(lead_count)
        b["leadInCount"] = max(b["leadInCount"], int(lead_count or 0))
        if fund.get("tier"):
            b["tiers"][fund["tier"]] += 1
        # Portfolio → projects
        for p in (fund.get("portfolio") or []):
            if not isinstance(p, dict) or not p.get("name"):
                continue
            b["projects"].append({
                "name":   p["name"],
                "symbol": p.get("symbol"),
                "amount": p.get("fundsRaised"),
                "source": "dropstab_fund",
            })
        # Country / fund metadata
        b["fundMeta"] = {
            "tier":             fund.get("tier"),
            "rank":             fund.get("rank"),
            "rating":           fund.get("rating"),
            "country":          fund.get("country"),
            "ventureType":      fund.get("ventureType"),
            "avgPublicRoi":     (fund.get("avgPublicRoi") or {}).get("USD") if isinstance(fund.get("avgPublicRoi"), dict) else fund.get("avgPublicRoi"),
            "avgPrivateRoi":    (fund.get("avgPrivateRoi") or {}).get("USD") if isinstance(fund.get("avgPrivateRoi"), dict) else fund.get("avgPrivateRoi"),
            "roundsPerYear":    fund.get("roundsPerYear"),
            "logo":             fund.get("logo"),
            "twitterUrl":       fund.get("twitterUrl"),
        }
        inv_index[name] = b
        funds_index[name] = fund

    # Build baker records
    bakers: List[Dict[str, Any]] = []
    persons = list(_db.canonical_persons.find({}, {"_id": 0}).limit(50))
    import math

    for name, b in inv_index.items():
        if b["totalRounds"] < minRounds:
            continue
        top_sector = max(b["sectors"].items(), key=lambda x: x[1])[0] if b["sectors"] else "OTHER"
        amount_for_score = max(b["totalAmount"], 1)
        fund_meta = b.get("fundMeta") or {}
        # Tier-aware scoring: Tier 1 funds get +25, Tier 2 +15, Tier 3 +5
        tier_boost = 25 if fund_meta.get("tier") == "Tier 1" else 15 if fund_meta.get("tier") == "Tier 2" else 5 if fund_meta.get("tier") == "Tier 3" else 0
        roi_boost = 0
        try:
            roi_pub = float(fund_meta.get("avgPublicRoi") or 0)
            if roi_pub > 50:   roi_boost = 20
            elif roi_pub > 10: roi_boost = 12
            elif roi_pub > 3:  roi_boost = 6
        except Exception:
            pass
        score = int(min(100,
            math.log10(max(b["totalRounds"], 1) + 1) * 25
            + b["leadInCount"] * 2
            + tier_boost
            + roi_boost
        ))
        # Honest play decision uses tier + lead activity
        if fund_meta.get("tier") == "Tier 1" and b["leadInCount"] >= 5:
            play = "ENTER"
        elif fund_meta.get("tier") in ("Tier 1", "Tier 2") and b["leadInCount"] >= 1:
            play = "FOLLOW"
        elif b["totalRounds"] >= 5:
            play = "FOLLOW"
        elif b["totalRounds"] >= 1:
            play = "WATCH"
        else:
            play = "AVOID"

        bakers.append({
            "id":             name.lower().replace(" ", "_"),
            "name":           name,
            "score":          score,
            "edgeScore":      min(int(score * 0.85), 100),
            "powerScore":     score,
            "playDecision":   play,
            "sector":         top_sector,
            "sectorBreakdown": dict(b["sectors"]),
            "totalRounds":    b["totalRounds"],
            "leadInCount":    b["leadInCount"],
            "tiers":          dict(b["tiers"]),
            "tier":           fund_meta.get("tier"),
            "country":        fund_meta.get("country"),
            "avgPublicRoi":   fund_meta.get("avgPublicRoi"),
            "avgPrivateRoi":  fund_meta.get("avgPrivateRoi"),
            "rank":           fund_meta.get("rank"),
            "ventureType":    fund_meta.get("ventureType"),
            "logo":           fund_meta.get("logo"),
            "twitterUrl":     fund_meta.get("twitterUrl"),
            "totalAmountUsd": int(b["totalAmount"]),
            "portfolio":      b["projects"][:15],
            "lastActive":     b["lastActive"],
            "alphaType":      "STRATEGIC" if b["leadInCount"] >= 5 else "TACTICAL",
            "trustMode":      "VERIFIED" if fund_meta.get("tier") in ("Tier 1", "Tier 2") else "EMERGING",
        })

    # Add famous individuals from canonical_persons that aren't investors already
    seen = {b["name"].lower() for b in bakers}
    for p in persons:
        name = (p.get("name") or p.get("handle") or "").strip()
        if not name or name.lower() in seen:
            continue
        bakers.append({
            "id":             name.lower().replace(" ", "_"),
            "name":           name,
            "score":          int(p.get("score", 0) * 100) if p.get("score", 0) <= 1 else int(p.get("score", 0)),
            "edgeScore":      0,
            "powerScore":     0,
            "playDecision":   "WATCH",
            "sector":         "OTHER",
            "sectorBreakdown": {},
            "totalRounds":    0,
            "leadInCount":    0,
            "tiers":          {},
            "totalAmountUsd": 0,
            "portfolio":      [],
            "lastActive":     p.get("updatedAt"),
            "alphaType":      "INFLUENCE",
            "trustMode":      "EMERGING",
            "kind":           "person",
        })

    bakers.sort(key=lambda b: b["score"], reverse=True)
    bakers = bakers[:limit]

    decisions = [b for b in bakers if b["playDecision"] in ("ENTER", "FOLLOW")]
    whyNow = []
    for d in decisions[:5]:
        whyNow.append({
            "id":     d["id"],
            "baker":  d["name"],
            "reason": f"{d['totalRounds']} rounds · lead in {d['leadInCount']} · top sector {d['sector']}",
            "score":  d["score"],
        })

    market_control: Dict[str, Any] = {}
    for sector in ("AI", "MEME", "DEFI", "INFRA", "L1"):
        sector_bakers = [b for b in bakers if b["sector"] == sector]
        if not sector_bakers:
            market_control[sector] = {
                "leader": None, "topBakers": [], "status": "no leader", "bakerCount": 0
            }
            continue
        leader = sector_bakers[0]
        market_control[sector] = {
            "leader":     {"name": leader["name"], "score": leader["score"]},
            "topBakers":  [{"name": b["name"], "score": b["score"]} for b in sector_bakers[:5]],
            "status":     "active",
            "bakerCount": len(sector_bakers),
        }

    stats_counter = defaultdict(int)
    for b in bakers:
        stats_counter[b["playDecision"].lower()] += 1
    stats_counter["total"] = len(bakers)

    return {
        "ok":             True,
        "bakers":         bakers,
        "decisions":      decisions,
        "whyNow":         whyNow,
        "sync":           {"snapshot": datetime.now(timezone.utc).isoformat()},
        "marketControl":  market_control,
        "stats":          dict(stats_counter),
        "count":          len(bakers),
        "asOf":           datetime.now(timezone.utc).isoformat(),
        "source":         "funding_rounds+deep_projects+canonical_persons",
    }


# ─── /api/backers/active ─────────────────────────────────────────────────────
@router.get("/active")
async def backers_active(limit: int = Query(20, ge=1, le=100)):
    """Recent funding flow events from raw_funding."""
    rounds = list(_db.funding_rounds.find({}, {"_id": 0}).sort("date", DESCENDING).limit(limit))
    flows = []
    for r in rounds:
        flows.append({
            "id":         r.get("id") or r.get("_id"),
            "project":    r.get("project") or r.get("name"),
            "amount":     r.get("amount_usd") or r.get("amount"),
            "round":      r.get("round") or r.get("type"),
            "investors":  r.get("investors") or [],
            "date":       r.get("date") or r.get("createdAt"),
            "sector":     r.get("category") or "OTHER",
        })
    return {"ok": True, "flows": flows, "count": len(flows),
            "asOf": datetime.now(timezone.utc).isoformat(),
            "source": "funding_rounds"}
