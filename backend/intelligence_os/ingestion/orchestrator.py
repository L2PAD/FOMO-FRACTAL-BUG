"""
Ingestion Orchestrator
======================
The brain of the ingestion layer.
Runs all parsers from the SOURCE_MATRIX, handles fallbacks, tracks health.

Rule: source → parser → fallback → validation → raw storage
"""
import time
from intelligence_os.ops.parser_registry import get_enabled_sources, ParserSpec
from intelligence_os.ops.health_service import HealthService
from intelligence_os.ops.fallback_manager import FallbackManager
from intelligence_os.ops.trust_service import TrustService
from intelligence_os.core.logging_config import get_logger

log = get_logger("orchestrator")


class IngestionOrchestrator:
    def __init__(self, db, parser_factory):
        self.db = db
        self.parser_factory = parser_factory
        self.health = HealthService(db)
        self.fallback = FallbackManager(parser_factory)
        self.trust = TrustService(db)

    async def run_source(self, spec: ParserSpec, query: dict | None = None) -> dict:
        t0 = time.time()
        try:
            parser = self.parser_factory(spec.name)
            rows = await parser.fetch(query)
            validated = parser.validate(rows)
            saved = await parser.save_raw(validated)
            duration = round(time.time() - t0, 2)

            await self.health.mark_success(spec.name, saved, duration)
            await self.trust.update_trust(spec.name)

            return {
                "source": spec.name,
                "domain": spec.domain.value,
                "ok": True,
                "saved": saved,
                "duration_sec": duration,
            }
        except Exception as e:
            duration = round(time.time() - t0, 2)
            log.exception(f"Parser failed: {spec.name}")
            await self.health.mark_failure(spec.name, str(e), duration)

            if spec.fallback_chain:
                fallback_result = await self.fallback.try_chain(spec, query)
                if fallback_result.get("ok"):
                    await self.trust.update_trust(spec.name)
                return fallback_result

            return {
                "source": spec.name,
                "domain": spec.domain.value,
                "ok": False,
                "saved": 0,
                "error": str(e)[:200],
                "duration_sec": duration,
            }

    async def run_all(self) -> dict:
        sources = get_enabled_sources()
        results = []
        total_saved = 0

        log.info(f"[INGESTION] Starting cycle: {len(sources)} sources")

        for spec in sources:
            result = await self.run_source(spec)
            results.append(result)
            total_saved += result.get("saved", 0)

        ok_count = sum(1 for r in results if r.get("ok"))
        fail_count = sum(1 for r in results if not r.get("ok"))

        log.info(
            f"[INGESTION] Cycle complete: {ok_count} OK, {fail_count} FAIL, "
            f"{total_saved} total saved"
        )

        return {
            "ok": True,
            "sources_total": len(sources),
            "sources_ok": ok_count,
            "sources_fail": fail_count,
            "total_saved": total_saved,
            "results": results,
        }

    async def run_domain(self, domain) -> dict:
        from intelligence_os.ops.parser_registry import get_sources_by_domain
        sources = get_sources_by_domain(domain)
        results = []
        for spec in sources:
            results.append(await self.run_source(spec))
        return {"domain": domain.value, "results": results}
