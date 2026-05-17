"""
Intelligence Module

Core components:
- Root Event Model (articles → updates → root_events)
- Scoring Pipeline (sentiment, importance, confidence, rumor)
- Entity Momentum Engine (structural influence tracking)
- Compute Separation (ingestion/intelligence/query clusters)
- Narrative Entity Linking (narrative → entity bidirectional links)
"""

from .root_event import (
    RootEvent,
    EventUpdate,
    EventUpdateType,
    LifecycleStage,
    RootEventService
)

from .scoring_pipeline import (
    IntelligenceScores,
    ScoringPipeline,
    scoring_pipeline
)

from .entity_momentum import (
    EntityMomentumEngine,
    get_momentum_engine
)

from .compute_separation import (
    ComputeJobQueue,
    ProjectionLayer,
    ComputeCluster,
    JobPriority,
    JobStatus,
    get_compute_job_queue,
    get_projection_layer
)

from .narrative_entity_linking import (
    NarrativeEntityLinker,
    get_narrative_entity_linker
)

__all__ = [
    "RootEvent",
    "EventUpdate",
    "EventUpdateType",
    "LifecycleStage",
    "RootEventService",
    "IntelligenceScores",
    "ScoringPipeline",
    "scoring_pipeline",
    # Momentum
    "EntityMomentumEngine",
    "get_momentum_engine",
    # Compute Separation
    "ComputeJobQueue",
    "ProjectionLayer",
    "ComputeCluster",
    "JobPriority",
    "JobStatus",
    "get_compute_job_queue",
    "get_projection_layer",
    # Narrative Linking
    "NarrativeEntityLinker",
    "get_narrative_entity_linker"
]
