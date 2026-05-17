"""
FOMO Persons Layer - Full Model
================================
Complete person model for Graph Engine with career, connections, influence.

Collections:
- intel_persons (core)
- person_positions (career history)
- person_connections (network graph)
- person_social (influence metrics)

Endpoints:
- GET /api/persons - List persons
- GET /api/persons/{id} - Profile
- GET /api/persons/{id}/career - Career history
- GET /api/persons/{id}/projects - Founded/worked projects
- GET /api/persons/{id}/investments - Angel investments
- GET /api/persons/{id}/advisory - Advisory roles
- GET /api/persons/{id}/connections - Direct connections
- GET /api/persons/{id}/coinvestors - Co-investor network
- GET /api/persons/{id}/network - Full network graph
- GET /api/persons/{id}/influence - Influence metrics
- GET /api/persons/leaderboard - Top persons by score
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/persons", tags=["Persons"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def calculate_person_score(person: dict, positions: list, investments: list, connections: list) -> dict:
    """
    Calculate person score (0-100).
    
    Components:
    - 40% investment_success (angel ROI, fund performance)
    - 30% founder_success (successful projects)
    - 20% influence (social reach)
    - 10% network_strength (tier1 connections)
    """
    components = {}
    
    # Investment success
    investment_count = len(investments)
    components["investment_success"] = min(investment_count * 5, 100)
    
    # Founder success
    founder_positions = [p for p in positions if p.get("role") in ["founder", "cofounder", "ceo", "cto"]]
    components["founder_success"] = min(len(founder_positions) * 20, 100)
    
    # Influence
    social = person.get("social", {})
    twitter_followers = social.get("twitter_followers", 0) or 0
    influence = min(twitter_followers / 10000, 100) if twitter_followers else 20
    components["influence"] = influence
    
    # Network strength
    tier1_connections = sum(1 for c in connections if c.get("tier") == 1)
    components["network_strength"] = min(tier1_connections * 10, 100)
    
    total = (
        components["investment_success"] * 0.40 +
        components["founder_success"] * 0.30 +
        components["influence"] * 0.20 +
        components["network_strength"] * 0.10
    )
    
    return {
        "total": round(total),
        "components": components,
        "tier": 1 if total >= 70 else 2 if total >= 40 else 3
    }


# ═══════════════════════════════════════════════════════════════
# PERSONS LIST
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_persons(
    search: str = Query(None, description="Search by name"),
    role: str = Query(None, description="Filter by role: founder, investor, advisor"),
    tier: int = Query(None, description="Filter by tier: 1, 2, 3"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all persons with filtering.
    """
    from server import db
    
    skip = (page - 1) * limit
    
    query = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    if role:
        query["roles"] = {"$in": [role]}
    if tier:
        query["tier"] = tier
    
    cursor = db.intel_persons.find(query).sort("influence_score", -1).skip(skip).limit(limit)
    persons = await cursor.to_list(limit)
    
    total = await db.intel_persons.count_documents(query)
    
    items = []
    for person in persons:
        items.append({
            "id": person.get("key", str(person.get("_id", ""))),
            "name": person.get("name", ""),
            "slug": person.get("slug", ""),
            "photo": person.get("photo_url", ""),
            "bio": person.get("bio", "")[:200] if person.get("bio") else None,
            "current_position": person.get("current_position"),
            "current_company": person.get("current_company"),
            "roles": person.get("roles", []),
            "tier": person.get("tier", 3),
            "influence_score": person.get("influence_score", 0),
            "social": {
                "twitter": person.get("twitter"),
                "linkedin": person.get("linkedin"),
                "twitter_followers": person.get("twitter_followers")
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
# PERSON PROFILE
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}")
async def get_person_profile(person_id: str):
    """
    Get comprehensive person profile.
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person_key = person.get("key", person_id)
    
    # Get positions
    positions = []
    try:
        cursor = db.person_positions.find({"person_id": person_key})
        positions = await cursor.to_list(50)
    except:
        pass
    
    # Get investments count
    investments = []
    try:
        cursor = db.person_investments.find({"person_id": person_key})
        investments = await cursor.to_list(100)
    except:
        pass
    
    # Get connections count
    connections = []
    try:
        cursor = db.person_connections.find({
            "$or": [{"person_a": person_key}, {"person_b": person_key}]
        })
        connections = await cursor.to_list(100)
    except:
        pass
    
    # Calculate score
    score = calculate_person_score(person, positions, investments, connections)
    
    return {
        "ts": ts_now(),
        "person": {
            "id": person_key,
            "name": person.get("name"),
            "slug": person.get("slug"),
            "photo": person.get("photo_url"),
            "bio": person.get("bio"),
            "location": person.get("location"),
            "nationality": person.get("nationality"),
            "current_position": person.get("current_position"),
            "current_company": person.get("current_company"),
            "roles": person.get("roles", []),
            "tags": person.get("tags", []),
            "tier": person.get("tier", score.get("tier", 3)),
            "influence_score": person.get("influence_score", score.get("total", 0))
        },
        "social": {
            "twitter": person.get("twitter"),
            "linkedin": person.get("linkedin"),
            "github": person.get("github"),
            "website": person.get("website"),
            "twitter_followers": person.get("twitter_followers"),
            "linkedin_followers": person.get("linkedin_followers"),
            "github_stars": person.get("github_stars")
        },
        "stats": {
            "positions_count": len(positions),
            "investments_count": len(investments),
            "connections_count": len(connections),
            "projects_count": len(person.get("projects", []))
        },
        "scores": score,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# CAREER HISTORY
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/career")
async def get_person_career(person_id: str):
    """
    Get person's career history (positions at companies/projects/funds).
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person_key = person.get("key", person_id)
    
    # Get positions from dedicated collection
    positions = []
    try:
        cursor = db.person_positions.find({"person_id": person_key}).sort("start_date", -1)
        positions = await cursor.to_list(50)
    except:
        pass
    
    # If no positions collection, try to infer from projects
    if not positions:
        projects = person.get("projects", [])
        for proj_key in projects:
            project = await db.intel_projects.find_one({"key": proj_key})
            if project:
                positions.append({
                    "company": project.get("name"),
                    "company_type": "project",
                    "project_id": proj_key,
                    "position": person.get("role", "Team Member"),
                    "is_current": True,
                    "start_date": None,
                    "end_date": None
                })
    
    # Format positions
    formatted = []
    for pos in positions:
        formatted.append({
            "company": pos.get("company"),
            "company_type": pos.get("company_type", "project"),
            "project_id": pos.get("project_id"),
            "fund_id": pos.get("fund_id"),
            "position": pos.get("position"),
            "is_current": pos.get("is_current", False),
            "start_date": pos.get("start_date"),
            "end_date": pos.get("end_date"),
            "duration_months": None  # Could calculate if dates available
        })
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person.get("name"),
        "current_position": person.get("current_position"),
        "current_company": person.get("current_company"),
        "positions_count": len(formatted),
        "positions": formatted,
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# FOUNDED/WORKED PROJECTS
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/projects")
async def get_person_projects(person_id: str):
    """
    Get projects where person is/was founder, co-founder, or team member.
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person_key = person.get("key", person_id)
    projects_keys = person.get("projects", [])
    
    # Get project details
    projects = []
    for key in projects_keys:
        project = await db.intel_projects.find_one({"key": key})
        if project:
            # Determine role
            role = "team_member"
            if person.get("role"):
                role_lower = person.get("role", "").lower()
                if "founder" in role_lower or "ceo" in role_lower:
                    role = "founder"
                elif "advisor" in role_lower:
                    role = "advisor"
                elif "investor" in role_lower:
                    role = "investor"
            
            projects.append({
                "key": key,
                "name": project.get("name"),
                "symbol": project.get("symbol"),
                "category": project.get("category"),
                "logo": project.get("logo_url"),
                "role": role,
                "is_current": True
            })
    
    # Categorize
    founded = [p for p in projects if p["role"] in ["founder", "cofounder"]]
    worked = [p for p in projects if p["role"] in ["team_member", "engineer", "lead"]]
    advised = [p for p in projects if p["role"] == "advisor"]
    invested = [p for p in projects if p["role"] == "investor"]
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person.get("name"),
        "summary": {
            "total": len(projects),
            "founded": len(founded),
            "worked": len(worked),
            "advised": len(advised),
            "invested": len(invested)
        },
        "projects": {
            "founded": founded,
            "worked": worked,
            "advised": advised,
            "invested": invested
        },
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# INVESTMENTS (Angel/Personal)
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/investments")
async def get_person_investments(person_id: str, limit: int = Query(50, ge=1, le=100)):
    """
    Get person's investment history (angel investments, personal deals).
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person_name = person.get("name", "")
    
    # Search funding rounds where this person invested
    cursor = db.intel_funding.find({
        "investors": {"$regex": person_name, "$options": "i"}
    }).sort("round_date", -1).limit(limit)
    
    rounds = await cursor.to_list(limit)
    
    investments = []
    total_invested = 0
    
    for funding_round in rounds:
        # Estimate investment (angel typically smaller than VC)
        raised = funding_round.get("raised_usd", 0) or 0
        investor_count = len(funding_round.get("investors", [])) or 1
        estimated = raised / investor_count * 0.3  # Angels usually invest less
        
        total_invested += estimated
        
        investments.append({
            "project": funding_round.get("project"),
            "project_key": funding_round.get("project_key"),
            "symbol": funding_round.get("symbol"),
            "round_type": funding_round.get("round_type"),
            "date": funding_round.get("round_date"),
            "role": "angel",
            "estimated_amount": round(estimated, 2),
            "round_total": raised
        })
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person_name,
        "summary": {
            "total_investments": len(investments),
            "estimated_total_usd": round(total_invested, 2)
        },
        "investments": investments,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# ADVISORY ROLES
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/advisory")
async def get_person_advisory(person_id: str):
    """
    Get projects where person serves as advisor.
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Get from person_advisors collection
    advisories = []
    try:
        cursor = db.person_advisors.find({"person_id": person.get("key", person_id)})
        advisories = await cursor.to_list(50)
    except:
        pass
    
    # If empty, check role in person data
    if not advisories and person.get("role") and "advisor" in person.get("role", "").lower():
        for proj_key in person.get("projects", []):
            project = await db.intel_projects.find_one({"key": proj_key})
            if project:
                advisories.append({
                    "project_key": proj_key,
                    "project_name": project.get("name"),
                    "role": "advisor",
                    "start_date": None,
                    "is_current": True
                })
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person.get("name"),
        "advisory_count": len(advisories),
        "advisory_roles": advisories,
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# CONNECTIONS (Direct)
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/connections")
async def get_person_connections(person_id: str, limit: int = Query(50, ge=1, le=100)):
    """
    Get person's direct connections (worked together, co-invested, etc.).
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person_key = person.get("key", person_id)
    
    # Get from connections collection
    connections = []
    seen_ids = set()  # Track seen person IDs to deduplicate
    try:
        cursor = db.person_connections.find({
            "$or": [{"person_a": person_key}, {"person_b": person_key}]
        }).limit(limit * 2)  # Fetch more to account for deduplication
        raw_connections = await cursor.to_list(limit * 2)
        
        for conn in raw_connections:
            other_id = conn["person_b"] if conn["person_a"] == person_key else conn["person_a"]
            
            # Skip if already seen this person
            if other_id in seen_ids:
                continue
            seen_ids.add(other_id)
            
            other_person = await db.intel_persons.find_one({"key": other_id})
            
            connections.append({
                "person_id": other_id,
                "person_name": other_person.get("name") if other_person else other_id,
                "photo": other_person.get("photo_url") if other_person else None,
                "relation_type": conn.get("relation_type"),
                "shared_entity": conn.get("shared_entity"),
                "strength": conn.get("strength", 1)
            })
    except Exception:
        pass
    
    # If no stored connections, build from shared projects
    if not connections:
        person_projects = set(person.get("projects", []))
        
        # Find other people who worked on same projects
        cursor = db.intel_persons.find({
            "key": {"$ne": person_key},
            "projects": {"$in": list(person_projects)}
        }).limit(limit)
        
        others = await cursor.to_list(limit)
        
        for other in others:
            other_projects = set(other.get("projects", []))
            shared = person_projects & other_projects
            
            if shared:
                connections.append({
                    "person_id": other.get("key"),
                    "person_name": other.get("name"),
                    "photo": other.get("photo_url"),
                    "relation_type": "worked_together",
                    "shared_entity": list(shared)[0],
                    "shared_count": len(shared),
                    "strength": len(shared)
                })
    
    # Sort by strength
    connections.sort(key=lambda x: x.get("strength", 0), reverse=True)
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person.get("name"),
        "connections_count": len(connections),
        "connections": connections[:limit],
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# CO-INVESTORS
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/coinvestors")
async def get_person_coinvestors(person_id: str, limit: int = Query(20, ge=1, le=50)):
    """
    Get person's co-investor network (other investors in same rounds).
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person_name = person.get("name", "")
    
    # Get rounds where person invested
    cursor = db.intel_funding.find({
        "investors": {"$regex": person_name, "$options": "i"}
    })
    rounds = await cursor.to_list(100)
    
    # Count co-investors
    coinvestors = {}
    for funding_round in rounds:
        for investor in funding_round.get("investors", []):
            if investor.lower() != person_name.lower():
                key = investor.lower()
                if key not in coinvestors:
                    coinvestors[key] = {
                        "name": investor,
                        "deals_together": 0,
                        "projects": []
                    }
                coinvestors[key]["deals_together"] += 1
                project = funding_round.get("project_key") or funding_round.get("project")
                if project and project not in coinvestors[key]["projects"]:
                    coinvestors[key]["projects"].append(project)
    
    # Sort by frequency
    sorted_coinvestors = sorted(
        coinvestors.values(),
        key=lambda x: x["deals_together"],
        reverse=True
    )[:limit]
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person_name,
        "total_deals": len(rounds),
        "coinvestors_count": len(coinvestors),
        "coinvestors": [
            {
                "name": c["name"],
                "deals_together": c["deals_together"],
                "projects": c["projects"][:5],
                "type": "fund" if any(w in c["name"].lower() for w in ["capital", "ventures", "labs"]) else "angel"
            }
            for c in sorted_coinvestors
        ],
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# FULL NETWORK (Graph Engine ready)
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/network")
async def get_person_network(person_id: str, depth: int = Query(1, ge=1, le=2)):
    """
    Get person's full network graph (for visualization).
    
    Returns nodes and edges for graph rendering.
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person_key = person.get("key", person_id)
    
    nodes = []
    edges = []
    
    # Add person as central node
    nodes.append({
        "id": person_key,
        "type": "person",
        "label": person.get("name"),
        "photo": person.get("photo_url"),
        "tier": person.get("tier", 3)
    })
    
    # Add projects
    for proj_key in person.get("projects", [])[:10]:
        project = await db.intel_projects.find_one({"key": proj_key})
        if project:
            nodes.append({
                "id": proj_key,
                "type": "project",
                "label": project.get("name"),
                "logo": project.get("logo_url"),
                "symbol": project.get("symbol")
            })
            edges.append({
                "source": person_key,
                "target": proj_key,
                "relation": "worked_at"
            })
    
    # Add connections (other people)
    connections_data = await get_person_connections(person_id, limit=10)
    for conn in connections_data.get("connections", []):
        nodes.append({
            "id": conn["person_id"],
            "type": "person",
            "label": conn["person_name"],
            "photo": conn.get("photo")
        })
        edges.append({
            "source": person_key,
            "target": conn["person_id"],
            "relation": conn["relation_type"]
        })
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person.get("name"),
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
# INFLUENCE METRICS
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}/influence")
async def get_person_influence(person_id: str):
    """
    Get person's influence metrics and social impact.
    """
    from server import db
    
    person = await db.intel_persons.find_one({
        "$or": [{"key": person_id}, {"slug": person_id}]
    })
    
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Social metrics
    twitter_followers = person.get("twitter_followers", 0) or 0
    linkedin_followers = person.get("linkedin_followers", 0) or 0
    github_stars = person.get("github_stars", 0) or 0
    
    # Calculate influence score
    social_reach = twitter_followers + linkedin_followers
    
    if social_reach > 1000000:
        influence_tier = "mega"
        influence_score = 95
    elif social_reach > 100000:
        influence_tier = "major"
        influence_score = 80
    elif social_reach > 10000:
        influence_tier = "notable"
        influence_score = 60
    elif social_reach > 1000:
        influence_tier = "emerging"
        influence_score = 40
    else:
        influence_tier = "low"
        influence_score = 20
    
    # Project impact
    projects = person.get("projects", [])
    
    return {
        "ts": ts_now(),
        "person_id": person_id,
        "person_name": person.get("name"),
        "social": {
            "twitter": person.get("twitter"),
            "twitter_followers": twitter_followers,
            "linkedin": person.get("linkedin"),
            "linkedin_followers": linkedin_followers,
            "github": person.get("github"),
            "github_stars": github_stars,
            "total_reach": social_reach
        },
        "influence": {
            "score": influence_score,
            "tier": influence_tier,
            "projects_count": len(projects)
        },
        "_meta": {"cache_sec": 600}
    }


# ═══════════════════════════════════════════════════════════════
# LEADERBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/leaderboard/top")
async def get_persons_leaderboard(
    metric: str = Query("influence", description="Metric: influence, investments, projects"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get top persons leaderboard.
    """
    from server import db
    
    # Sort field based on metric
    sort_field = "influence_score"
    if metric == "investments":
        sort_field = "investments_count"
    elif metric == "projects":
        sort_field = "projects"
    
    cursor = db.intel_persons.find({}).sort(sort_field, -1).limit(limit)
    persons = await cursor.to_list(limit)
    
    leaderboard = []
    for i, person in enumerate(persons):
        leaderboard.append({
            "rank": i + 1,
            "person": {
                "id": person.get("key"),
                "name": person.get("name"),
                "photo": person.get("photo_url"),
                "current_position": person.get("current_position"),
                "tier": person.get("tier", 3)
            },
            "metrics": {
                "influence_score": person.get("influence_score", 0),
                "projects_count": len(person.get("projects", [])),
                "twitter_followers": person.get("twitter_followers", 0)
            }
        })
    
    return {
        "ts": ts_now(),
        "metric": metric,
        "leaderboard": leaderboard,
        "_meta": {"cache_sec": 600}
    }
