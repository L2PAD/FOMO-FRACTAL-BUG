"""
Narrative Early Detection Layer

Detects emerging narratives BEFORE they become obvious.

Signals analyzed:
1. Event clustering - multiple events on same topic
2. Entity convergence - same entities appearing together
3. Topic momentum - rapid topic growth
4. Graph convergence - new cluster formation

This transforms reactive analytics into predictive intelligence.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from enum import Enum
import hashlib


class NarrativeLifecycle(str, Enum):
    """Narrative lifecycle states"""
    EMERGING = "emerging"      # Just detected, low confidence
    GROWING = "growing"        # Gaining momentum
    DOMINANT = "dominant"      # Peak attention
    FADING = "fading"          # Declining interest
    DEAD = "dead"              # No longer active


class EmergenceSignal(BaseModel):
    """Signal contributing to narrative emergence"""
    signal_type: str  # event_cluster, entity_convergence, topic_momentum, graph_cluster
    strength: float = Field(0.0, ge=0, le=100)
    evidence: List[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NarrativeEmergence(BaseModel):
    """
    Narrative with emergence scoring
    """
    id: str
    name: str
    canonical_name: str
    
    # Lifecycle
    lifecycle: NarrativeLifecycle = NarrativeLifecycle.EMERGING
    
    # Emergence scoring
    emergence_score: float = Field(0.0, ge=0, le=100)
    momentum_score: float = Field(0.0, ge=0, le=100)
    confidence: float = Field(0.0, ge=0, le=1)
    
    # Signal breakdown
    event_cluster_score: float = Field(0.0, ge=0, le=100)
    entity_overlap_score: float = Field(0.0, ge=0, le=100)
    topic_momentum_score: float = Field(0.0, ge=0, le=100)
    graph_cluster_score: float = Field(0.0, ge=0, le=100)
    
    # Signals
    signals: List[EmergenceSignal] = Field(default_factory=list)
    
    # Metrics
    event_count_7d: int = 0
    event_count_30d: int = 0
    entity_count: int = 0
    topic_count: int = 0
    
    # Top entities
    top_entities: List[Dict] = Field(default_factory=list)
    top_events: List[Dict] = Field(default_factory=list)
    top_topics: List[str] = Field(default_factory=list)
    
    # Timeline
    first_detected: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    peak_time: Optional[datetime] = None
    
    class Config:
        use_enum_values = True


# =============================================================================
# EMERGENCE THRESHOLDS
# =============================================================================

EMERGENCE_THRESHOLDS = {
    "emerging": 30,    # Score >= 30 = emerging
    "growing": 50,     # Score >= 50 = growing
    "dominant": 75,    # Score >= 75 = dominant
    "fading": 25,      # Score drops below 25 from higher state = fading
}

SIGNAL_WEIGHTS = {
    "event_cluster": 0.35,
    "entity_overlap": 0.25,
    "topic_momentum": 0.25,
    "graph_cluster": 0.15,
}


class NarrativeEarlyDetector:
    """
    Service for detecting emerging narratives
    """
    
    def __init__(self, db):
        self.db = db
        self.narratives = db.narratives
        self.topics = db.topics
        self.root_events = db.root_events
        self.topic_events = db.topic_events
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
    
    async def detect_emerging_narratives(self) -> List[NarrativeEmergence]:
        """
        Main detection job - find emerging narratives
        
        Should run every 30 minutes
        """
        emerging = []
        
        # Get active topics
        cursor = self.topics.find({
            "status": {"$ne": "archived"},
            "event_count": {"$gte": 2}
        })
        
        # Group topics by potential narrative
        topic_clusters = await self._cluster_related_topics(cursor)
        
        for cluster_name, topic_ids in topic_clusters.items():
            # Calculate emergence signals
            signals = await self._calculate_emergence_signals(topic_ids)
            
            # Calculate total emergence score
            emergence_score = self._calculate_emergence_score(signals)
            
            if emergence_score >= EMERGENCE_THRESHOLDS["emerging"]:
                narrative = await self._create_or_update_narrative(
                    cluster_name, topic_ids, signals, emergence_score
                )
                emerging.append(narrative)
        
        return emerging
    
    async def _cluster_related_topics(self, topics_cursor) -> Dict[str, List[str]]:
        """Group topics that might form a narrative"""
        clusters = {}
        
        async for topic in topics_cursor:
            topic_id = topic.get("id")
            narrative_id = topic.get("narrative_id")
            
            if narrative_id:
                # Already assigned to narrative
                if narrative_id not in clusters:
                    clusters[narrative_id] = []
                clusters[narrative_id].append(topic_id)
            else:
                # Check if topic keywords match existing clusters
                matched = False
                keywords = set(topic.get("keywords", []))
                entities = set(topic.get("entities", []))
                
                for cluster_name, cluster_topics in clusters.items():
                    # Get cluster keywords
                    cluster_keywords = set()
                    for ct_id in cluster_topics[:5]:
                        ct = await self.topics.find_one({"id": ct_id})
                        if ct:
                            cluster_keywords.update(ct.get("keywords", []))
                    
                    # Check overlap
                    if len(keywords & cluster_keywords) >= 2 or len(entities & cluster_keywords) >= 1:
                        clusters[cluster_name].append(topic_id)
                        matched = True
                        break
                
                if not matched:
                    # Create new cluster
                    cluster_name = topic.get("canonical_name", topic_id)
                    clusters[cluster_name] = [topic_id]
        
        return clusters
    
    async def _calculate_emergence_signals(
        self,
        topic_ids: List[str]
    ) -> Dict[str, EmergenceSignal]:
        """Calculate all emergence signals for a topic cluster"""
        signals = {}
        
        # 1. Event clustering signal
        signals["event_cluster"] = await self._calc_event_cluster_signal(topic_ids)
        
        # 2. Entity convergence signal
        signals["entity_overlap"] = await self._calc_entity_overlap_signal(topic_ids)
        
        # 3. Topic momentum signal
        signals["topic_momentum"] = await self._calc_topic_momentum_signal(topic_ids)
        
        # 4. Graph cluster signal
        signals["graph_cluster"] = await self._calc_graph_cluster_signal(topic_ids)
        
        return signals
    
    async def _calc_event_cluster_signal(
        self,
        topic_ids: List[str]
    ) -> EmergenceSignal:
        """
        Calculate event clustering signal
        
        High if multiple events on same topic in short time
        """
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        
        # Get events for these topics in last 7 days
        event_ids = set()
        for topic_id in topic_ids:
            links = await self.topic_events.find({
                "topic_id": topic_id,
                "linked_at": {"$gte": week_ago}
            }).to_list(length=100)
            
            for link in links:
                event_ids.add(link.get("event_id"))
        
        event_count = len(event_ids)
        
        # Score: 3+ events = strong signal
        strength = min(100, (event_count - 2) * 25) if event_count >= 3 else 0
        
        return EmergenceSignal(
            signal_type="event_cluster",
            strength=strength,
            evidence=[f"{event_count} events in 7 days"]
        )
    
    async def _calc_entity_overlap_signal(
        self,
        topic_ids: List[str]
    ) -> EmergenceSignal:
        """
        Calculate entity convergence signal
        
        High if same entities appear across topics
        """
        entity_counts = {}
        
        for topic_id in topic_ids:
            topic = await self.topics.find_one({"id": topic_id})
            if topic:
                for entity in topic.get("entities", []):
                    entity_counts[entity] = entity_counts.get(entity, 0) + 1
        
        # Count entities appearing in 2+ topics
        shared_entities = [e for e, c in entity_counts.items() if c >= 2]
        
        # Score: more shared entities = stronger signal
        strength = min(100, len(shared_entities) * 20)
        
        return EmergenceSignal(
            signal_type="entity_overlap",
            strength=strength,
            evidence=shared_entities[:5]
        )
    
    async def _calc_topic_momentum_signal(
        self,
        topic_ids: List[str]
    ) -> EmergenceSignal:
        """
        Calculate topic momentum signal
        
        High if topics are rapidly growing
        """
        momentum_sum = 0
        
        for topic_id in topic_ids:
            topic = await self.topics.find_one({"id": topic_id})
            if topic:
                momentum_sum += topic.get("momentum_score", 0)
        
        # Average momentum
        avg_momentum = momentum_sum / len(topic_ids) if topic_ids else 0
        
        return EmergenceSignal(
            signal_type="topic_momentum",
            strength=avg_momentum,
            evidence=[f"avg_momentum: {avg_momentum:.1f}"]
        )
    
    async def _calc_graph_cluster_signal(
        self,
        topic_ids: List[str]
    ) -> EmergenceSignal:
        """
        Calculate graph cluster signal
        
        High if entities form new clusters in graph
        """
        now = datetime.now(timezone.utc)
        month_ago = now - timedelta(days=30)
        
        # Get entities from topics
        entities = set()
        for topic_id in topic_ids:
            topic = await self.topics.find_one({"id": topic_id})
            if topic:
                entities.update(topic.get("entities", []))
        
        if not entities:
            return EmergenceSignal(signal_type="graph_cluster", strength=0)
        
        # Check for new edges between these entities
        new_edges = 0
        
        # Get node IDs for entities
        node_ids = []
        for entity in entities:
            node = await self.graph_nodes.find_one({
                "$or": [
                    {"entity_id": entity},
                    {"slug": entity}
                ]
            })
            if node:
                node_ids.append(node["id"])
        
        if len(node_ids) < 2:
            return EmergenceSignal(signal_type="graph_cluster", strength=0)
        
        # Count edges between these nodes created recently
        for i, n1 in enumerate(node_ids):
            for n2 in node_ids[i+1:]:
                edge = await self.graph_edges.find_one({
                    "$or": [
                        {"from_node_id": n1, "to_node_id": n2},
                        {"from_node_id": n2, "to_node_id": n1}
                    ],
                    "created_at": {"$gte": month_ago}
                })
                if edge:
                    new_edges += 1
        
        # Score
        strength = min(100, new_edges * 25)
        
        return EmergenceSignal(
            signal_type="graph_cluster",
            strength=strength,
            evidence=[f"{new_edges} new edges in cluster"]
        )
    
    def _calculate_emergence_score(
        self,
        signals: Dict[str, EmergenceSignal]
    ) -> float:
        """
        Calculate total emergence score from signals
        """
        score = 0.0
        
        for signal_type, weight in SIGNAL_WEIGHTS.items():
            if signal_type in signals:
                score += signals[signal_type].strength * weight
        
        return min(100, score)
    
    def _determine_lifecycle(
        self,
        emergence_score: float,
        prev_lifecycle: NarrativeLifecycle = None,
        prev_score: float = 0
    ) -> NarrativeLifecycle:
        """Determine lifecycle state from score"""
        if emergence_score >= EMERGENCE_THRESHOLDS["dominant"]:
            return NarrativeLifecycle.DOMINANT
        elif emergence_score >= EMERGENCE_THRESHOLDS["growing"]:
            return NarrativeLifecycle.GROWING
        elif emergence_score >= EMERGENCE_THRESHOLDS["emerging"]:
            return NarrativeLifecycle.EMERGING
        else:
            # Check if fading from higher state
            if prev_lifecycle in [NarrativeLifecycle.DOMINANT, NarrativeLifecycle.GROWING]:
                return NarrativeLifecycle.FADING
            return NarrativeLifecycle.DEAD
    
    async def _create_or_update_narrative(
        self,
        cluster_name: str,
        topic_ids: List[str],
        signals: Dict[str, EmergenceSignal],
        emergence_score: float
    ) -> NarrativeEmergence:
        """Create or update narrative from cluster"""
        narrative_id = f"n_{hashlib.md5(cluster_name.encode()).hexdigest()[:12]}"
        
        # Get existing
        existing = await self.narratives.find_one({"id": narrative_id})
        prev_lifecycle = NarrativeLifecycle(existing.get("lifecycle", "emerging")) if existing else None
        prev_score = existing.get("emergence_score", 0) if existing else 0
        
        # Determine lifecycle
        lifecycle = self._determine_lifecycle(emergence_score, prev_lifecycle, prev_score)
        
        # Collect top entities
        entity_counts = {}
        for topic_id in topic_ids:
            topic = await self.topics.find_one({"id": topic_id})
            if topic:
                for entity in topic.get("entities", []):
                    entity_counts[entity] = entity_counts.get(entity, 0) + 1
        
        top_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Count events
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        event_ids_7d = set()
        event_ids_30d = set()
        
        for topic_id in topic_ids:
            links_7d = await self.topic_events.find({
                "topic_id": topic_id,
                "linked_at": {"$gte": week_ago}
            }).to_list(length=100)
            
            links_30d = await self.topic_events.find({
                "topic_id": topic_id,
                "linked_at": {"$gte": month_ago}
            }).to_list(length=200)
            
            for link in links_7d:
                event_ids_7d.add(link.get("event_id"))
            for link in links_30d:
                event_ids_30d.add(link.get("event_id"))
        
        # Build narrative
        narrative = NarrativeEmergence(
            id=narrative_id,
            name=cluster_name.replace("_", " ").title(),
            canonical_name=cluster_name,
            lifecycle=lifecycle,
            emergence_score=round(emergence_score, 1),
            momentum_score=signals.get("topic_momentum", EmergenceSignal(signal_type="", strength=0)).strength,
            confidence=min(1.0, emergence_score / 100),
            event_cluster_score=signals.get("event_cluster", EmergenceSignal(signal_type="", strength=0)).strength,
            entity_overlap_score=signals.get("entity_overlap", EmergenceSignal(signal_type="", strength=0)).strength,
            topic_momentum_score=signals.get("topic_momentum", EmergenceSignal(signal_type="", strength=0)).strength,
            graph_cluster_score=signals.get("graph_cluster", EmergenceSignal(signal_type="", strength=0)).strength,
            signals=[s for s in signals.values()],
            event_count_7d=len(event_ids_7d),
            event_count_30d=len(event_ids_30d),
            entity_count=len(entity_counts),
            topic_count=len(topic_ids),
            top_entities=[{"entity": e, "count": c} for e, c in top_entities],
            top_topics=topic_ids[:5],
            first_detected=existing.get("first_detected", now) if existing else now,
            peak_time=now if lifecycle == NarrativeLifecycle.DOMINANT else existing.get("peak_time") if existing else None
        )
        
        # Save
        await self.narratives.update_one(
            {"id": narrative_id},
            {"$set": narrative.dict()},
            upsert=True
        )
        
        return narrative
    
    async def get_emerging_narratives(self, limit: int = 10) -> List[Dict]:
        """Get narratives in emerging state"""
        cursor = self.narratives.find({
            "lifecycle": NarrativeLifecycle.EMERGING.value
        }).sort("emergence_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_growing_narratives(self, limit: int = 10) -> List[Dict]:
        """Get narratives in growing state"""
        cursor = self.narratives.find({
            "lifecycle": NarrativeLifecycle.GROWING.value
        }).sort("emergence_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_dominant_narratives(self, limit: int = 10) -> List[Dict]:
        """Get dominant narratives"""
        cursor = self.narratives.find({
            "lifecycle": NarrativeLifecycle.DOMINANT.value
        }).sort("emergence_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_all_active_narratives(self, limit: int = 30) -> List[Dict]:
        """Get all non-dead narratives"""
        cursor = self.narratives.find({
            "lifecycle": {"$ne": NarrativeLifecycle.DEAD.value}
        }).sort("emergence_score", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
