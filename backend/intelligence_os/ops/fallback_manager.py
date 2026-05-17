"""
Fallback Manager — Automatic failover between sources
======================================================
When primary parser fails, tries fallback chain in order.
"""
from intelligence_os.core.logging_config import get_logger

log = get_logger("fallback")


class FallbackManager:
    def __init__(self, parser_factory):
        self.parser_factory = parser_factory

    async def try_chain(self, spec, query=None) -> dict:
        for fallback_name in spec.fallback_chain:
            try:
                log.info(f"[FALLBACK] {spec.name} → trying {fallback_name}")
                parser = self.parser_factory(fallback_name)
                rows = await parser.fetch(query)
                validated = parser.validate(rows)
                saved = await parser.save_raw(validated)
                log.info(f"[FALLBACK] {fallback_name}: OK, saved={saved}")
                return {
                    "source": spec.name,
                    "fallback_used": fallback_name,
                    "ok": True,
                    "saved": saved,
                }
            except Exception as e:
                log.warning(f"[FALLBACK] {fallback_name} also failed: {e}")
                continue

        return {
            "source": spec.name,
            "ok": False,
            "saved": 0,
            "error": "All fallbacks exhausted",
        }
