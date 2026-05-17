"""
Canonical Resolver — Entity resolution engine
===============================================
Resolves raw entity references to their canonical IDs.
Resolution order: exact → alias → symbol → fuzzy

Rule: ONE canonical_id per real-world entity.
"""
import re
from difflib import SequenceMatcher
from intelligence_os.core.config import FUZZY_MATCH_THRESHOLD, SYMBOL_MATCH_BOOST
from intelligence_os.core.ids import make_entity_id
from intelligence_os.core.logging_config import get_logger

log = get_logger("canonical.resolver")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


class CanonicalResolver:
    def __init__(self, db, alias_store):
        self.db = db
        self.alias_store = alias_store

    async def resolve_project(self, name: str, symbol: str = None) -> dict | None:
        if not name:
            return None

        # 1. Exact match by name
        canon = await self.db["canonical_projects"].find_one(
            {"name_lower": name.strip().lower()}, {"_id": 0}
        )
        if canon:
            return canon

        # 2. Symbol match
        if symbol:
            canon = await self.db["canonical_projects"].find_one(
                {"symbol": symbol.upper()}, {"_id": 0}
            )
            if canon:
                return canon

        # 3. Alias match
        canonical_id = await self.alias_store.find_by_alias("project", name)
        if canonical_id:
            canon = await self.db["canonical_projects"].find_one(
                {"canonical_id": canonical_id}, {"_id": 0}
            )
            if canon:
                return canon

        # 4. Fuzzy match
        best, best_score = None, 0.0
        cursor = self.db["canonical_projects"].find({}, {"_id": 0}).limit(2000)
        async for c in cursor:
            score = _sim(name, c.get("name", ""))
            if symbol and c.get("symbol") and symbol.upper() == c["symbol"].upper():
                score = max(score, SYMBOL_MATCH_BOOST)
            if score > best_score:
                best, best_score = c, score

        if best_score >= FUZZY_MATCH_THRESHOLD:
            log.info(f"Fuzzy resolved: '{name}' → '{best.get('name')}' (score={best_score:.2f})")
            return best

        return None

    async def resolve_fund(self, name: str) -> dict | None:
        if not name:
            return None

        canon = await self.db["canonical_funds"].find_one(
            {"name_lower": name.strip().lower()}, {"_id": 0}
        )
        if canon:
            return canon

        canonical_id = await self.alias_store.find_by_alias("fund", name)
        if canonical_id:
            return await self.db["canonical_funds"].find_one(
                {"canonical_id": canonical_id}, {"_id": 0}
            )

        # Fuzzy
        best, best_score = None, 0.0
        cursor = self.db["canonical_funds"].find({}, {"_id": 0}).limit(1000)
        async for c in cursor:
            score = _sim(name, c.get("name", ""))
            if score > best_score:
                best, best_score = c, score

        return best if best_score >= FUZZY_MATCH_THRESHOLD else None

    async def resolve_person(self, name: str) -> dict | None:
        if not name:
            return None

        canon = await self.db["canonical_persons"].find_one(
            {"name_lower": name.strip().lower()}, {"_id": 0}
        )
        if canon:
            return canon

        canonical_id = await self.alias_store.find_by_alias("person", name)
        if canonical_id:
            return await self.db["canonical_persons"].find_one(
                {"canonical_id": canonical_id}, {"_id": 0}
            )

        return None

    async def resolve_token(self, symbol: str) -> dict | None:
        if not symbol:
            return None

        return await self.db["canonical_tokens"].find_one(
            {"symbol": symbol.upper()}, {"_id": 0}
        )
