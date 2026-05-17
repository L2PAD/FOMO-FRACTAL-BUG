"""
Deep data runtime endpoints:
  GET /api/deep/funds          — DropsTab fund profiles (Tier 1-3, ROI, leadInvestments)
  GET /api/deep/persons        — Influencers / fund partners with X handles + scores
  GET /api/deep/unlocks        — Upcoming + past unlock events
  GET /api/deep/projects/{slug} — Per-project full dossier (investors, sales, vesting)
  GET /api/deep/stats          — Coverage stats across the deep_* collections
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException
from pymongo import MongoClient, DESCENDING

router = APIRouter(prefix="/api/deep", tags=["deep-runtime"])

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "fomo_mobile")]


def _clean(d: dict) -> dict:
    d.pop("_id", None)
    return d


@router.get("/stats")
async def deep_stats():
    return {
        "ok": True,
        "counts": {
            "deep_projects":       _db.deep_projects.count_documents({}),
            "deep_funding_rounds": _db.deep_funding_rounds.count_documents({}),
            "deep_persons":        _db.deep_persons.count_documents({}),
            "deep_unlocks":        _db.deep_unlocks.count_documents({}),
            "deep_funds":          _db.deep_funds.count_documents({}),
            "deep_project_events": _db.deep_project_events.count_documents({}),
        },
        "bySource": {
            "cryptorank": _db.deep_projects.count_documents({"source": "cryptorank"}),
            "icodrops":   _db.deep_projects.count_documents({"source": "icodrops"}),
            "dropstab":   _db.deep_projects.count_documents({"source": "dropstab"}),
        },
        "asOf":   datetime.now(timezone.utc).isoformat(),
        "source": "deep_parser",
    }


@router.get("/funds")
async def deep_funds(
    limit: int = Query(50, ge=1, le=200),
    tier: Optional[str] = Query(None, description="Filter by tier: 'Tier 1' / 'Tier 2' / 'Tier 3'"),
    minRoi: Optional[float] = Query(None, description="Minimum avgPublicRoi (USD)"),
):
    q: Dict[str, Any] = {}
    if tier:
        q["tier"] = tier
    cursor = _db.deep_funds.find(q).sort("rank", 1).limit(limit * 3)
    funds = []
    for f in cursor:
        roi_pub_obj = f.get("avgPublicRoi")
        roi_pub = roi_pub_obj.get("USD") if isinstance(roi_pub_obj, dict) else roi_pub_obj
        if minRoi is not None and (roi_pub is None or roi_pub < minRoi):
            continue
        funds.append({
            "id":               f.get("id"),
            "slug":             f.get("slug"),
            "name":             f.get("name"),
            "tier":             f.get("tier"),
            "rank":             f.get("rank"),
            "rating":           f.get("rating"),
            "country":          f.get("country"),
            "ventureType":      f.get("ventureType"),
            "twitterUrl":       f.get("twitterUrl"),
            "totalInvestments": f.get("totalInvestments"),
            "leadInvestments":  f.get("leadInvestments"),
            "avgPublicRoi":     roi_pub,
            "avgPrivateRoi":    (f.get("avgPrivateRoi") or {}).get("USD") if isinstance(f.get("avgPrivateRoi"), dict) else f.get("avgPrivateRoi"),
            "roundsPerYear":    f.get("roundsPerYear"),
            "portfolioCount":   f.get("portfolioCount"),
            "logo":             f.get("logo"),
            "description":      f.get("description"),
        })
        if len(funds) >= limit:
            break
    return {"ok": True, "count": len(funds), "funds": funds,
            "asOf": datetime.now(timezone.utc).isoformat(), "source": "deep_funds"}


@router.get("/persons")
async def deep_persons(
    limit: int = Query(50, ge=1, le=200),
    kind: Optional[str] = Query(None, description="'influencer' | 'fund_person' | 'project' | 'team'"),
    minScore: Optional[float] = Query(None),
    project: Optional[str] = Query(None, description="Filter by project_key"),
):
    q: Dict[str, Any] = {}
    if kind:
        q["kind"] = kind
    if project:
        q["project_key"] = project
    cursor = _db.deep_persons.find(q).sort("score", -1).limit(limit * 2)
    persons: List[Dict[str, Any]] = []
    seen_handles = set()
    for p in cursor:
        if minScore is not None and (p.get("score") or 0) < minScore:
            continue
        h = (p.get("handle") or "").lower()
        if h and h in seen_handles:
            continue
        if h:
            seen_handles.add(h)
        persons.append({
            "id":           p.get("id"),
            "handle":       p.get("handle"),
            "name":         p.get("name"),
            "kind":         p.get("kind"),
            "tag":          p.get("tag"),
            "score":        p.get("score"),
            "followers":    p.get("followers"),
            "avatar":       p.get("avatar"),
            "project":      p.get("project_name"),
            "projectKey":   p.get("project_key"),
        })
        if len(persons) >= limit:
            break
    return {"ok": True, "count": len(persons), "persons": persons,
            "asOf": datetime.now(timezone.utc).isoformat(), "source": "deep_persons"}


@router.get("/unlocks")
async def deep_unlocks(
    limit: int = Query(50, ge=1, le=200),
    phase: Optional[str] = Query(None, description="'past' or 'upcoming'"),
    symbol: Optional[str] = Query(None),
):
    q: Dict[str, Any] = {}
    if phase:
        q["phase"] = phase
    if symbol:
        q["symbol"] = symbol.upper()
    cursor = _db.deep_unlocks.find(q).limit(limit)
    unlocks = [_clean(u) for u in cursor]
    return {"ok": True, "count": len(unlocks), "unlocks": unlocks,
            "asOf": datetime.now(timezone.utc).isoformat(), "source": "deep_unlocks"}


@router.get("/projects/{slug}")
async def deep_project(slug: str):
    # Try exact key match in any source
    docs = list(_db.deep_projects.find({"project_key": slug}))
    if not docs:
        docs = list(_db.deep_projects.find({"name": {"$regex": f"^{slug}$", "$options": "i"}}))
    if not docs:
        raise HTTPException(404, f"No deep project for {slug}")
    # Merge multiple sources (cryptorank + icodrops + dropstab)
    merged: Dict[str, Any] = {"project_key": slug, "sources": []}
    for d in docs:
        d = _clean(d)
        merged["sources"].append(d.get("source"))
        for k, v in d.items():
            if k in merged and isinstance(merged[k], list) and isinstance(v, list):
                merged[k] = merged[k] + v
            elif k not in merged or not merged[k]:
                merged[k] = v
    # Related funding rounds
    merged["fundingRounds"] = [
        _clean(r) for r in _db.deep_funding_rounds.find({"project_key": slug})
    ]
    merged["persons"] = [
        _clean(p) for p in _db.deep_persons.find({"project_key": slug}).sort("score", -1).limit(40)
    ]
    merged["unlocks"] = [
        _clean(u) for u in _db.deep_unlocks.find({"project_key": slug})
    ]
    merged["events"] = [
        _clean(e) for e in _db.deep_project_events.find({"project_key": slug}).limit(40)
    ]
    return {"ok": True, "project": merged,
            "asOf": datetime.now(timezone.utc).isoformat(), "source": "deep_*_merged"}


@router.get("/projects")
async def deep_projects_list(limit: int = Query(50, ge=1, le=200)):
    cursor = _db.deep_projects.find({}).sort("investorCount", -1).limit(limit)
    items = []
    for d in cursor:
        d = _clean(d)
        items.append({
            "id":           d.get("id"),
            "source":       d.get("source"),
            "project_key":  d.get("project_key"),
            "name":         d.get("name"),
            "symbol":       d.get("symbol"),
            "category":     d.get("category"),
            "investorCount": d.get("investorCount", 0),
            "roundsCount":  d.get("roundsCount", 0),
            "unlockCount":  d.get("unlockCount", 0),
            "personCount":  d.get("personCount", 0),
            "totalRaised":  d.get("totalRaised"),
            "tgeDate":      d.get("tgeDate"),
            "nextUnlockDetails": d.get("nextUnlockDetails"),
            "icodropsHypeRate": d.get("icodropsHypeRate"),
            "icodropsRiskRate": d.get("icodropsRiskRate"),
            "icodropsRoiRate":  d.get("icodropsRoiRate"),
        })
    return {"ok": True, "count": len(items), "projects": items,
            "asOf": datetime.now(timezone.utc).isoformat(), "source": "deep_projects"}
