"""
Fractal Module Configuration
=============================
Single source of truth for all module settings.
Module code MUST NOT read os.environ directly — everything comes through this config.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class FractalConfig:
    """Immutable config injected at module init time."""
    mongo_url: str
    db_name: str = "intelligence_engine"

    # Horizons to generate
    horizons: List[int] = field(default_factory=lambda: [7, 30])

    # Freeze guard
    freeze_enabled: bool = False

    # Thresholds
    drift_max: float = 0.25
    calibration_max: float = 0.20

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_cron: str = "0 10 * * *"  # 00:10 UTC daily

    # Collections
    forecasts_collection: str = "exchange_forecasts"
    runs_collection: str = "exchange_forecast_runs"
    regime_signals_collection: str = "regime_signals"

    # Assets
    assets: List[str] = field(default_factory=lambda: ["BTC"])
