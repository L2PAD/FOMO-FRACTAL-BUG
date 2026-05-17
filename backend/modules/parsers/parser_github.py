"""
GitHub Parser
=============
Fetches developer activity, repository data, and contributors from GitHub API.

TIER 3 source - Person/Project Data
can_provide: developer_activity, contributors, team_members

Data:
- Repository stats (stars, forks, commits)
- Contributors and their activity
- Recent commit history
- Developer metrics

GitHub API: https://api.github.com
Rate limits: 60 req/hour (unauthenticated), 5000 req/hour (with token)
"""

import httpx
import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from modules.intel.parser_validation import ParserValidator, validate_parser_output

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubParser:
    """GitHub data parser using public API with validation"""
    
    source_id = "github"
    
    # Known crypto project repositories
    TRACKED_REPOS = [
        # Layer 1 / Infrastructure
        {"owner": "ethereum", "repo": "go-ethereum", "project": "Ethereum"},
        {"owner": "solana-labs", "repo": "solana", "project": "Solana"},
        {"owner": "aptos-labs", "repo": "aptos-core", "project": "Aptos"},
        {"owner": "MystenLabs", "repo": "sui", "project": "Sui"},
        {"owner": "celestiaorg", "repo": "celestia-node", "project": "Celestia"},
        {"owner": "availproject", "repo": "avail", "project": "Avail"},
        {"owner": "movementlabsxyz", "repo": "movement", "project": "Movement"},
        
        # Layer 2 / Scaling
        {"owner": "ethereum-optimism", "repo": "optimism", "project": "Optimism"},
        {"owner": "OffchainLabs", "repo": "nitro", "project": "Arbitrum"},
        {"owner": "matter-labs", "repo": "zksync-era", "project": "zkSync"},
        {"owner": "starkware-libs", "repo": "cairo", "project": "StarkNet"},
        {"owner": "scroll-tech", "repo": "scroll", "project": "Scroll"},
        {"owner": "base-org", "repo": "base-contracts", "project": "Base"},
        
        # DeFi Protocols
        {"owner": "Uniswap", "repo": "v3-core", "project": "Uniswap"},
        {"owner": "aave", "repo": "aave-v3-core", "project": "Aave"},
        {"owner": "curvefi", "repo": "curve-contract", "project": "Curve"},
        {"owner": "makerdao", "repo": "dss", "project": "MakerDAO"},
        {"owner": "compound-finance", "repo": "compound-protocol", "project": "Compound"},
        {"owner": "Lido-Finance", "repo": "lido-dao", "project": "Lido"},
        
        # Infrastructure / Tools
        {"owner": "chainlink", "repo": "chainlink", "project": "Chainlink"},
        {"owner": "graphprotocol", "repo": "graph-node", "project": "The Graph"},
        {"owner": "eigenlayer", "repo": "eigenlayer-contracts", "project": "EigenLayer"},
        {"owner": "succinctlabs", "repo": "sp1", "project": "Succinct"},
        
        # Hot Projects 2024-2025
        {"owner": "berachain", "repo": "polaris", "project": "Berachain"},
        {"owner": "hyperlane-xyz", "repo": "hyperlane-monorepo", "project": "Hyperlane"},
        {"owner": "LayerZero-Labs", "repo": "LayerZero", "project": "LayerZero"},
    ]
    
    def __init__(self, db):
        self.db = db
        self.validator = ParserValidator(self.source_id)
        
        # Check for GitHub token in environment
        self.github_token = os.environ.get("GITHUB_TOKEN")
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "FOMO-Intel-Terminal/1.0"
        }
        
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
            logger.info("[GitHub] Using authenticated requests (5000 req/hour)")
        else:
            logger.info("[GitHub] Using unauthenticated requests (60 req/hour)")
        
        self.client = httpx.AsyncClient(
            timeout=30,
            headers=headers
        )
    
    async def close(self):
        await self.client.aclose()
    
    async def fetch_repo_info(self, owner: str, repo: str) -> Optional[Dict]:
        """Fetch repository information"""
        try:
            resp = await self.client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "repo_id": data.get("id"),
                    "name": data.get("name"),
                    "full_name": data.get("full_name"),
                    "description": data.get("description"),
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                    "watchers": data.get("watchers_count", 0),
                    "open_issues": data.get("open_issues_count", 0),
                    "language": data.get("language"),
                    "topics": data.get("topics", []),
                    "default_branch": data.get("default_branch"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "pushed_at": data.get("pushed_at"),
                    "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
                    "homepage": data.get("homepage"),
                    "archived": data.get("archived", False),
                    "html_url": data.get("html_url")
                }
            elif resp.status_code == 404:
                logger.warning(f"[GitHub] Repo not found: {owner}/{repo}")
            elif resp.status_code == 403:
                logger.warning("[GitHub] Rate limit exceeded")
            else:
                logger.warning(f"[GitHub] Repo API returned {resp.status_code} for {owner}/{repo}")
            
            return None
        except Exception as e:
            logger.error(f"[GitHub] Repo fetch error for {owner}/{repo}: {e}")
            return None
    
    async def fetch_contributors(self, owner: str, repo: str, limit: int = 30) -> List[Dict]:
        """Fetch repository contributors"""
        try:
            resp = await self.client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contributors",
                params={"per_page": limit}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {
                        "github_id": c.get("id"),
                        "login": c.get("login"),
                        "avatar_url": c.get("avatar_url"),
                        "contributions": c.get("contributions", 0),
                        "type": c.get("type"),
                        "profile_url": c.get("html_url")
                    }
                    for c in data
                ]
            
            return []
        except Exception as e:
            logger.error(f"[GitHub] Contributors fetch error for {owner}/{repo}: {e}")
            return []
    
    async def fetch_recent_commits(self, owner: str, repo: str, days: int = 30) -> List[Dict]:
        """Fetch recent commits"""
        try:
            since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            resp = await self.client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                params={"since": since, "per_page": 100}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {
                        "sha": c.get("sha", "")[:7],
                        "message": (c.get("commit", {}).get("message", "") or "")[:100],
                        "author": c.get("commit", {}).get("author", {}).get("name"),
                        "author_login": c.get("author", {}).get("login") if c.get("author") else None,
                        "date": c.get("commit", {}).get("author", {}).get("date")
                    }
                    for c in data
                ]
            
            return []
        except Exception as e:
            logger.error(f"[GitHub] Commits fetch error for {owner}/{repo}: {e}")
            return []
    
    async def fetch_commit_activity(self, owner: str, repo: str) -> Optional[Dict]:
        """Fetch commit activity stats (last year)"""
        try:
            resp = await self.client.get(f"{GITHUB_API}/repos/{owner}/{repo}/stats/commit_activity")
            
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    # data is array of 52 weeks
                    total_commits = sum(week.get("total", 0) for week in data)
                    recent_weeks = data[-4:] if len(data) >= 4 else data
                    recent_commits = sum(week.get("total", 0) for week in recent_weeks)
                    
                    return {
                        "yearly_commits": total_commits,
                        "monthly_commits": recent_commits,
                        "weekly_data": data[-12:] if len(data) >= 12 else data
                    }
            elif resp.status_code == 202:
                # GitHub is computing stats, retry later
                logger.info(f"[GitHub] Stats being computed for {owner}/{repo}")
            
            return None
        except Exception as e:
            logger.error(f"[GitHub] Activity fetch error for {owner}/{repo}: {e}")
            return None
    
    async def fetch_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Fetch repository languages breakdown"""
        try:
            resp = await self.client.get(f"{GITHUB_API}/repos/{owner}/{repo}/languages")
            
            if resp.status_code == 200:
                return resp.json()
            
            return {}
        except Exception as e:
            logger.error(f"[GitHub] Languages fetch error for {owner}/{repo}: {e}")
            return {}
    
    async def fetch_user_profile(self, username: str) -> Optional[Dict]:
        """Fetch GitHub user profile"""
        try:
            resp = await self.client.get(f"{GITHUB_API}/users/{username}")
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "github_id": data.get("id"),
                    "login": data.get("login"),
                    "name": data.get("name"),
                    "company": data.get("company"),
                    "blog": data.get("blog"),
                    "location": data.get("location"),
                    "bio": data.get("bio"),
                    "twitter_username": data.get("twitter_username"),
                    "public_repos": data.get("public_repos", 0),
                    "public_gists": data.get("public_gists", 0),
                    "followers": data.get("followers", 0),
                    "following": data.get("following", 0),
                    "created_at": data.get("created_at"),
                    "avatar_url": data.get("avatar_url"),
                    "profile_url": data.get("html_url")
                }
            
            return None
        except Exception as e:
            logger.error(f"[GitHub] User profile fetch error for {username}: {e}")
            return None
    
    async def get_developer_activity(self, owner: str, repo: str, project: str) -> Dict[str, Any]:
        """
        Compile full developer activity for a project.
        This is the main field this parser provides.
        """
        # Fetch all data in parallel
        repo_info_task = self.fetch_repo_info(owner, repo)
        contributors_task = self.fetch_contributors(owner, repo)
        commits_task = self.fetch_recent_commits(owner, repo)
        activity_task = self.fetch_commit_activity(owner, repo)
        languages_task = self.fetch_languages(owner, repo)
        
        repo_info, contributors, commits, activity, languages = await asyncio.gather(
            repo_info_task, contributors_task, commits_task, activity_task, languages_task
        )
        
        now = datetime.now(timezone.utc)
        
        # Calculate developer score (0-100)
        dev_score = 0
        if repo_info:
            dev_score += min(repo_info.get("stars", 0) / 100, 30)  # Max 30 from stars
            dev_score += min(repo_info.get("forks", 0) / 50, 20)   # Max 20 from forks
        if activity:
            dev_score += min(activity.get("monthly_commits", 0) / 10, 25)  # Max 25 from commits
        if contributors:
            dev_score += min(len(contributors) / 5, 25)  # Max 25 from contributors
        
        return {
            "id": f"github:{owner}:{repo}",
            "project": project,
            "project_key": project.lower().replace(" ", "-"),
            "repository": {
                "owner": owner,
                "repo": repo,
                "full_name": f"{owner}/{repo}",
                **(repo_info or {})
            },
            "developer_activity": {
                "dev_score": round(dev_score, 1),
                "total_contributors": len(contributors),
                "top_contributors": contributors[:10],
                "commits_30d": len(commits),
                "recent_commits": commits[:10],
                **(activity or {}),
                "languages": languages
            },
            "contributors": contributors[:20],
            "metrics": {
                "stars": repo_info.get("stars", 0) if repo_info else 0,
                "forks": repo_info.get("forks", 0) if repo_info else 0,
                "open_issues": repo_info.get("open_issues", 0) if repo_info else 0,
                "contributors_count": len(contributors),
                "commits_30d": len(commits),
                "monthly_commits": activity.get("monthly_commits", 0) if activity else 0,
                "yearly_commits": activity.get("yearly_commits", 0) if activity else 0
            },
            "source": self.source_id,
            "updated_at": now.isoformat()
        }
    
    async def sync_tracked_repos(self, batch_size: int = 5):
        """
        Sync all tracked repositories.
        Uses batching to respect rate limits.
        """
        results = {
            "synced": 0,
            "failed": 0,
            "projects": []
        }
        
        # Process in batches
        for i in range(0, len(self.TRACKED_REPOS), batch_size):
            batch = self.TRACKED_REPOS[i:i + batch_size]
            
            for repo_config in batch:
                try:
                    data = await self.get_developer_activity(
                        repo_config["owner"],
                        repo_config["repo"],
                        repo_config["project"]
                    )
                    
                    # Validate with Field Ownership
                    validated = self.validator.filter_data(data)
                    
                    # Store in database
                    await self.db.intel_github.update_one(
                        {"id": validated["id"]},
                        {"$set": validated},
                        upsert=True
                    )
                    
                    results["synced"] += 1
                    results["projects"].append({
                        "project": repo_config["project"],
                        "repo": f"{repo_config['owner']}/{repo_config['repo']}",
                        "dev_score": validated.get("developer_activity", {}).get("dev_score", 0)
                    })
                    
                    logger.info(f"[GitHub] Synced {repo_config['project']}: score={validated.get('developer_activity', {}).get('dev_score', 0)}")
                    
                except Exception as e:
                    logger.error(f"[GitHub] Failed to sync {repo_config['project']}: {e}")
                    results["failed"] += 1
            
            # Delay between batches to respect rate limits
            if i + batch_size < len(self.TRACKED_REPOS):
                await asyncio.sleep(2)
        
        return results
    
    async def sync_single_repo(self, owner: str, repo: str, project: str = None):
        """Sync a single repository"""
        if not project:
            project = repo.replace("-", " ").title()
        
        data = await self.get_developer_activity(owner, repo, project)
        validated = self.validator.filter_data(data)
        
        await self.db.intel_github.update_one(
            {"id": validated["id"]},
            {"$set": validated},
            upsert=True
        )
        
        return {
            "ok": True,
            "project": project,
            "dev_score": validated.get("developer_activity", {}).get("dev_score", 0),
            "validation": self.validator.get_stats()
        }
    
    async def get_project_github_data(self, project_key: str) -> Optional[Dict]:
        """Get cached GitHub data for a project"""
        return await self.db.intel_github.find_one(
            {"project_key": project_key},
            {"_id": 0}
        )
    
    async def get_all_github_data(self) -> List[Dict]:
        """Get all cached GitHub data"""
        return await self.db.intel_github.find(
            {},
            {"_id": 0}
        ).sort("developer_activity.dev_score", -1).to_list(100)
    
    async def search_contributors(self, username: str) -> List[Dict]:
        """Search for a contributor across all tracked repos"""
        results = await self.db.intel_github.find(
            {"contributors.login": {"$regex": username, "$options": "i"}},
            {"_id": 0, "project": 1, "repository.full_name": 1, "contributors.$": 1}
        ).to_list(20)
        
        return results


async def sync_github_data(db, batch_size: int = 5):
    """
    Helper function to sync GitHub data.
    Called by scheduler.
    """
    parser = GitHubParser(db)
    
    try:
        result = await parser.sync_tracked_repos(batch_size)
        logger.info(f"[GitHub] Sync complete: {result['synced']} repos, {result['failed']} failed")
        return {
            "ok": True,
            **result,
            "source": "github"
        }
    except Exception as e:
        logger.error(f"[GitHub] Sync error: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        await parser.close()


# ═══════════════════════════════════════════════════════════════
# API Routes Helper Functions
# ═══════════════════════════════════════════════════════════════

async def get_github_summary(db) -> Dict:
    """Get summary of GitHub data for API"""
    total = await db.intel_github.count_documents({})
    
    if total == 0:
        return {
            "total_repos": 0,
            "average_dev_score": 0,
            "top_projects": []
        }
    
    # Get top projects by dev score
    top_projects = await db.intel_github.find(
        {},
        {"_id": 0, "project": 1, "repository.full_name": 1, 
         "developer_activity.dev_score": 1, "metrics": 1}
    ).sort("developer_activity.dev_score", -1).limit(10).to_list(10)
    
    # Calculate average
    pipeline = [
        {"$group": {
            "_id": None,
            "avg_score": {"$avg": "$developer_activity.dev_score"},
            "total_stars": {"$sum": "$metrics.stars"},
            "total_contributors": {"$sum": "$metrics.contributors_count"}
        }}
    ]
    
    agg_result = await db.intel_github.aggregate(pipeline).to_list(1)
    stats = agg_result[0] if agg_result else {}
    
    return {
        "total_repos": total,
        "average_dev_score": round(stats.get("avg_score", 0), 1),
        "total_stars": stats.get("total_stars", 0),
        "total_contributors": stats.get("total_contributors", 0),
        "top_projects": [
            {
                "project": p["project"],
                "repo": p.get("repository", {}).get("full_name"),
                "dev_score": p.get("developer_activity", {}).get("dev_score", 0),
                "stars": p.get("metrics", {}).get("stars", 0)
            }
            for p in top_projects
        ]
    }
