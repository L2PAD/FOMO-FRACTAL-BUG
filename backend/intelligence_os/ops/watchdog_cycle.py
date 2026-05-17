"""
Watchdog Cycle — Main watchdog orchestration
==============================================
Runs every 15 minutes. Checks health, recovers, logs incidents.
"""
from intelligence_os.ops.ingestion_watchdog import IngestionWatchdog
from intelligence_os.ops.recovery_manager import RecoveryManager
from intelligence_os.ops.incident_logger import IncidentLogger
from intelligence_os.core.logging_config import get_logger

log = get_logger("ops.watchdog_cycle")


class WatchdogCycle:
    def __init__(self, db):
        self.db = db
        self.watchdog = IngestionWatchdog(db)
        self.recovery = RecoveryManager(db)
        self.incident_logger = IncidentLogger(db)

    async def run(self) -> dict:
        """Execute a complete watchdog check + recovery cycle."""
        report = await self.watchdog.check()

        if report["status"] != "OK":
            # Take recovery actions
            actions = await self.recovery.recover(report)

            # Log incident
            await self.incident_logger.log_incident(
                kind="INGESTION",
                status=report["status"],
                payload={
                    "twitter": report.get("twitter", {}),
                    "dataset_growth_6h": report.get("dataset_growth_6h"),
                    "graph_growth_6h": report.get("graph_growth_6h"),
                    "signals_6h": report.get("signals_6h"),
                },
                actions=actions,
            )

            log.warning(f"[WATCHDOG] Status={report['status']}, Actions={actions}")
        else:
            # Restore normal if was previously degraded
            await self.recovery.recover(report)
            log.info("[WATCHDOG] System OK")

        return report
