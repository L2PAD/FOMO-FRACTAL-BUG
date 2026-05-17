"""
Funding Intelligence
====================
Builds intelligence from canonical funding events:
- Coinvest patterns (who invests together)
- Round clustering (group by project/date)
- Backer patterns (investor behavior)
- Investor profiles
"""
from datetime import datetime, timezone
from collections import defaultdict
from intelligence_os.core.logging_config import get_logger
from intelligence_os.core.ids import make_edge_id

log = get_logger("domain.funding")


class FundingIntelligence:
    def __init__(self, db):
        self.db = db

    async def build_coinvest_patterns(self) -> dict:
        """Find investors who co-invest together."""
        rounds = self.db["canonical_events"].find({"event_type": "funding_round"})
        coinvest_map = defaultdict(lambda: defaultdict(int))
        round_count = 0

        async for r in rounds:
            round_count += 1
            investors = r.get("data", {}).get("investors", [])
            if not isinstance(investors, list):
                continue
            for i, inv_a in enumerate(investors):
                for inv_b in investors[i + 1:]:
                    key = tuple(sorted([str(inv_a), str(inv_b)]))
                    coinvest_map[key[0]][key[1]] += 1

        # Store top coinvest pairs
        pairs_stored = 0
        now = datetime.now(timezone.utc).isoformat()
        for inv_a, partners in coinvest_map.items():
            for inv_b, count in partners.items():
                if count >= 2:
                    await self.db["intel_coinvest_patterns"].update_one(
                        {"investor_a": inv_a, "investor_b": inv_b},
                        {
                            "$set": {
                                "coinvest_count": count,
                                "updated_at": now,
                            },
                            "$setOnInsert": {"created_at": now},
                        },
                        upsert=True,
                    )
                    pairs_stored += 1

        log.info(f"[FUNDING] Coinvest: {round_count} rounds → {pairs_stored} pairs")
        return {"rounds_analyzed": round_count, "coinvest_pairs": pairs_stored}

    async def build_investor_profiles(self) -> dict:
        """Build aggregated investor profiles from funding events."""
        rounds = self.db["canonical_events"].find({"event_type": "funding_round"})
        investor_stats = defaultdict(lambda: {
            "rounds": 0, "total_invested": 0, "projects": set(), "lead_rounds": 0
        })

        async for r in rounds:
            data = r.get("data", {})
            investors = data.get("investors", [])
            lead = data.get("lead_investor")
            amount = data.get("amount_usd", 0) or 0
            project = r.get("project_name", "")

            for inv in investors:
                inv_name = str(inv)
                investor_stats[inv_name]["rounds"] += 1
                investor_stats[inv_name]["total_invested"] += amount / max(len(investors), 1)
                investor_stats[inv_name]["projects"].add(project)
                if inv_name == lead:
                    investor_stats[inv_name]["lead_rounds"] += 1

        now = datetime.now(timezone.utc).isoformat()
        profiles_stored = 0
        for name, stats in investor_stats.items():
            await self.db["intel_investor_profiles"].update_one(
                {"name": name},
                {
                    "$set": {
                        "rounds_count": stats["rounds"],
                        "total_invested_usd": round(stats["total_invested"], 2),
                        "unique_projects": len(stats["projects"]),
                        "lead_rounds": stats["lead_rounds"],
                        "updated_at": now,
                    },
                    "$setOnInsert": {"name": name, "created_at": now},
                },
                upsert=True,
            )
            profiles_stored += 1

        log.info(f"[FUNDING] Profiles: {profiles_stored} investors profiled")
        return {"profiles": profiles_stored}

    async def get_graph_hooks(self) -> list[dict]:
        """Generate graph edges from funding intelligence."""
        edges = []
        cursor = self.db["canonical_events"].find({"event_type": "funding_round"})

        async for r in cursor:
            project_id = r.get("project_canonical_id")
            if not project_id:
                continue

            investors = r.get("data", {}).get("investors", [])
            for inv in investors:
                edges.append({
                    "from_id": f"fund:{str(inv).lower().replace(' ', '-')}",
                    "to_id": project_id,
                    "edge_type": "invested_in",
                    "layer": "KNOWLEDGE",
                    "source": "funding_intelligence",
                })

        return edges
