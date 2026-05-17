"""
Fractal Module Entry Point
===========================
Creates and initializes the module from FractalConfig.
This is the ONLY place where config → repo binding happens.
"""

from forecast.config import FractalConfig
from forecast.repo import init_repo


_initialized = False


def init_fractal_module(config: FractalConfig):
    """Initialize the fractal module with injected config.
    Idempotent — safe to call multiple times."""
    global _initialized
    if _initialized:
        return

    init_repo(config)
    _initialized = True
    print(f"[Fractal] Module initialized: db={config.db_name}, freeze={config.freeze_enabled}, "
          f"horizons={config.horizons}, scheduler={config.scheduler_enabled}")


def get_config_from_env() -> FractalConfig:
    """Build FractalConfig from environment variables.
    This is the ONLY function that reads os.environ — called once at startup."""
    import os
    return FractalConfig(
        mongo_url=os.environ.get("MONGO_URL", ""),
        db_name=os.environ.get("DB_NAME", "intelligence_engine"),
        freeze_enabled=os.environ.get("SYSTEM_FROZEN", "false").lower() == "true",
        scheduler_enabled=os.environ.get("FORECAST_SCHEDULER_ENABLED", "true").lower() == "true",
    )
