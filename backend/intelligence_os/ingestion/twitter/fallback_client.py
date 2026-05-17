"""
Twitter Fallback Client (L3 — Backup)
=======================================
When both cookies and Playwright fail, infer activity from:
1. Graph data — recent edges for actor's tokens
2. News mentions — recent news about actor's tokens
3. Historical actor continuity — last known signals
"""
from datetime import datetime, timezone, timedelta
from intelligence_os.core.logging_config import get_logger

log = get_logger("twitter.fallback")


class TwitterFallbackClient:
    def __init__(self, db):
        self.db = db

    async def infer(self, username: str) -> list[dict]:
        """Infer signals from indirect sources when Twitter is dead."""
        results = []
        now = datetime.now(timezone.utc)

        # 1. Last known signals for this actor
        recent_signals = await self.db["actor_signal_events"].find(
            {"actor_handle": username},
            {"_id": 0, "token": 1, "signal_type": 1, "created_at": 1},
        ).sort("created_at", -1).limit(10).to_list(length=10)

        tokens = list(set(s.get("token", "") for s in recent_signals if s.get("token")))

        if not tokens:
            log.info(f"[FALLBACK] {username}: No known tokens, skipping")
            return results

        # 2. Graph edges for these tokens (recent activity)
        for token in tokens[:5]:
            edge_count = await self.db["graph_edges"].count_documents({
                "to_node_id": f"token:{token}",
            })
            if edge_count > 0:
                results.append({
                    "text": f"Graph activity detected for {token} (actor: {username})",
                    "token": token,
                    "actor": username,
                    "source": "graph_inference",
                    "inferred": True,
                    "evidence_count": edge_count,
                    "created_at": now.isoformat(),
                })

        # 3. Recent news for these tokens
        for token in tokens[:3]:
            news_count = await self.db["canonical_events"].count_documents({
                "event_type": "news_event",
                "symbol": token,
            })
            if news_count > 0:
                results.append({
                    "text": f"News activity for {token} ({news_count} articles, actor: {username})",
                    "token": token,
                    "actor": username,
                    "source": "news_inference",
                    "inferred": True,
                    "evidence_count": news_count,
                    "created_at": now.isoformat(),
                })

        log.info(f"[FALLBACK] {username}: inferred {len(results)} signals from {len(tokens)} tokens")
        return results

    async def save_inferred_to_db(self, results: list[dict]) -> int:
        """Save inferred signals to actor_signal_events."""
        if not results:
            return 0

        events = []
        for r in results:
            events.append({
                "actor_handle": r.get("actor", "unknown"),
                "text": r.get("text", ""),
                "token": r.get("token", ""),
                "signal_type": "inferred",
                "source": r.get("source", "fallback"),
                "inferred": True,
                "created_at": r.get("created_at"),
                "enriched": False,
                "metrics": {"evidence_count": r.get("evidence_count", 0)},
            })

        if events:
            await self.db["actor_signal_events"].insert_many(events)

        return len(events)
