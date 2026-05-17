"""
Self-Learning Discovery Scheduler (Enhanced)
============================================

Complete self-learning API discovery system with:
- Automatic seed domain discovery (every 24h)
- Drift detection & auto re-discovery
- Endpoint scoring & ranking
- Intelligent scheduling based on priority

Architecture:
    ┌─────────────────────────────────────────────────┐
    │           Self-Learning Discovery               │
    ├─────────────────────────────────────────────────┤
    │  Seed Domains (24h)                             │
    │       ↓                                         │
    │  Browser Discovery Engine                       │
    │       ↓                                         │
    │  Endpoint Registry                              │
    │       ↓                                         │
    │  ┌───────────────┬─────────────────┐           │
    │  │ Drift Detection │ Scoring Engine │           │
    │  │    (1h)        │    (6h)        │           │
    │  └───────────────┴─────────────────┘           │
    │       ↓                                         │
    │  Auto Re-discovery (on drift)                  │
    │       ↓                                         │
    │  Scraper Engine (uses best endpoints)          │
    └─────────────────────────────────────────────────┘
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import threading

from motor.motor_asyncio import AsyncIOMotorDatabase
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


# Seed domains by category with priority
SEED_DOMAINS = {
    "market_data": {
        "domains": ["coingecko.com", "coinmarketcap.com", "messari.io"],
        "priority": "critical",
        "discovery_interval": 24  # hours
    },
    "defi": {
        "domains": ["defillama.com", "tokenterminal.com"],
        "priority": "high",
        "discovery_interval": 24
    },
    "dex": {
        "domains": ["dexscreener.com", "geckoterminal.com", "dextools.io"],
        "priority": "high",
        "discovery_interval": 24
    },
    "derivatives": {
        "domains": ["coinglass.com"],
        "priority": "medium",
        "discovery_interval": 48
    },
    "intel": {
        "domains": ["cryptorank.io", "dropstab.com", "rootdata.com"],
        "priority": "critical",
        "discovery_interval": 24
    },
    "news": {
        "domains": ["cointelegraph.com", "coindesk.com", "theblock.co"],
        "priority": "low",
        "discovery_interval": 72
    },
}


class SelfLearningScheduler:
    """
    Enhanced self-learning discovery scheduler.
    
    Features:
    - Automatic seed domain discovery
    - Drift detection with auto re-discovery
    - Endpoint scoring and ranking
    - Priority-based scheduling
    - Background task management
    """
    
    def __init__(
        self, 
        db: AsyncIOMotorDatabase,
        discovery_interval: int = 86400,    # 24 hours
        drift_check_interval: int = 3600,   # 1 hour
        scoring_interval: int = 21600,      # 6 hours
        validation_interval: int = 1800,    # 30 minutes
    ):
        self.db = db
        self.endpoints = db.endpoint_registry
        self.discovery_logs = db.discovery_logs
        self.scheduler_status = db.scheduler_status
        
        self.discovery_interval = discovery_interval
        self.drift_check_interval = drift_check_interval
        self.scoring_interval = scoring_interval
        self.validation_interval = validation_interval
        
        self.scheduler = AsyncIOScheduler()
        self._running = False
        self._lock = threading.Lock()
        
        # Lazy-loaded components
        self._browser_engine = None
        self._drift_detector = None
        self._scoring_engine = None
        
        # Stats
        self._stats = {
            "discoveries": 0,
            "drift_checks": 0,
            "re_discoveries": 0,
            "scorings": 0,
            "last_discovery": None,
            "last_drift_check": None,
            "last_scoring": None
        }
    
    @property
    def browser_engine(self):
        if self._browser_engine is None:
            from modules.discovery_engine.browser_engine import BrowserDiscoveryEngine
            self._browser_engine = BrowserDiscoveryEngine(self.db)
        return self._browser_engine
    
    @property
    def drift_detector(self):
        if self._drift_detector is None:
            from modules.discovery_engine.drift_detector import DriftDetector
            self._drift_detector = DriftDetector(self.db)
        return self._drift_detector
    
    @property
    def scoring_engine(self):
        if self._scoring_engine is None:
            from modules.discovery_engine.scoring_engine import DiscoveryScoringEngine
            self._scoring_engine = DiscoveryScoringEngine(self.db)
        return self._scoring_engine
    
    def start(self):
        """Start all scheduled jobs"""
        with self._lock:
            if self._running:
                return
            
            # 1. Discovery cycle (every 24h, at 3 AM)
            self.scheduler.add_job(
                self._run_discovery_cycle,
                CronTrigger(hour=3, minute=0),  # 3 AM daily
                id="discovery_cycle",
                name="Self-Learning Discovery",
                replace_existing=True
            )
            
            # 2. Drift detection (every 1h)
            self.scheduler.add_job(
                self._run_drift_check,
                IntervalTrigger(seconds=self.drift_check_interval),
                id="drift_check",
                name="Drift Detection",
                replace_existing=True
            )
            
            # 3. Endpoint scoring (every 6h)
            self.scheduler.add_job(
                self._run_scoring_cycle,
                IntervalTrigger(seconds=self.scoring_interval),
                id="scoring_cycle",
                name="Endpoint Scoring",
                replace_existing=True
            )
            
            # 4. Endpoint validation (every 30 min)
            self.scheduler.add_job(
                self._run_validation_cycle,
                IntervalTrigger(seconds=self.validation_interval),
                id="validation_cycle",
                name="Endpoint Validation",
                replace_existing=True
            )
            
            self.scheduler.start()
            self._running = True
            
            logger.info(f"[SelfLearningScheduler] Started with 4 jobs")
            logger.info(f"  → Discovery: Daily at 3 AM")
            logger.info(f"  → Drift Check: Every {self.drift_check_interval // 60} min")
            logger.info(f"  → Scoring: Every {self.scoring_interval // 3600} hours")
            logger.info(f"  → Validation: Every {self.validation_interval // 60} min")
    
    def stop(self):
        """Stop all scheduled jobs"""
        with self._lock:
            if self._running:
                self.scheduler.shutdown(wait=False)
                self._running = False
                logger.info("[SelfLearningScheduler] Stopped")
    
    def get_status(self) -> Dict:
        """Get scheduler status"""
        jobs = []
        if self._running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None
                })
        
        return {
            "running": self._running,
            "jobs": jobs,
            "stats": self._stats,
            "intervals": {
                "discovery": f"{self.discovery_interval // 3600}h",
                "drift_check": f"{self.drift_check_interval // 60}min",
                "scoring": f"{self.scoring_interval // 3600}h",
                "validation": f"{self.validation_interval // 60}min"
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # DISCOVERY CYCLE
    # ═══════════════════════════════════════════════════════════════
    
    async def _run_discovery_cycle(self):
        """Run discovery cycle for all seed domains"""
        logger.info("[SelfLearningScheduler] Starting discovery cycle...")
        
        results = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total_domains": 0,
            "discovered": 0,
            "skipped": 0,
            "failed": 0,
            "endpoints_found": 0,
            "by_category": {}
        }
        
        for category, config in SEED_DOMAINS.items():
            category_results = {"discovered": 0, "endpoints": 0, "failed": 0}
            
            for domain in config["domains"]:
                results["total_domains"] += 1
                
                try:
                    # Check if recently discovered
                    if await self._was_discovered_recently(domain, config["discovery_interval"]):
                        results["skipped"] += 1
                        logger.debug(f"[Discovery] Skipping {domain} - recently discovered")
                        continue
                    
                    # Run discovery
                    logger.info(f"[Discovery] Discovering {domain}...")
                    result = await self.browser_engine.discover(f"https://{domain}")
                    
                    if result.get("status") == "success":
                        endpoints = result.get("endpoints_found", 0)
                        results["discovered"] += 1
                        results["endpoints_found"] += endpoints
                        category_results["discovered"] += 1
                        category_results["endpoints"] += endpoints
                        logger.info(f"[Discovery] {domain}: {endpoints} endpoints")
                        
                        # Score new endpoints
                        await self._score_domain_endpoints(domain)
                    else:
                        results["failed"] += 1
                        category_results["failed"] += 1
                        logger.warning(f"[Discovery] {domain} failed: {result.get('error')}")
                    
                    # Rate limiting
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    results["failed"] += 1
                    category_results["failed"] += 1
                    logger.error(f"[Discovery] Error for {domain}: {e}")
            
            results["by_category"][category] = category_results
        
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Update stats
        self._stats["discoveries"] += 1
        self._stats["last_discovery"] = results["completed_at"]
        
        # Log to database
        await self.discovery_logs.insert_one({
            "type": "discovery_cycle",
            **results
        })
        
        logger.info(f"[SelfLearningScheduler] Discovery complete: {results['discovered']}/{results['total_domains']} domains, {results['endpoints_found']} endpoints")
    
    # ═══════════════════════════════════════════════════════════════
    # DRIFT DETECTION
    # ═══════════════════════════════════════════════════════════════
    
    async def _run_drift_check(self):
        """Run drift detection on active endpoints"""
        logger.info("[SelfLearningScheduler] Running drift check...")
        
        drifts = await self.drift_detector.check_all_drift(limit=30)
        
        self._stats["drift_checks"] += 1
        self._stats["last_drift_check"] = datetime.now(timezone.utc).isoformat()
        
        if drifts:
            logger.warning(f"[DriftCheck] Found {len(drifts)} drifting endpoints")
            
            # Group by domain for re-discovery
            domains_to_rediscover = set()
            for drift in drifts:
                if drift.severity in ("critical", "high"):
                    domains_to_rediscover.add(drift.domain)
                    logger.warning(f"[DriftCheck] {drift.domain}: {drift.drift_type} ({drift.severity})")
            
            # Trigger re-discovery for high severity
            for domain in domains_to_rediscover:
                await self._trigger_rediscovery(domain, "drift_detected")
        else:
            logger.info("[DriftCheck] No drift detected")
    
    async def _trigger_rediscovery(self, domain: str, reason: str):
        """Trigger re-discovery for domain"""
        logger.info(f"[Re-discovery] Triggering for {domain} (reason: {reason})")
        
        try:
            result = await self.browser_engine.rediscover(domain)
            
            self._stats["re_discoveries"] += 1
            
            if result.get("status") == "success":
                logger.info(f"[Re-discovery] {domain}: Found {result.get('endpoints_found', 0)} endpoints")
                
                # Re-score endpoints
                await self._score_domain_endpoints(domain)
            else:
                logger.error(f"[Re-discovery] {domain} failed")
                
        except Exception as e:
            logger.error(f"[Re-discovery] Error for {domain}: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # SCORING CYCLE
    # ═══════════════════════════════════════════════════════════════
    
    async def _run_scoring_cycle(self):
        """Run scoring for all active endpoints"""
        logger.info("[SelfLearningScheduler] Running scoring cycle...")
        
        try:
            scores = await self.scoring_engine.calculate_all_scores(limit=100)
            
            self._stats["scorings"] += 1
            self._stats["last_scoring"] = datetime.now(timezone.utc).isoformat()
            
            # Log summary
            if scores:
                avg_score = sum(s.total_score for s in scores) / len(scores)
                logger.info(f"[Scoring] Scored {len(scores)} endpoints, avg score: {avg_score:.1f}")
            
        except Exception as e:
            logger.error(f"[Scoring] Error: {e}")
    
    async def _score_domain_endpoints(self, domain: str):
        """Score all endpoints for a domain"""
        try:
            scores = await self.scoring_engine.calculate_domain_scores(domain)
            if scores:
                logger.info(f"[Scoring] {domain}: Scored {len(scores)} endpoints")
        except Exception as e:
            logger.error(f"[Scoring] Error for {domain}: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # VALIDATION CYCLE
    # ═══════════════════════════════════════════════════════════════
    
    async def _run_validation_cycle(self):
        """Validate active endpoints"""
        logger.debug("[SelfLearningScheduler] Running validation cycle...")
        
        # Find endpoints needing validation
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        
        cursor = self.endpoints.find({
            "status": "active",
            "$or": [
                {"last_verified": {"$exists": False}},
                {"last_verified": {"$lt": cutoff.isoformat()}}
            ]
        }, {"_id": 0, "id": 1}).limit(10)
        
        validated = 0
        failed = 0
        
        async for ep in cursor:
            try:
                result = await self.browser_engine.replay_endpoint(ep["id"])
                if result.get("ok"):
                    validated += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.debug(f"[Validation] Error for {ep['id']}: {e}")
        
        if validated + failed > 0:
            logger.debug(f"[Validation] Complete: {validated} OK, {failed} failed")
    
    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    async def _was_discovered_recently(self, domain: str, hours: int = 24) -> bool:
        """Check if domain was discovered recently"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        endpoint = await self.endpoints.find_one({
            "domain": domain,
            "discovered_at": {"$gt": cutoff.isoformat()}
        })
        
        return endpoint is not None
    
    # ═══════════════════════════════════════════════════════════════
    # MANUAL TRIGGERS
    # ═══════════════════════════════════════════════════════════════
    
    async def trigger_discovery(self, domain: str = None) -> Dict:
        """Manually trigger discovery"""
        if domain:
            result = await self.browser_engine.discover(f"https://{domain}")
            return {
                "ok": True,
                "domain": domain,
                **result
            }
        else:
            await self._run_discovery_cycle()
            return {"ok": True, "message": "Full discovery cycle completed"}
    
    async def trigger_drift_check(self, domain: str = None) -> Dict:
        """Manually trigger drift check"""
        if domain:
            drifts = await self.drift_detector.check_domain_drift(domain)
            return {
                "ok": True,
                "domain": domain,
                "drifts_found": len(drifts),
                "drifts": [{"type": d.drift_type, "severity": d.severity} for d in drifts]
            }
        else:
            await self._run_drift_check()
            return {"ok": True, "message": "Drift check completed"}
    
    async def trigger_scoring(self, domain: str = None) -> Dict:
        """Manually trigger scoring"""
        if domain:
            scores = await self.scoring_engine.calculate_domain_scores(domain)
            return {
                "ok": True,
                "domain": domain,
                "endpoints_scored": len(scores),
                "scores": [s.to_dict() for s in scores[:5]]
            }
        else:
            await self._run_scoring_cycle()
            return {"ok": True, "message": "Scoring cycle completed"}
    
    async def add_seed_domain(self, category: str, domain: str) -> Dict:
        """Add new seed domain"""
        if category not in SEED_DOMAINS:
            return {"ok": False, "error": f"Unknown category: {category}"}
        
        if domain not in SEED_DOMAINS[category]["domains"]:
            SEED_DOMAINS[category]["domains"].append(domain)
        
        # Trigger immediate discovery
        result = await self.trigger_discovery(domain)
        
        return {
            "ok": True,
            "category": category,
            "domain": domain,
            "discovery": result
        }
    
    async def get_comprehensive_stats(self) -> Dict:
        """Get comprehensive scheduler statistics"""
        status = self.get_status()
        drift_stats = await self.drift_detector.get_drift_stats()
        scoring_stats = await self.scoring_engine.get_scoring_stats()
        
        # Endpoint counts
        total_endpoints = await self.endpoints.count_documents({})
        active_endpoints = await self.endpoints.count_documents({"status": "active"})
        scored_endpoints = await self.endpoints.count_documents({"score": {"$exists": True}})
        
        return {
            "scheduler": status,
            "endpoints": {
                "total": total_endpoints,
                "active": active_endpoints,
                "scored": scored_endpoints
            },
            "drift": drift_stats,
            "scoring": scoring_stats,
            "seed_domains": {
                cat: {"count": len(cfg["domains"]), "priority": cfg["priority"]}
                for cat, cfg in SEED_DOMAINS.items()
            }
        }


# Global instance
_scheduler = None


def get_self_learning_scheduler(db: AsyncIOMotorDatabase) -> SelfLearningScheduler:
    """Get or create self-learning scheduler"""
    global _scheduler
    if _scheduler is None:
        _scheduler = SelfLearningScheduler(db)
    return _scheduler
