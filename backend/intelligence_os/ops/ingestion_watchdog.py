"""
Ingestion Watchdog — System-wide data flow monitoring
=====================================================
Monitors ALL data streams, not just Twitter.
"""
from datetime import datetime, timezone, timedelta
from intelligence_os.ops.twitter_watchdog import TwitterWatchdog
from intelligence_os.core.logging_config import get_logger

log = get_logger("ops.ingestion_watchdog")


class IngestionWatchdog:
    def __init__(self, db):
        self.db = db
        self.twitter_watchdog = TwitterWatchdog(db)

    async def check(self) -> dict:
        now = datetime.now(timezone.utc)
        six_hours_ago = (now - timedelta(hours=6)).isoformat()

        # Twitter health
        twitter = await self.twitter_watchdog.check()

        # Dataset growth
        dataset_growth = await self.db["dataset_entries"].count_documents(
            {"meta.created_at": {"$gte": six_hours_ago}}
        )

        # Graph growth
        graph_growth = await self.db["graph_edges"].count_documents(
            {"last_seen": {"$gte": six_hours_ago}}
        )

        # Canonical growth
        canonical_growth = await self.db["canonical_events"].count_documents(
            {"canonicalized_at": {"$gte": six_hours_ago}}
        )

        # Signal flow
        signals_6h = await self.db["signal_log"].count_documents(
            {"created_at": {"$gte": six_hours_ago}}
        )

        # News flow
        news_6h = await self.db["raw_news"].count_documents(
            {"_raw_fetched_at": {"$gte": six_hours_ago}}
        )

        # Aggregate status
        status = self._aggregate(twitter, dataset_growth, graph_growth, signals_6h)

        report = {
            "status": status,
            "timestamp": now.isoformat(),
            "twitter": twitter,
            "dataset_growth_6h": dataset_growth,
            "graph_growth_6h": graph_growth,
            "canonical_growth_6h": canonical_growth,
            "signals_6h": signals_6h,
            "news_6h": news_6h,
        }

        log.info(
            f"[INGESTION WATCHDOG] {status} | "
            f"twitter={twitter['status']} dataset={dataset_growth} "
            f"graph={graph_growth} signals={signals_6h} news={news_6h}"
        )
        return report

    def _aggregate(self, twitter, dataset_growth, graph_growth, signals_6h) -> str:
        if twitter["status"] == "DEAD" and dataset_growth == 0 and signals_6h == 0:
            return "DEAD"
        if twitter["status"] == "DEAD" or dataset_growth == 0:
            return "DEGRADED"
        if twitter["status"] == "DEGRADED" or dataset_growth < 5:
            return "DEGRADED"
        return "OK"
