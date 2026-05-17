"""
Telegram Integration for Scheduler
===================================
Integrates scheduler health events with Telegram alerts.
Sends real-time notifications on source failures, recoveries, etc.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SchedulerTelegramIntegration:
    """
    Bridges scheduler events to Telegram alerts.
    """
    
    def __init__(self, db):
        self.db = db
        self._alert_engine = None
    
    def _get_alert_engine(self):
        """Lazy load alert engine"""
        if self._alert_engine is None:
            from modules.telegram_service.alert_engine import get_alert_engine
            self._alert_engine = get_alert_engine(self.db)
        return self._alert_engine
    
    async def on_source_down(self, source_id: str, consecutive_fails: int, error: str = None):
        """Called when source goes down (auto-paused)"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="source_down",
                data={
                    "source": source_id,
                    "downtime": f"{consecutive_fails} consecutive failures",
                    "error": error or "Unknown error"
                },
                entity=source_id
            )
            logger.info(f"[TelegramIntegration] Sent source_down alert for {source_id}")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send source_down alert: {e}")
    
    async def on_source_recovered(self, source_id: str):
        """Called when source recovers"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="source_recovered",
                data={"source": source_id},
                entity=source_id
            )
            logger.info(f"[TelegramIntegration] Sent source_recovered alert for {source_id}")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send source_recovered alert: {e}")
    
    async def on_source_degraded(self, source_id: str, health_score: float, error_rate: float):
        """Called when source is degraded but not down"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="source_degraded",
                data={
                    "source": source_id,
                    "error_rate": int(error_rate * 100),
                    "latency": health_score
                },
                entity=source_id
            )
            logger.info(f"[TelegramIntegration] Sent source_degraded alert for {source_id}")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send source_degraded alert: {e}")
    
    async def on_parser_failed(self, parser_name: str, error: str):
        """Called when parser fails"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="parser_failed",
                data={
                    "parser": parser_name,
                    "error": str(error)[:200]
                },
                entity=parser_name
            )
            logger.info(f"[TelegramIntegration] Sent parser_failed alert for {parser_name}")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send parser_failed alert: {e}")
    
    async def on_parser_recovered(self, parser_name: str):
        """Called when parser recovers after failures"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="parser_recovered",
                data={"parser": parser_name},
                entity=parser_name
            )
            logger.info(f"[TelegramIntegration] Sent parser_recovered alert for {parser_name}")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send parser_recovered alert: {e}")
    
    async def on_scheduler_job_failed(self, job_name: str, error: str):
        """Called when scheduler job fails"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="scheduler_job_failed",
                data={
                    "job": job_name,
                    "error": str(error)[:200]
                },
                entity=job_name
            )
            logger.info(f"[TelegramIntegration] Sent scheduler_job_failed alert for {job_name}")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send scheduler_job_failed alert: {e}")
    
    async def on_graph_growth_anomaly(self, nodes_delta: int, edges_delta: int):
        """Called when graph growth is anomalous"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="graph_growth_anomaly",
                data={
                    "count": nodes_delta,
                    "description": f"+{nodes_delta} nodes, +{edges_delta} edges"
                },
                entity="knowledge_graph"
            )
            logger.info(f"[TelegramIntegration] Sent graph_growth_anomaly alert")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send graph_growth_anomaly alert: {e}")
    
    async def on_momentum_spike(self, entity_id: str, entity_type: str, velocity: float, score: float):
        """Called when entity momentum spikes"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="entity_momentum_spike",
                data={
                    "entity": entity_id,
                    "entity_type": entity_type,
                    "velocity": int(velocity),
                    "score": int(score)
                },
                entity=entity_id
            )
            logger.info(f"[TelegramIntegration] Sent momentum_spike alert for {entity_id}")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send momentum_spike alert: {e}")
    
    async def on_new_entity_discovered(self, entity_id: str, entity_type: str, source: str):
        """Called when new entity is discovered"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="entity_new_discovery",
                data={
                    "entity": entity_id,
                    "entity_type": entity_type,
                    "description": f"Discovered from {source}"
                },
                entity=entity_id
            )
            logger.info(f"[TelegramIntegration] Sent new_entity alert for {entity_id}")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send new_entity alert: {e}")
    
    async def on_narrative_detected(self, narrative: str, score: float, entities_count: int):
        """Called when new narrative is detected"""
        try:
            engine = self._get_alert_engine()
            await engine.emit_alert(
                alert_code="narrative_detected",
                data={
                    "narrative": narrative,
                    "score": int(score),
                    "count": entities_count
                },
                entity=narrative
            )
            logger.info(f"[TelegramIntegration] Sent narrative_detected alert for {narrative}")
        except Exception as e:
            logger.error(f"[TelegramIntegration] Failed to send narrative_detected alert: {e}")


# Singleton instance
_integration: Optional[SchedulerTelegramIntegration] = None


def get_telegram_integration(db) -> SchedulerTelegramIntegration:
    """Get or create telegram integration"""
    global _integration
    if _integration is None:
        _integration = SchedulerTelegramIntegration(db)
    return _integration
