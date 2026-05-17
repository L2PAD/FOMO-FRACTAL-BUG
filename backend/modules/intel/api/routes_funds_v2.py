"""
FOMO Funds Layer - Full Model
==============================
Complete fund model for Graph Engine with team, portfolio, performance.

Collections:
- intel_funds (core - replaces simple intel_investors)
- fund_people (partners/team)
- fund_investments (individual deals)
- fund_portfolio_snapshot (aggregated for UI)

Endpoints:
- GET /api/funds - List funds
- GET /api/funds/{id} - Profile
- GET /api/funds/{id}/portfolio - Full portfolio
- GET /api/funds/{id}/investments - Individual deals
- GET /api/funds/{id}/people - Partners/team
- GET /api/funds/{id}/coinvestors - Co-investor network
- GET /api/funds/{id}/scores - Performance scores
- GET /api/funds/{id}/network - Graph data
- GET /api/funds/leaderboard - Rankings
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/funds", tags=["Funds / VCs"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# Tier 1 VC names
TIER1_FUNDS = {
    "a16z", "andreessen horowitz", "paradigm", "sequoia", "polychain",
    "multicoin", "coinbase ventures", "binance labs", "pantera",
    "dragonfly", "framework", "electric capital", "placeholder",
    "variant", "haun ventures", "galaxy digital"
}


def calculate_fund_tier(name: str, deals: int, aum: float = 0) -> int:
    """Determine fund tier (1-4)"""
    name_lower = name.lower()
    
    # Check if known tier 1
    if any(t in name_lower for t in TIER1_FUNDS):
        return 1
    
    # AUM-based
    if aum and aum > 1_000_000_000:
        return 1
    elif aum and aum > 100_000_000:
        return 2
    
    # Deal count based
    if deals > 100:
        return 1
    elif deals > 50:
        return 2
    elif deals > 10:
        return 3
    
    return 4


def calculate_fund_scores(fund: dict, investments: list) -> dict:
    """
    Calculate fund scores (0-100).
    
    Components:
    - influence_score: deal flow, lead rate, network
    - performance_score: listing success, ROI, survival
    - deal_flow_score: activity level
    - credibility_score: source coverage, history
    """
    scores = {}
    
    # Deal flow score
    deals_count = len(investments)
    recent_deals = sum(1 for inv in investments if inv.get("date") and inv.get("date") > ts_now() - 90*24*60*60*1000)
    scores["deal_flow"] = min(deals_count + recent_deals * 5, 100)
    
    # Lead rate
    lead_count = sum(1 for inv in investments if inv.get("role") == "lead")
    scores["lead_rate"] = min(lead_count / max(deals_count, 1) * 100, 100)
    
    # Influence
    scores["influence"] = min(
        scores["deal_flow"] * 0.5 + scores["lead_rate"] * 0.5,
        100
    )
    
    # Performance (placeholder - would need exit data)
    scores["performance"] = 50  # Default neutral
    
    # Credibility
    sources = fund.get("sources", [])
    scores["credibility"] = min(len(sources) * 25 + 50, 100)
    
    # Overall
    scores["overall"] = round(
        scores["influence"] * 0.35 +
        scores["performance"] * 0.30 +
        scores["deal_flow"] * 0.20 +
        scores["credibility"] * 0.15
    )
    
    return scores


def estimate_roi(entry_date: int, current_price: float = None) -> dict:
    """Estimate ROI for investment"""
    if not entry_date:
        return {"level": "C", "multiple": 1.0, "confidence": 0.2}
    
    now = ts_now()
    days = (now - entry_date) / (1000 * 60 * 60 * 24)
    
    # Time-based proxy
    if days > 730:  # 2+ years
        multiple = 2.5
    elif days > 365:
        multiple = 1.5
    elif days > 180:
        multiple = 1.2
    else:
        multiple = 1.0
    
    return {"level": "C", "multiple": round(multiple, 2), "confidence": 0.35}


# ═══════════════════════════════════════════════════════════════
# FUNDS LIST
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_funds(
    search: str = Query(None, description="Search by name"),
    tier: int = Query(None, description="Filter by tier: 1, 2, 3, 4"),
    type: str = Query(None, description="Filter by type: vc, hedge, exchange, angel"),
    stage: str = Query(None, description="Filter by stage focus: seed, private, series_a"),
    sector: str = Query(None, description="Filter by sector focus: defi, infra, gaming"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all funds with comprehensive filtering.
    """
    from server import db
    
    skip = (page - 1) * limit
    
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"slug": {"$regex": search, "$options": "i"}}
        ]
    if tier:
        query["tier"] = tier
    if type:
        query["type"] = type
    if stage:
        query["stage_focus"] = {"$in": [stage]}
    if sector:
        query["sector_focus"] = {"$in": [sector]}
    
    # Try intel_investors first (main collection), fallback to intel_funds
    cursor = db.intel_investors.find(query).sort("influence_score", -1).skip(skip).limit(limit)
    funds = await cursor.to_list(limit)
    total = await db.intel_investors.count_documents(query)
    
    # If empty, try intel_funds as fallback
    if not funds:
        cursor = db.intel_funds.find(query).sort("influence_score", -1).skip(skip).limit(limit)
        funds = await cursor.to_list(limit)
        total = await db.intel_funds.count_documents(query)
    
    items = []
    for fund in funds:
        tier_val = fund.get("tier") or calculate_fund_tier(
            fund.get("name", ""),
            fund.get("investments_count", 0),
            fund.get("aum_usd", 0)
        )
        
        items.append({
            "id": fund.get("id", str(fund.get("_id", ""))),
            "name": fund.get("name", ""),
            "slug": fund.get("slug", ""),
            "logo": fund.get("logo", fund.get("logo_url", "")),
            "type": fund.get("type", "vc"),
            "tier": tier_val,
            "hq_location": fund.get("hq_location", fund.get("region", "")),
            "founded_year": fund.get("founded_year"),
            "aum_usd": fund.get("aum_usd"),
            "portfolio_size": fund.get("portfolio_size", fund.get("investments_count", 0)),
            "stage_focus": fund.get("stage_focus", []),
            "sector_focus": fund.get("sector_focus", []),
            "scores": {
                "influence": fund.get("influence_score", 0),
                "performance": fund.get("performance_score", 0)
            },
            "activity": {
                "last_deal_at": fund.get("last_deal_at"),
                "deals_30d": fund.get("deals_30d", 0)
            }
        })
    
    return {
        "ts": ts_now(),
        "page": page,
        "limit": limit,
        "total": total,
        "items": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# FUND PROFILE
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}")
async def get_fund_profile(fund_id: str):
    """
    Get comprehensive fund profile.
    """
    from server import db
    
    # Try intel_funds first
    fund = await db.intel_funds.find_one({
        "$or": [{"id": fund_id}, {"slug": fund_id}]
    })
    
    # Fallback to intel_investors
    if not fund:
        fund = await db.intel_investors.find_one({
            "$or": [{"id": fund_id}, {"slug": fund_id}]
        })
    
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_name = fund.get("name", "")
    
    # Get investments
    cursor = db.intel_funding.find({
        "investors": {"$regex": fund_name, "$options": "i"}
    })
    investments = await cursor.to_list(200)
    
    # Calculate tier
    tier = fund.get("tier") or calculate_fund_tier(
        fund_name,
        len(investments),
        fund.get("aum_usd", 0)
    )
    
    # Calculate scores
    scores = calculate_fund_scores(fund, investments)
    
    # Get categories breakdown
    categories = {}
    stages = {}
    for inv in investments:
        cat = inv.get("category", "other") or "other"
        categories[cat] = categories.get(cat, 0) + 1
        
        stage = inv.get("round_type", "other") or "other"
        stages[stage] = stages.get(stage, 0) + 1
    
    return {
        "ts": ts_now(),
        "fund": {
            "id": fund.get("id", str(fund.get("_id", ""))),
            "name": fund_name,
            "legal_name": fund.get("legal_name"),
            "slug": fund.get("slug"),
            "logo": fund.get("logo", fund.get("logo_url")),
            "description": fund.get("description", ""),
            "type": fund.get("type", "vc"),
            "category": fund.get("category", "crypto"),
            "tier": tier,
            "hq_location": fund.get("hq_location", fund.get("region")),
            "founded_year": fund.get("founded_year"),
            "website": fund.get("website"),
            "social": {
                "twitter": fund.get("twitter"),
                "linkedin": fund.get("linkedin"),
                "telegram": fund.get("telegram")
            }
        },
        "stats": {
            "aum_usd": fund.get("aum_usd"),
            "funds_count": fund.get("funds_count"),
            "portfolio_size": len(investments),
            "total_invested_usd": sum(inv.get("raised_usd", 0) or 0 for inv in investments)
        },
        "focus": {
            "stage_focus": fund.get("stage_focus", list(stages.keys())[:3]),
            "sector_focus": fund.get("sector_focus", list(categories.keys())[:5]),
            "geo_focus": fund.get("geo_focus", [])
        },
        "activity": {
            "last_deal_at": investments[0].get("round_date") if investments else None,
            "deals_30d": sum(1 for inv in investments if inv.get("round_date") and inv.get("round_date") > ts_now() - 30*24*60*60*1000),
            "deals_90d": sum(1 for inv in investments if inv.get("round_date") and inv.get("round_date") > ts_now() - 90*24*60*60*1000)
        },
        "scores": scores,
        "distributions": {
            "by_category": [{"category": k, "count": v} for k, v in sorted(categories.items(), key=lambda x: -x[1])[:10]],
            "by_stage": [{"stage": k, "count": v} for k, v in sorted(stages.items(), key=lambda x: -x[1])]
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# FUND PORTFOLIO
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/portfolio")
async def get_fund_portfolio(
    fund_id: str,
    sort: str = Query("date", description="Sort: date, roi, amount"),
    status: str = Query("all", description="Status: all, active, exited"),
    limit: int = Query(100, ge=1, le=200)
):
    """
    Get fund's full portfolio with ROI estimates.
    """
    from server import db
    
    # Get fund
    fund = await db.intel_funds.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    if not fund:
        fund = await db.intel_investors.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_name = fund.get("name", "")
    
    # Get investments
    cursor = db.intel_funding.find({
        "investors": {"$regex": fund_name, "$options": "i"}
    }).sort("round_date", -1).limit(limit)
    
    rounds = await cursor.to_list(limit)
    
    portfolio = []
    total_invested = 0
    total_value = 0
    winners = 0
    
    for funding_round in rounds:
        # Get project
        project = await db.intel_projects.find_one({"key": funding_round.get("project_key")})
        
        # Estimate investment
        raised = funding_round.get("raised_usd", 0) or 0
        investor_count = len(funding_round.get("investors", [])) or 1
        estimated_amount = raised / investor_count
        
        # Check if lead
        is_lead = fund_name.lower() in [l.lower() for l in funding_round.get("lead_investors", [])]
        if is_lead:
            estimated_amount *= 2
        
        # Calculate ROI
        roi = estimate_roi(funding_round.get("round_date"))
        estimated_value = estimated_amount * roi["multiple"]
        
        total_invested += estimated_amount
        total_value += estimated_value
        
        if roi["multiple"] >= 1:
            winners += 1
        
        # Determine status
        inv_status = "active"
        if roi["multiple"] < 0.5:
            inv_status = "underwater"
        elif funding_round.get("exited"):
            inv_status = "exited"
        
        if status != "all" and inv_status != status:
            continue
        
        portfolio.append({
            "project": {
                "key": funding_round.get("project_key"),
                "name": project.get("name") if project else funding_round.get("project"),
                "symbol": funding_round.get("symbol"),
                "logo": project.get("logo_url") if project else None,
                "category": project.get("category") if project else funding_round.get("category")
            },
            "investment": {
                "round_id": funding_round.get("id"),
                "round_type": funding_round.get("round_type"),
                "date": funding_round.get("round_date"),
                "valuation": funding_round.get("valuation_usd"),
                "estimated_amount": round(estimated_amount, 2),
                "is_lead": is_lead,
                "co_investors": [inv for inv in funding_round.get("investors", []) if inv.lower() != fund_name.lower()][:5]
            },
            "roi": {
                "level": roi["level"],
                "multiple": roi["multiple"],
                "estimated_value": round(estimated_value, 2),
                "pnl": round(estimated_value - estimated_amount, 2),
                "confidence": roi["confidence"]
            },
            "status": inv_status
        })
    
    # Sort
    if sort == "roi":
        portfolio.sort(key=lambda x: x["roi"]["multiple"], reverse=True)
    elif sort == "amount":
        portfolio.sort(key=lambda x: x["investment"]["estimated_amount"], reverse=True)
    
    win_rate = winners / len(portfolio) * 100 if portfolio else 0
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": fund_name,
        "summary": {
            "portfolio_count": len(portfolio),
            "total_invested_usd": round(total_invested, 2),
            "total_value_usd": round(total_value, 2),
            "total_pnl_usd": round(total_value - total_invested, 2),
            "overall_multiple": round(total_value / total_invested, 2) if total_invested > 0 else 1.0,
            "win_rate_pct": round(win_rate, 1),
            "roi_level": "C",
            "confidence": 0.35
        },
        "portfolio": portfolio,
        "_meta": {"cache_sec": 300, "note": "ROI estimates use proxy method (Level C)"}
    }


# ═══════════════════════════════════════════════════════════════
# FUND DASHBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/dashboard")
async def get_fund_dashboard(fund_id: str):
    """
    Get fund dashboard with aggregated metrics.
    """
    # Get portfolio data
    portfolio_data = await get_fund_portfolio(fund_id, sort="roi", limit=100)
    
    portfolio = portfolio_data.get("portfolio", [])
    summary = portfolio_data.get("summary", {})
    
    # Find top gainer and loser
    top_gainer = None
    top_loser = None
    
    if portfolio:
        sorted_by_roi = sorted(portfolio, key=lambda x: x["roi"]["multiple"], reverse=True)
        if sorted_by_roi:
            top_gainer = {
                "project": sorted_by_roi[0]["project"]["name"],
                "symbol": sorted_by_roi[0]["project"]["symbol"],
                "multiple": sorted_by_roi[0]["roi"]["multiple"]
            }
            top_loser = {
                "project": sorted_by_roi[-1]["project"]["name"],
                "symbol": sorted_by_roi[-1]["project"]["symbol"],
                "multiple": sorted_by_roi[-1]["roi"]["multiple"]
            }
    
    # Category distribution
    categories = {}
    for p in portfolio:
        cat = p["project"].get("category", "other") or "other"
        if cat not in categories:
            categories[cat] = {"count": 0, "invested": 0, "value": 0}
        categories[cat]["count"] += 1
        categories[cat]["invested"] += p["investment"]["estimated_amount"]
        categories[cat]["value"] += p["roi"]["estimated_value"]
    
    category_distribution = [
        {
            "category": k,
            "count": v["count"],
            "invested_usd": round(v["invested"], 2),
            "value_usd": round(v["value"], 2),
            "pct": round(v["invested"] / summary.get("total_invested_usd", 1) * 100, 1) if summary.get("total_invested_usd", 0) > 0 else 0
        }
        for k, v in sorted(categories.items(), key=lambda x: -x[1]["invested"])
    ]
    
    # Stage distribution
    stages = {}
    for p in portfolio:
        stage = p["investment"].get("round_type", "other") or "other"
        stages[stage] = stages.get(stage, 0) + 1
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": portfolio_data.get("fund_name"),
        "metrics": {
            "current_value_usd": summary.get("total_value_usd", 0),
            "total_invested_usd": summary.get("total_invested_usd", 0),
            "unrealized_pnl_usd": summary.get("total_pnl_usd", 0),
            "realized_pnl_usd": 0,  # Would need exit data
            "overall_multiple": summary.get("overall_multiple", 1.0),
            "win_rate_pct": summary.get("win_rate_pct", 0)
        },
        "highlights": {
            "top_gainer": top_gainer,
            "top_loser": top_loser,
            "total_investments": summary.get("portfolio_count", 0)
        },
        "distributions": {
            "by_category": category_distribution,
            "by_stage": [
                {"stage": k, "count": v, "pct": round(v / len(portfolio) * 100, 1) if portfolio else 0}
                for k, v in sorted(stages.items(), key=lambda x: -x[1])
            ]
        },
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# FUND INVESTMENTS (Individual deals)
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/investments")
async def get_fund_investments(
    fund_id: str,
    from_date: str = Query(None, description="From date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="To date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get fund's individual investment deals.
    """
    from server import db
    
    fund = await db.intel_funds.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    if not fund:
        fund = await db.intel_investors.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_name = fund.get("name", "")
    
    # Build query
    query = {"investors": {"$regex": fund_name, "$options": "i"}}
    
    if from_date:
        try:
            from_ts = int(datetime.fromisoformat(from_date).timestamp() * 1000)
            query["round_date"] = {"$gte": from_ts}
        except:
            pass
    
    if to_date:
        try:
            to_ts = int(datetime.fromisoformat(to_date).timestamp() * 1000)
            if "round_date" in query:
                query["round_date"]["$lte"] = to_ts
            else:
                query["round_date"] = {"$lte": to_ts}
        except:
            pass
    
    cursor = db.intel_funding.find(query).sort("round_date", -1).limit(limit)
    rounds = await cursor.to_list(limit)
    
    investments = []
    for funding_round in rounds:
        is_lead = fund_name.lower() in [l.lower() for l in funding_round.get("lead_investors", [])]
        
        investments.append({
            "round_id": funding_round.get("id"),
            "project": funding_round.get("project"),
            "project_key": funding_round.get("project_key"),
            "symbol": funding_round.get("symbol"),
            "round_type": funding_round.get("round_type"),
            "date": funding_round.get("round_date"),
            "raised_usd": funding_round.get("raised_usd"),
            "valuation_usd": funding_round.get("valuation_usd"),
            "role": "lead" if is_lead else "participant",
            "co_investors_count": len(funding_round.get("investors", [])) - 1
        })
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": fund_name,
        "investments_count": len(investments),
        "investments": investments,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# FUND PEOPLE (Partners/Team)
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/people")
async def get_fund_people(fund_id: str):
    """
    Get fund's partners and team members.
    """
    from server import db
    
    fund = await db.intel_funds.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    if not fund:
        fund = await db.intel_investors.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_key = fund.get("id", fund_id)
    
    # Get from fund_people collection
    people = []
    try:
        cursor = db.fund_people.find({"fund_id": fund_key})
        people = await cursor.to_list(50)
    except:
        pass
    
    # If no stored data, try to find from persons
    if not people:
        cursor = db.intel_persons.find({
            "$or": [
                {"current_company": {"$regex": fund.get("name", ""), "$options": "i"}},
                {"projects": fund_key}
            ]
        })
        persons = await cursor.to_list(20)
        
        for person in persons:
            people.append({
                "person_id": person.get("key"),
                "name": person.get("name"),
                "photo": person.get("photo_url"),
                "role": person.get("current_position", person.get("role", "Team Member")),
                "is_current": True,
                "twitter": person.get("twitter"),
                "linkedin": person.get("linkedin")
            })
    else:
        # Format stored data
        formatted = []
        for p in people:
            person = await db.intel_persons.find_one({"key": p.get("person_id")})
            formatted.append({
                "person_id": p.get("person_id"),
                "name": person.get("name") if person else p.get("person_id"),
                "photo": person.get("photo_url") if person else None,
                "role": p.get("role", "Partner"),
                "is_current": p.get("is_current", True),
                "start_date": p.get("start_date"),
                "twitter": person.get("twitter") if person else None
            })
        people = formatted
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": fund.get("name"),
        "team_count": len(people),
        "team": people,
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# CO-INVESTORS
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/coinvestors")
async def get_fund_coinvestors(fund_id: str, limit: int = Query(30, ge=1, le=50)):
    """
    Get fund's co-investor network.
    """
    from server import db
    
    fund = await db.intel_funds.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    if not fund:
        fund = await db.intel_investors.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_name = fund.get("name", "")
    
    # Get all rounds with this fund
    cursor = db.intel_funding.find({
        "investors": {"$regex": fund_name, "$options": "i"}
    })
    rounds = await cursor.to_list(500)
    
    # Count co-investors
    coinvestors = {}
    for funding_round in rounds:
        for investor in funding_round.get("investors", []):
            if investor.lower() != fund_name.lower():
                key = investor.lower()
                if key not in coinvestors:
                    coinvestors[key] = {
                        "name": investor,
                        "deals_together": 0,
                        "projects": [],
                        "as_lead": 0,
                        "as_participant": 0
                    }
                coinvestors[key]["deals_together"] += 1
                
                project = funding_round.get("project_key") or funding_round.get("project")
                if project and project not in coinvestors[key]["projects"]:
                    coinvestors[key]["projects"].append(project)
                
                # Track lead/participant
                if investor in funding_round.get("lead_investors", []):
                    coinvestors[key]["as_lead"] += 1
                else:
                    coinvestors[key]["as_participant"] += 1
    
    # Sort and format
    sorted_coinvestors = sorted(
        coinvestors.values(),
        key=lambda x: x["deals_together"],
        reverse=True
    )[:limit]
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": fund_name,
        "total_rounds": len(rounds),
        "coinvestors_count": len(coinvestors),
        "coinvestors": [
            {
                "name": c["name"],
                "deals_together": c["deals_together"],
                "projects": c["projects"][:5],
                "lead_rate": round(c["as_lead"] / c["deals_together"] * 100, 1) if c["deals_together"] > 0 else 0,
                "tier": calculate_fund_tier(c["name"], c["deals_together"], 0)
            }
            for c in sorted_coinvestors
        ],
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# FUND SCORES
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/scores")
async def get_fund_scores(fund_id: str):
    """
    Get fund's performance scores and metrics.
    """
    from server import db
    
    fund = await db.intel_funds.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    if not fund:
        fund = await db.intel_investors.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_name = fund.get("name", "")
    
    # Get investments
    cursor = db.intel_funding.find({
        "investors": {"$regex": fund_name, "$options": "i"}
    })
    investments = await cursor.to_list(500)
    
    # Calculate scores
    scores = calculate_fund_scores(fund, investments)
    
    # Calculate tier
    tier = calculate_fund_tier(fund_name, len(investments), fund.get("aum_usd", 0))
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": fund_name,
        "tier": tier,
        "scores": {
            "overall": scores["overall"],
            "influence": round(scores["influence"]),
            "performance": scores["performance"],
            "deal_flow": round(scores["deal_flow"]),
            "credibility": round(scores["credibility"]),
            "lead_rate": round(scores["lead_rate"])
        },
        "metrics": {
            "total_deals": len(investments),
            "lead_deals": sum(1 for inv in investments if fund_name.lower() in [l.lower() for l in inv.get("lead_investors", [])]),
            "avg_deal_size": sum(inv.get("raised_usd", 0) or 0 for inv in investments) / len(investments) / len(investments[0].get("investors", [1])) if investments else 0
        },
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# FUND SKILL SCORE (ROI Engine)
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/skill-score")
async def get_fund_skill_score(fund_id: str):
    """
    Get fund's Skill Score using ROI Engine.
    
    Skill Score formula:
    - 40% investment_success (weighted avg ROI)
    - 25% pick_rate (% with positive returns)
    - 20% consistency (std dev of returns)
    - 15% timing (early stage premium)
    """
    from server import db
    from modules.intel.roi_engine import roi_engine
    
    fund = await db.intel_funds.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    if not fund:
        fund = await db.intel_investors.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_name = fund.get("name", "")
    
    # Get investments
    cursor = db.intel_funding.find({
        "investors": {"$regex": fund_name, "$options": "i"}
    })
    rounds = await cursor.to_list(500)
    
    # Transform to investment format for ROI engine
    investments = []
    for r in rounds:
        investments.append({
            "date": r.get("round_date"),
            "round_type": r.get("round_type"),
            "category": r.get("category"),
            "valuation": r.get("valuation_usd"),
            "project": r.get("project"),
            "symbol": r.get("symbol")
        })
    
    # Calculate skill score
    skill = roi_engine.calculate_skill_score(investments)
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": fund_name,
        "skill_score": skill,
        "roi_methodology": {
            "levels": {
                "A": "Realized - actual entry/exit prices",
                "B": "Mark-to-Market - valuation comparison",
                "C": "Proxy - time-based heuristics"
            },
            "current_level": "C",
            "note": "Level A/B requires price/FDV data integration"
        },
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# FUND NETWORK (Graph data)
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/network")
async def get_fund_network(fund_id: str, depth: int = Query(1, ge=1, le=2)):
    """
    Get fund's network graph for visualization.
    """
    from server import db
    
    fund = await db.intel_funds.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    if not fund:
        fund = await db.intel_investors.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_name = fund.get("name", "")
    fund_key = fund.get("id", fund_id)
    
    nodes = []
    edges = []
    
    # Add fund as central node
    nodes.append({
        "id": fund_key,
        "type": "fund",
        "label": fund_name,
        "logo": fund.get("logo", fund.get("logo_url")),
        "tier": fund.get("tier", 3)
    })
    
    # Get investments
    cursor = db.intel_funding.find({
        "investors": {"$regex": fund_name, "$options": "i"}
    }).limit(20)
    investments = await cursor.to_list(20)
    
    # Add projects
    for inv in investments:
        proj_key = inv.get("project_key") or inv.get("project")
        project = await db.intel_projects.find_one({"key": proj_key})
        
        nodes.append({
            "id": proj_key,
            "type": "project",
            "label": project.get("name") if project else inv.get("project"),
            "logo": project.get("logo_url") if project else None,
            "symbol": inv.get("symbol")
        })
        edges.append({
            "source": fund_key,
            "target": proj_key,
            "relation": "invested_in"
        })
    
    # Add top co-investors
    coinvestors_data = await get_fund_coinvestors(fund_id, limit=5)
    for coinv in coinvestors_data.get("coinvestors", [])[:5]:
        coinv_id = coinv["name"].lower().replace(" ", "_")
        nodes.append({
            "id": coinv_id,
            "type": "fund",
            "label": coinv["name"],
            "tier": coinv["tier"]
        })
        edges.append({
            "source": fund_key,
            "target": coinv_id,
            "relation": "coinvestor",
            "weight": coinv["deals_together"]
        })
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": fund_name,
        "depth": depth,
        "graph": {
            "nodes": nodes,
            "edges": edges,
            "nodes_count": len(nodes),
            "edges_count": len(edges)
        },
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# LEADERBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/leaderboard/{metric}")
async def get_funds_leaderboard(
    metric: str,
    tier: int = Query(None, description="Filter by tier"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get funds leaderboard by metric.
    
    Metrics: influence, performance, deal_flow, portfolio_size
    """
    from server import db
    
    # Determine sort field
    sort_map = {
        "influence": "influence_score",
        "performance": "performance_score",
        "deal_flow": "deals_30d",
        "portfolio_size": "investments_count"
    }
    sort_field = sort_map.get(metric, "investments_count")
    
    query = {}
    if tier:
        query["tier"] = tier
    
    # Try intel_investors first (main collection), fallback to intel_funds
    cursor = db.intel_investors.find(query).sort(sort_field, -1).limit(limit)
    funds = await cursor.to_list(limit)
    
    # If empty, try intel_funds as fallback
    if not funds:
        cursor = db.intel_funds.find(query).sort(sort_field, -1).limit(limit)
        funds = await cursor.to_list(limit)
    
    leaderboard = []
    for i, fund in enumerate(funds):
        tier_val = fund.get("tier") or calculate_fund_tier(
            fund.get("name", ""),
            fund.get("investments_count", 0),
            fund.get("aum_usd", 0)
        )
        
        leaderboard.append({
            "rank": i + 1,
            "fund": {
                "id": fund.get("id", str(fund.get("_id", ""))),
                "name": fund.get("name"),
                "slug": fund.get("slug"),
                "logo": fund.get("logo", fund.get("logo_url")),
                "tier": tier_val
            },
            "metrics": {
                "influence_score": fund.get("influence_score", 0),
                "performance_score": fund.get("performance_score", 0),
                "portfolio_size": fund.get("investments_count", 0),
                "deals_30d": fund.get("deals_30d", 0)
            }
        })
    
    return {
        "ts": ts_now(),
        "metric": metric,
        "leaderboard": leaderboard,
        "_meta": {"cache_sec": 600}
    }
