"""
Data Fusion Engine
==================

Объединяет данные из разных источников в единые события и сигналы.

Компоненты:
- Entity Fusion: BTC, bitcoin, BTCUSDT → единая сущность
- Event Fusion: funding + news + investor → единый funding event
- Signal Fusion: volume + OI + liquidations → market signal
"""

from .engine import DataFusionEngine, get_fusion_engine
from .models import (
    FusedEntity, FusedEvent, FusedSignal,
    FusionCandidate, FusionRule
)

__all__ = [
    "DataFusionEngine",
    "get_fusion_engine",
    "FusedEntity",
    "FusedEvent", 
    "FusedSignal",
    "FusionCandidate",
    "FusionRule"
]
