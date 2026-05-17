"""
FOMO Funds (VC) Analytics API
=============================
Fund profiles, portfolios, ROI calculations, and leaderboards.

Endpoints:
- GET /api/funds - List all funds
- GET /api/funds/{fundId} - Fund profile
- GET /api/funds/{fundId}/portfolio - Fund portfolio
- GET /api/funds/{fundId}/dashboard - Fund dashboard metrics
- GET /api/funds/{fundId}/coinvestors - Co-investor network
- GET /api/funds/{fundId}/performance - Fund performance metrics
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import asyncio

router = APIRouter(prefix="/api/funds", tags=["Funds / VCs"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# Tier classification
TIER1_FUNDS = {
    "a16z", "andreessen horowitz", "paradigm", "sequoia", "polychain",
    "multicoin", "coinbase ventures", "binance labs", "pantera",
    "dragonfly", "framework", "electric capital", "placeholder",
    "variant", "haun ventures", "galaxy digital"
}


def calculate_fund_tier(name: str, investments: int) -> str:
    """Determine fund tier based on name and activity"""
    name_lower = name.lower()
    
    if any(t in name_lower for t in TIER1_FUNDS):
        return "tier_1"
    elif investments > 50:
        return "tier_2"
    elif investments > 10:
        return "tier_3"
    else:
        return "other"


def estimate_roi(entry_date: int, current_price: float, entry_valuation: float = None) -> dict:
    """
    Estimate ROI for an investment.
    
    Returns:
    - roi_level: A (realized), B (mark-to-market), C (proxy)
    - multiple: Current value / invested
    - confidence: 0.0 - 1.0
    """
    # Default proxy ROI calculation
    # In real implementation, this would use actual price data
    
    if not entry_date:
        return {"roi_level": "C", "multiple": 1.0, "confidence": 0.2}
    
    # Estimate based on time since entry
    now = ts_now()
    days_since_entry = (now - entry_date) / (1000 * 60 * 60 * 24)
    
    # Simple proxy: assume average crypto growth
    # This is placeholder - real implementation uses actual prices
    if days_since_entry > 730:  # 2+ years
        estimated_multiple = 2.5
    elif days_since_entry > 365:  # 1-2 years
        estimated_multiple = 1.5
    elif days_since_entry > 180:  # 6-12 months
        estimated_multiple = 1.2
    else:
        estimated_multiple = 1.0
    
    return {
        "roi_level": "C",  # Proxy level
        "multiple": round(estimated_multiple, 2),
        "confidence": 0.35,
        "method": "time_proxy"
    }


# ═══════════════════════════════════════════════════════════════
# FUNDS LIST
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_funds(
    search: str = Query(None, description="Search by name"),
    region: str = Query(None, description="Filter by region"),
    tier: str = Query(None, description="Filter by tier"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all funds with basic info.
    """
    from server import db
    
    skip = (page - 1) * limit
    
    # Build query
    query = {}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"slug": {"$regex": search, "$options": "i"}}
        ]
    
    if region:
        query["region"] = {"$regex": region, "$options": "i"}
    
    # Get funds from investors collection
    cursor = db.intel_investors.find(query).sort("investments_count", -1).skip(skip).limit(limit)
    funds = await cursor.to_list(limit)
    
    total = await db.intel_investors.count_documents(query)
    
    items = []
    for fund in funds:
        fund_tier = calculate_fund_tier(fund.get("name", ""), fund.get("investments_count", 0))
        
        # Skip if tier filter doesn't match
        if tier and fund_tier != tier:
            continue
        
        items.append({
            "id": fund.get("id", str(fund.get("_id", ""))),
            "name": fund.get("name", ""),
            "slug": fund.get("slug", ""),
            "logo": fund.get("logo_url", ""),
            "tier": fund_tier,
            "region": fund.get("region", ""),
            "website": fund.get("website", ""),
            "twitter": fund.get("twitter", ""),
            "investments_count": fund.get("investments_count", 0),
            "portfolio_preview": fund.get("portfolio", [])[:5]
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
    Get detailed fund profile.
    """
    from server import db
    
    # Try to find by id or slug
    fund = await db.intel_investors.find_one({"id": fund_id})
    if not fund:
        fund = await db.intel_investors.find_one({"slug": fund_id})
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund.pop("_id", None)
    fund.pop("raw_data", None)
    
    fund_tier = calculate_fund_tier(fund.get("name", ""), fund.get("investments_count", 0))
    
    # Get portfolio projects
    portfolio_keys = fund.get("portfolio", [])
    
    # Get funding rounds where this fund invested
    cursor = db.intel_funding.find({
        "investors": {"$regex": fund.get("name", ""), "$options": "i"}
    })
    rounds = await cursor.to_list(100)
    
    # Calculate basic stats
    total_invested = sum(r.get("raised_usd", 0) or 0 for r in rounds)
    categories = {}
    for r in rounds:
        cat = r.get("category", "other") or "other"
        categories[cat] = categories.get(cat, 0) + 1
    
    return {
        "ts": ts_now(),
        "fund": {
            "id": fund.get("id"),
            "name": fund.get("name"),
            "slug": fund.get("slug"),
            "logo": fund.get("logo_url"),
            "tier": fund_tier,
            "category": fund.get("category", "venture"),
            "region": fund.get("region"),
            "website": fund.get("website"),
            "twitter": fund.get("twitter"),
            "description": fund.get("description", "")
        },
        "stats": {
            "investments_count": len(rounds),
            "portfolio_size": len(portfolio_keys),
            "total_invested_usd": total_invested,
            "categories": [
                {"category": k, "count": v}
                for k, v in sorted(categories.items(), key=lambda x: -x[1])
            ]
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
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get fund portfolio with investment details and ROI estimates.
    """
    from server import db
    
    # Get fund
    fund = await db.intel_investors.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_name = fund.get("name", "")
    
    # Get all funding rounds where this fund invested
    cursor = db.intel_funding.find({
        "investors": {"$regex": fund_name, "$options": "i"}
    }).sort("round_date", -1).limit(limit)
    
    rounds = await cursor.to_list(limit)
    
    portfolio = []
    total_invested = 0
    total_value = 0
    
    for funding_round in rounds:
        # Get project info
        project = await db.intel_projects.find_one({"key": funding_round.get("project_key")})
        
        # Estimate investment amount (average per investor)
        raised = funding_round.get("raised_usd", 0) or 0
        investor_count = len(funding_round.get("investors", [])) or 1
        estimated_amount = raised / investor_count
        
        # Is this fund a lead investor?
        is_lead = fund_name.lower() in [l.lower() for l in funding_round.get("lead_investors", [])]
        if is_lead:
            estimated_amount *= 2  # Leads typically invest more
        
        # Calculate ROI estimate
        roi = estimate_roi(funding_round.get("round_date"), 0)
        
        estimated_value = estimated_amount * roi["multiple"]
        total_invested += estimated_amount
        total_value += estimated_value
        
        portfolio.append({
            "project": {
                "key": funding_round.get("project_key"),
                "name": project.get("name") if project else funding_round.get("project"),
                "symbol": funding_round.get("symbol"),
                "logo": project.get("logo_url") if project else None,
                "category": project.get("category") if project else funding_round.get("category")
            },
            "round": {
                "id": funding_round.get("id"),
                "type": funding_round.get("round_type"),
                "date": funding_round.get("round_date"),
                "valuation": funding_round.get("valuation_usd")
            },
            "investment": {
                "estimated_amount": round(estimated_amount, 2),
                "is_lead": is_lead,
                "co_investors": [inv for inv in funding_round.get("investors", []) if inv.lower() != fund_name.lower()][:5]
            },
            "roi": {
                "level": roi["roi_level"],
                "multiple": roi["multiple"],
                "estimated_value": round(estimated_value, 2),
                "pnl": round(estimated_value - estimated_amount, 2),
                "confidence": roi["confidence"]
            },
            "status": "active" if roi["multiple"] >= 1 else "underwater"
        })
    
    # Sort
    if sort == "roi":
        portfolio.sort(key=lambda x: x["roi"]["multiple"], reverse=True)
    elif sort == "amount":
        portfolio.sort(key=lambda x: x["investment"]["estimated_amount"], reverse=True)
    
    # Calculate win rate
    winners = sum(1 for p in portfolio if p["roi"]["multiple"] >= 1)
    win_rate = winners / len(portfolio) * 100 if portfolio else 0
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": fund_name,
        "summary": {
            "total_investments": len(portfolio),
            "total_invested_usd": round(total_invested, 2),
            "total_value_usd": round(total_value, 2),
            "total_pnl_usd": round(total_value - total_invested, 2),
            "overall_multiple": round(total_value / total_invested, 2) if total_invested > 0 else 1.0,
            "win_rate_pct": round(win_rate, 1)
        },
        "portfolio": portfolio,
        "_meta": {"cache_sec": 300, "roi_note": "ROI is estimated using proxy method (Level C)"}
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
    
    portfolio = portfolio_data["portfolio"]
    summary = portfolio_data["summary"]
    
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
            "pct": round(v["invested"] / summary["total_invested_usd"] * 100, 1) if summary["total_invested_usd"] > 0 else 0
        }
        for k, v in sorted(categories.items(), key=lambda x: -x[1]["invested"])
    ]
    
    # Stage distribution
    stages = {}
    for p in portfolio:
        stage = p["round"]["type"] or "other"
        stages[stage] = stages.get(stage, 0) + 1
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": portfolio_data["fund_name"],
        "metrics": {
            "current_value_usd": summary["total_value_usd"],
            "total_invested_usd": summary["total_invested_usd"],
            "unrealized_pnl_usd": summary["total_pnl_usd"],
            "realized_pnl_usd": 0,  # Would need exit data
            "overall_multiple": summary["overall_multiple"],
            "win_rate_pct": summary["win_rate_pct"]
        },
        "highlights": {
            "top_gainer": top_gainer,
            "top_loser": top_loser,
            "total_investments": summary["total_investments"]
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
# CO-INVESTORS
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/coinvestors")
async def get_fund_coinvestors(fund_id: str, limit: int = Query(20, ge=1, le=50)):
    """
    Get fund's co-investor network.
    """
    from server import db
    
    # Get fund
    fund = await db.intel_investors.find_one({"$or": [{"id": fund_id}, {"slug": fund_id}]})
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")
    
    fund_name = fund.get("name", "")
    
    # Get all rounds with this fund
    cursor = db.intel_funding.find({
        "investors": {"$regex": fund_name, "$options": "i"}
    })
    rounds = await cursor.to_list(200)
    
    # Count co-investors
    coinvestors = {}
    for funding_round in rounds:
        for investor in funding_round.get("investors", []):
            if investor.lower() != fund_name.lower():
                key = investor.lower()
                if key not in coinvestors:
                    coinvestors[key] = {"name": investor, "count": 0, "projects": []}
                coinvestors[key]["count"] += 1
                project = funding_round.get("project_key") or funding_round.get("project")
                if project and project not in coinvestors[key]["projects"]:
                    coinvestors[key]["projects"].append(project)
    
    # Sort by frequency
    sorted_coinvestors = sorted(coinvestors.values(), key=lambda x: -x["count"])[:limit]
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": fund_name,
        "total_rounds": len(rounds),
        "coinvestors": [
            {
                "name": c["name"],
                "deals_together": c["count"],
                "projects": c["projects"][:5],
                "tier": calculate_fund_tier(c["name"], c["count"])
            }
            for c in sorted_coinvestors
        ],
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# FUND PERFORMANCE
# ═══════════════════════════════════════════════════════════════

@router.get("/{fund_id}/performance")
async def get_fund_performance(fund_id: str):
    """
    Get detailed fund performance metrics.
    """
    # Get portfolio data
    portfolio_data = await get_fund_portfolio(fund_id, sort="date", limit=200)
    
    portfolio = portfolio_data["portfolio"]
    summary = portfolio_data["summary"]
    
    # Calculate by year
    by_year = {}
    for p in portfolio:
        if p["round"]["date"]:
            year = datetime.fromtimestamp(p["round"]["date"] / 1000).year
            if year not in by_year:
                by_year[year] = {"count": 0, "invested": 0, "value": 0}
            by_year[year]["count"] += 1
            by_year[year]["invested"] += p["investment"]["estimated_amount"]
            by_year[year]["value"] += p["roi"]["estimated_value"]
    
    yearly_performance = [
        {
            "year": year,
            "investments": data["count"],
            "invested_usd": round(data["invested"], 2),
            "current_value_usd": round(data["value"], 2),
            "multiple": round(data["value"] / data["invested"], 2) if data["invested"] > 0 else 1.0
        }
        for year, data in sorted(by_year.items(), reverse=True)
    ]
    
    # Calculate skill score
    skill_components = {
        "performance": min(summary["overall_multiple"] * 25, 100) * 0.3,
        "win_rate": summary["win_rate_pct"] * 0.25,
        "consistency": 50 * 0.2,  # Placeholder
        "selection_alpha": 50 * 0.15,  # Placeholder
        "network": min(summary["total_investments"] * 2, 100) * 0.1
    }
    
    skill_score = sum(skill_components.values())
    
    return {
        "ts": ts_now(),
        "fund_id": fund_id,
        "fund_name": portfolio_data["fund_name"],
        "overall": {
            "total_investments": summary["total_investments"],
            "total_invested_usd": summary["total_invested_usd"],
            "current_value_usd": summary["total_value_usd"],
            "overall_multiple": summary["overall_multiple"],
            "win_rate_pct": summary["win_rate_pct"]
        },
        "skill_score": {
            "total": round(skill_score),
            "components": {k: round(v, 1) for k, v in skill_components.items()},
            "rank": None,  # Would need leaderboard
            "tier": "tier_1" if skill_score > 70 else "tier_2" if skill_score > 50 else "tier_3"
        },
        "by_year": yearly_performance,
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# FUNDS LEADERBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/leaderboard/roi")
async def get_funds_leaderboard(
    window: str = Query("all", description="Window: 30d, 90d, 1y, all"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get funds leaderboard sorted by performance.
    """
    from server import db
    
    # Get all funds
    cursor = db.intel_investors.find({}).sort("investments_count", -1).limit(100)
    funds = await cursor.to_list(100)
    
    leaderboard = []
    
    for fund in funds:
        if fund.get("investments_count", 0) < 3:
            continue
        
        fund_id = fund.get("id", str(fund.get("_id", "")))
        
        try:
            # Get portfolio summary
            portfolio = await get_fund_portfolio(fund_id, sort="date", limit=50)
            summary = portfolio["summary"]
            
            if summary["total_invested_usd"] < 1000:
                continue
            
            leaderboard.append({
                "rank": 0,
                "fund": {
                    "id": fund_id,
                    "name": fund.get("name"),
                    "slug": fund.get("slug"),
                    "logo": fund.get("logo_url"),
                    "tier": calculate_fund_tier(fund.get("name", ""), fund.get("investments_count", 0))
                },
                "metrics": {
                    "investments": summary["total_investments"],
                    "invested_usd": summary["total_invested_usd"],
                    "value_usd": summary["total_value_usd"],
                    "multiple": summary["overall_multiple"],
                    "win_rate_pct": summary["win_rate_pct"]
                }
            })
        except:
            continue
    
    # Sort by multiple
    leaderboard.sort(key=lambda x: x["metrics"]["multiple"], reverse=True)
    
    # Add ranks
    for i, item in enumerate(leaderboard[:limit]):
        item["rank"] = i + 1
    
    return {
        "ts": ts_now(),
        "window": window,
        "leaderboard": leaderboard[:limit],
        "_meta": {"cache_sec": 600}
    }
