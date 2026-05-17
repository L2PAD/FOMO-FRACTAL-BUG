"""
Full Cycle — The main orchestration engine
============================================
SOURCE → PARSER → RAW → CANONICAL → INTELLIGENCE → GRAPH → DATASET → API

This is the heartbeat of the Crypto Intelligence Operating System.
"""
import time
from datetime import datetime, timezone
from intelligence_os.ingestion.orchestrator import IngestionOrchestrator
from intelligence_os.ingestion.parser_factory import create_parser_factory
from intelligence_os.canonical.pipeline import CanonicalPipeline
from intelligence_os.domains.funding.intelligence import FundingIntelligence
from intelligence_os.domains.projects.intelligence import ProjectsIntelligence
from intelligence_os.domains.ico.intelligence import ICOIntelligence
from intelligence_os.domains.activities.intelligence import ActivitiesIntelligence
from intelligence_os.domains.unlocks.intelligence import UnlocksIntelligence
from intelligence_os.domains.news.intelligence import NewsIntelligence
from intelligence_os.ops.health_service import HealthService
from intelligence_os.core.logging_config import get_logger

log = get_logger("full_cycle")


class FullCycle:
    def __init__(self, db):
        self.db = db
        self.parser_factory = create_parser_factory(db)
        self.ingestion = IngestionOrchestrator(db, self.parser_factory)
        self.canonical = CanonicalPipeline(db)
        self.funding_intel = FundingIntelligence(db)
        self.projects_intel = ProjectsIntelligence(db)
        self.ico_intel = ICOIntelligence(db)
        self.activities_intel = ActivitiesIntelligence(db)
        self.unlocks_intel = UnlocksIntelligence(db)
        self.news_intel = NewsIntelligence(db)
        self.health = HealthService(db)

    async def run_full_cycle(self) -> dict:
        """Execute the complete data pipeline."""
        t0 = time.time()
        now = datetime.now(timezone.utc).isoformat()
        stages = {}

        log.info("=" * 60)
        log.info("[FULL CYCLE] Starting...")
        log.info("=" * 60)

        # ── Stage 1: INGESTION ──
        try:
            stages["ingestion"] = await self.ingestion.run_all()
            log.info(f"[STAGE 1/6] Ingestion: {stages['ingestion'].get('total_saved', 0)} saved")
        except Exception as e:
            stages["ingestion"] = {"ok": False, "error": str(e)[:200]}
            log.exception("[STAGE 1/6] Ingestion failed")

        # ── Stage 2: CANONICALIZATION ──
        try:
            stages["canonicalization"] = await self.canonical.run_full()
            log.info(f"[STAGE 2/6] Canonicalization complete")
        except Exception as e:
            stages["canonicalization"] = {"ok": False, "error": str(e)[:200]}
            log.exception("[STAGE 2/6] Canonicalization failed")

        # ── Stage 3: INTELLIGENCE ──
        intel_results = {}
        try:
            intel_results["funding"] = await self.funding_intel.build_coinvest_patterns()
            intel_results["funding_profiles"] = await self.funding_intel.build_investor_profiles()
            intel_results["projects"] = await self.projects_intel.enrich_projects()
            intel_results["ico"] = await self.ico_intel.classify_launches()
            intel_results["activities"] = await self.activities_intel.process_activities()
            intel_results["unlocks"] = await self.unlocks_intel.build_unlock_calendar()
            intel_results["news"] = await self.news_intel.process_news_events()
            stages["intelligence"] = intel_results
            log.info(f"[STAGE 3/6] Intelligence complete")
        except Exception as e:
            stages["intelligence"] = {"ok": False, "error": str(e)[:200]}
            log.exception("[STAGE 3/6] Intelligence failed")

        # ── Stage 4: GRAPH HOOKS ──
        try:
            graph_edges = []
            graph_edges.extend(await self.funding_intel.get_graph_hooks())
            graph_edges.extend(await self.ico_intel.get_graph_hooks())
            graph_edges.extend(await self.activities_intel.get_graph_hooks())
            # Note: news does NOT generate graph base edges

            edges_written = 0
            for edge in graph_edges:
                if not edge.get("from_id") or not edge.get("to_id"):
                    continue
                await self.db["graph_edges"].update_one(
                    {
                        "from_node_id": edge["from_id"],
                        "to_node_id": edge["to_id"],
                        "relation_type": edge["edge_type"],
                        "layer": edge["layer"],
                    },
                    {
                        "$set": {"last_seen": now, "source": edge.get("source")},
                        "$inc": {"evidence_count": 1},
                        "$setOnInsert": {"first_seen": now},
                    },
                    upsert=True,
                )
                edges_written += 1

            stages["graph_hooks"] = {"edges_generated": len(graph_edges), "edges_written": edges_written}
            log.info(f"[STAGE 4/6] Graph hooks: {edges_written} edges")
        except Exception as e:
            stages["graph_hooks"] = {"ok": False, "error": str(e)[:200]}
            log.exception("[STAGE 4/6] Graph hooks failed")

        # ── Stage 5: HEALTH SNAPSHOT ──
        try:
            canonical_stats = await self.canonical.get_stats()
            health_snapshot = {
                "cycle_completed_at": now,
                "duration_sec": round(time.time() - t0, 2),
                "canonical": canonical_stats,
                "stages_summary": {k: "OK" if not isinstance(v, dict) or v.get("ok") is not False else "FAIL"
                           for k, v in stages.items()},
            }
            await self.db["ops_cycle_health"].insert_one(dict(health_snapshot))
            stages["health"] = {
                "cycle_completed_at": now,
                "duration_sec": health_snapshot["duration_sec"],
                "canonical": canonical_stats,
            }
            log.info(f"[STAGE 5/6] Health snapshot saved")
        except Exception as e:
            log.exception("[STAGE 5/6] Health snapshot failed")

        duration = round(time.time() - t0, 2)
        log.info(f"[FULL CYCLE] Complete in {duration}s")
        log.info("=" * 60)

        return {
            "ok": True,
            "duration_sec": duration,
            "completed_at": now,
            "stages": stages,
        }

    async def run_ingestion_only(self) -> dict:
        return await self.ingestion.run_all()

    async def run_canonical_only(self) -> dict:
        return await self.canonical.run_full()

    async def run_intelligence_only(self) -> dict:
        results = {}
        results["funding"] = await self.funding_intel.build_coinvest_patterns()
        results["projects"] = await self.projects_intel.enrich_projects()
        results["ico"] = await self.ico_intel.classify_launches()
        results["activities"] = await self.activities_intel.process_activities()
        results["unlocks"] = await self.unlocks_intel.build_unlock_calendar()
        results["news"] = await self.news_intel.process_news_events()
        return results
