"""
Canonical Pipeline — The core canonicalization engine
======================================================
Processes raw data → resolves entities → merges or creates canonical entries.

THIS IS THE MOST IMPORTANT MODULE IN THE SYSTEM.

Rule: NO intelligence, graph, or signal module reads raw data directly.
Everything goes through canonical first.
"""
from datetime import datetime, timezone
from intelligence_os.core.ids import make_entity_id
from intelligence_os.core.enums import EventType, CanonicalStatus
from intelligence_os.core.logging_config import get_logger
from intelligence_os.canonical.resolver import CanonicalResolver
from intelligence_os.canonical.merger import CanonicalMerger
from intelligence_os.canonical.alias_store import AliasStore

log = get_logger("canonical.pipeline")


class CanonicalPipeline:
    def __init__(self, db):
        self.db = db
        self.alias_store = AliasStore(db)
        self.resolver = CanonicalResolver(db, self.alias_store)
        self.merger = CanonicalMerger(db, self.alias_store)

    # ═══════════════════════════════════════════════════════════════
    # PROJECTS: raw_projects + raw_market_data → canonical_projects
    # ═══════════════════════════════════════════════════════════════

    async def process_raw_projects(self, limit: int = 500) -> dict:
        processed, created, merged = 0, 0, 0
        now = datetime.now(timezone.utc).isoformat()

        for col_name in ["raw_projects", "raw_market_data"]:
            cursor = self.db[col_name].find(
                {"_canonicalized": {"$ne": True}}
            ).limit(limit)

            async for raw in cursor:
                raw_id = raw.get("_id")
                name = raw.get("name") or raw.get("project_name")
                symbol = raw.get("symbol")

                if not name:
                    await self.db[col_name].update_one(
                        {"_id": raw_id}, {"$set": {"_canonicalized": True}}
                    )
                    continue

                canonical = await self.resolver.resolve_project(name, symbol)

                if canonical:
                    await self.merger.merge_project(raw, canonical)
                    merged += 1
                else:
                    canonical_id = make_entity_id("project", name)
                    await self.db["canonical_projects"].insert_one({
                        "canonical_id": canonical_id,
                        "name": name,
                        "name_lower": name.strip().lower(),
                        "symbol": symbol.upper() if symbol else None,
                        "status": CanonicalStatus.ACTIVE.value,
                        "sources": [raw.get("source", "unknown")],
                        "metadata": {
                            "category": raw.get("category"),
                            "market_cap": raw.get("market_cap"),
                            "description": raw.get("description"),
                        },
                        "created_at": now,
                        "updated_at": now,
                        "last_seen": now,
                    })
                    await self.alias_store.add_alias(
                        "project", canonical_id, name, raw.get("source", "unknown")
                    )
                    created += 1

                await self.db[col_name].update_one(
                    {"_id": raw_id}, {"$set": {"_canonicalized": True}}
                )
                processed += 1

        log.info(f"[CANONICAL] Projects: processed={processed}, created={created}, merged={merged}")
        return {"processed": processed, "created": created, "merged": merged}

    # ═══════════════════════════════════════════════════════════════
    # TOKENS: raw_market_data → canonical_tokens
    # ═══════════════════════════════════════════════════════════════

    async def process_raw_tokens(self, limit: int = 500) -> dict:
        processed, created, merged = 0, 0, 0
        now = datetime.now(timezone.utc).isoformat()

        cursor = self.db["raw_market_data"].find(
            {"_token_canonicalized": {"$ne": True}, "symbol": {"$exists": True}}
        ).limit(limit)

        async for raw in cursor:
            raw_id = raw.get("_id")
            symbol = (raw.get("symbol") or "").upper()
            name = raw.get("name")

            if not symbol:
                await self.db["raw_market_data"].update_one(
                    {"_id": raw_id}, {"$set": {"_token_canonicalized": True}}
                )
                continue

            canonical = await self.resolver.resolve_token(symbol)

            if canonical:
                await self.merger.merge_token(raw, canonical)
                merged += 1
            else:
                canonical_id = make_entity_id("token", symbol)
                await self.db["canonical_tokens"].insert_one({
                    "canonical_id": canonical_id,
                    "symbol": symbol,
                    "name": name,
                    "name_lower": (name or "").strip().lower(),
                    "status": CanonicalStatus.ACTIVE.value,
                    "sources": [raw.get("source", "unknown")],
                    "market": {
                        "price_usd": raw.get("price_usd"),
                        "market_cap": raw.get("market_cap"),
                        "volume_24h": raw.get("volume_24h"),
                    },
                    "created_at": now,
                    "updated_at": now,
                })
                created += 1

            await self.db["raw_market_data"].update_one(
                {"_id": raw_id}, {"$set": {"_token_canonicalized": True}}
            )
            processed += 1

        log.info(f"[CANONICAL] Tokens: processed={processed}, created={created}, merged={merged}")
        return {"processed": processed, "created": created, "merged": merged}

    # ═══════════════════════════════════════════════════════════════
    # EVENTS: raw_funding + raw_ico + raw_activities + raw_unlocks + raw_news → canonical_events
    # ═══════════════════════════════════════════════════════════════

    async def process_raw_events(self, limit: int = 500) -> dict:
        processed, created = 0, 0
        now = datetime.now(timezone.utc).isoformat()

        event_sources = [
            ("raw_funding", EventType.FUNDING_ROUND),
            ("raw_ico", EventType.ICO),
            ("raw_activities", EventType.ACTIVITY),
            ("raw_unlocks", EventType.UNLOCK),
            ("raw_news", EventType.NEWS),
        ]

        for col_name, event_type in event_sources:
            cursor = self.db[col_name].find(
                {"_event_canonicalized": {"$ne": True}}
            ).limit(limit // len(event_sources))

            async for raw in cursor:
                raw_id = raw.get("_id")
                project_name = (
                    raw.get("project_name")
                    or raw.get("name")
                    or raw.get("title", "")
                )

                # Resolve project to canonical
                project_canonical = await self.resolver.resolve_project(
                    project_name, raw.get("symbol")
                )
                project_canonical_id = (
                    project_canonical.get("canonical_id") if project_canonical else None
                )

                event = {
                    "event_type": event_type.value,
                    "source": raw.get("source", "unknown"),
                    "project_name": project_name,
                    "project_canonical_id": project_canonical_id,
                    "symbol": raw.get("symbol"),
                    "data": {
                        k: v
                        for k, v in raw.items()
                        if k not in ("_id", "_raw_source", "_raw_fetched_at", "_canonicalized",
                                     "_event_canonicalized", "source", "domain")
                    },
                    "created_at": raw.get("fetched_at", now),
                    "canonicalized_at": now,
                }

                await self.db["canonical_events"].insert_one(event)
                created += 1

                await self.db[col_name].update_one(
                    {"_id": raw_id}, {"$set": {"_event_canonicalized": True}}
                )
                processed += 1

        log.info(f"[CANONICAL] Events: processed={processed}, created={created}")
        return {"processed": processed, "created": created}

    # ═══════════════════════════════════════════════════════════════
    # FULL PIPELINE
    # ═══════════════════════════════════════════════════════════════

    async def process_raw_funds(self, limit: int = 500) -> dict:
        """Extract funds/investors from funding events → canonical_funds."""
        processed, created, merged = 0, 0, 0
        now = datetime.now(timezone.utc).isoformat()

        # Source 1: funding events in canonical_events
        cursor = self.db["canonical_events"].find(
            {"event_type": "funding_round", "_funds_extracted": {"$ne": True}}
        ).limit(limit)

        async for event in cursor:
            data = event.get("data", {})
            investors = data.get("investors", [])
            if not isinstance(investors, list):
                investors = []

            for inv_name in investors:
                inv_name = str(inv_name).strip()
                if not inv_name or len(inv_name) < 2:
                    continue

                canonical = await self.resolver.resolve_fund(inv_name)
                if canonical:
                    await self.merger.merge_fund({"name": inv_name, "source": event.get("source")}, canonical)
                    merged += 1
                else:
                    canonical_id = make_entity_id("fund", inv_name)
                    await self.db["canonical_funds"].insert_one({
                        "canonical_id": canonical_id,
                        "name": inv_name,
                        "name_lower": inv_name.lower(),
                        "status": CanonicalStatus.ACTIVE.value,
                        "sources": [event.get("source", "unknown")],
                        "metadata": {},
                        "created_at": now,
                        "updated_at": now,
                        "last_seen": now,
                    })
                    await self.alias_store.add_alias("fund", canonical_id, inv_name, event.get("source", "unknown"))
                    created += 1

            await self.db["canonical_events"].update_one(
                {"_id": event["_id"]}, {"$set": {"_funds_extracted": True}}
            )
            processed += 1

        # Source 2: existing graph_nodes of type fund/investor
        fund_nodes = self.db["graph_nodes"].find(
            {"type": {"$in": ["fund", "investor", "vc"]}, "_fund_canonicalized": {"$ne": True}}
        ).limit(limit)

        async for node in fund_nodes:
            name = node.get("label") or node.get("name")
            if not name:
                continue

            canonical = await self.resolver.resolve_fund(name)
            if not canonical:
                canonical_id = make_entity_id("fund", name)
                await self.db["canonical_funds"].insert_one({
                    "canonical_id": canonical_id,
                    "name": name,
                    "name_lower": name.lower(),
                    "status": CanonicalStatus.ACTIVE.value,
                    "sources": ["graph_nodes"],
                    "metadata": {"entity_id": node.get("entity_id")},
                    "created_at": now,
                    "updated_at": now,
                })
                await self.alias_store.add_alias("fund", canonical_id, name, "graph_nodes")
                created += 1
            else:
                merged += 1

            await self.db["graph_nodes"].update_one(
                {"_id": node["_id"]}, {"$set": {"_fund_canonicalized": True}}
            )
            processed += 1

        log.info(f"[CANONICAL] Funds: processed={processed}, created={created}, merged={merged}")
        return {"processed": processed, "created": created, "merged": merged}

    async def process_raw_persons(self, limit: int = 500) -> dict:
        """Extract persons from graph nodes and funding data → canonical_persons."""
        processed, created, merged = 0, 0, 0
        now = datetime.now(timezone.utc).isoformat()

        # Source: graph_nodes of type person
        person_nodes = self.db["graph_nodes"].find(
            {"type": "person", "_person_canonicalized": {"$ne": True}}
        ).limit(limit)

        async for node in person_nodes:
            name = node.get("label") or node.get("name")
            if not name:
                continue

            canonical = await self.resolver.resolve_person(name)
            if not canonical:
                canonical_id = make_entity_id("person", name)
                await self.db["canonical_persons"].insert_one({
                    "canonical_id": canonical_id,
                    "name": name,
                    "name_lower": name.lower(),
                    "status": CanonicalStatus.ACTIVE.value,
                    "sources": ["graph_nodes"],
                    "metadata": {
                        "entity_id": node.get("entity_id"),
                        "twitter": node.get("twitter"),
                        "role": node.get("role"),
                    },
                    "created_at": now,
                    "updated_at": now,
                })
                await self.alias_store.add_alias("person", canonical_id, name, "graph_nodes")
                created += 1
            else:
                merged += 1

            await self.db["graph_nodes"].update_one(
                {"_id": node["_id"]}, {"$set": {"_person_canonicalized": True}}
            )
            processed += 1

        # Source 2: twitter actors from actor_signal_events
        actor_handles = await self.db["actor_signal_events"].distinct("actor_handle")
        for handle in actor_handles[:limit]:
            if not handle:
                continue
            canonical = await self.resolver.resolve_person(handle)
            if not canonical:
                existing = await self.db["canonical_persons"].find_one(
                    {"name_lower": handle.lower()}, {"_id": 1}
                )
                if not existing:
                    canonical_id = make_entity_id("person", handle)
                    await self.db["canonical_persons"].insert_one({
                        "canonical_id": canonical_id,
                        "name": handle,
                        "name_lower": handle.lower(),
                        "status": CanonicalStatus.ACTIVE.value,
                        "sources": ["twitter"],
                        "metadata": {"twitter_handle": handle},
                        "created_at": now,
                        "updated_at": now,
                    })
                    created += 1
                    processed += 1

        log.info(f"[CANONICAL] Persons: processed={processed}, created={created}, merged={merged}")
        return {"processed": processed, "created": created, "merged": merged}

    async def run_full(self, limit: int = 500) -> dict:
        log.info("[CANONICAL] Starting full canonicalization pipeline")

        projects = await self.process_raw_projects(limit)
        tokens = await self.process_raw_tokens(limit)
        events = await self.process_raw_events(limit)
        funds = await self.process_raw_funds(limit)
        persons = await self.process_raw_persons(limit)

        result = {
            "projects": projects,
            "tokens": tokens,
            "events": events,
            "funds": funds,
            "persons": persons,
        }
        log.info(f"[CANONICAL] Full pipeline complete: {result}")
        return result

    async def get_stats(self) -> dict:
        stats = {}
        for name in ["canonical_projects", "canonical_funds", "canonical_persons",
                      "canonical_tokens", "canonical_events"]:
            stats[name] = await self.db[name].estimated_document_count()
        return stats
