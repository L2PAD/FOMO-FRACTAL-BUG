"""
Fractal Module Isolation Tests
================================
Tests that the Fractal module can be initialized without global state.
Verifies config injection, repo binding, and freeze guard.
"""

import pytest
import os
import sys

# Add backend root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestFractalConfig:
    """Test FractalConfig dataclass."""

    def test_default_config(self):
        from forecast.config import FractalConfig
        config = FractalConfig(mongo_url="mongodb://test:27017")
        assert config.db_name == "intelligence_engine"
        assert config.horizons == [7, 30]
        assert config.freeze_enabled is False
        assert config.scheduler_enabled is True
        assert config.forecasts_collection == "exchange_forecasts"
        assert config.assets == ["BTC"]

    def test_custom_config(self):
        from forecast.config import FractalConfig
        config = FractalConfig(
            mongo_url="mongodb://custom:27017",
            db_name="test_db",
            freeze_enabled=True,
            horizons=[7],
            scheduler_enabled=False,
        )
        assert config.db_name == "test_db"
        assert config.freeze_enabled is True
        assert config.horizons == [7]
        assert config.scheduler_enabled is False

    def test_config_is_frozen(self):
        from forecast.config import FractalConfig
        config = FractalConfig(mongo_url="mongodb://test:27017")
        with pytest.raises(Exception):
            config.db_name = "hacked"


class TestFractalModule:
    """Test module initialization."""

    def test_module_init_from_config(self):
        from forecast.config import FractalConfig
        from forecast.module import init_fractal_module
        from forecast.repo import _config

        config = FractalConfig(mongo_url="mongodb://test-isolation:27017")
        # Reset to test fresh init
        import forecast.module as mod
        mod._initialized = False
        import forecast.repo as repo
        repo._config = None

        init_fractal_module(config)
        assert repo._config is not None
        assert repo._config.mongo_url == "mongodb://test-isolation:27017"

    def test_repo_fails_without_init(self):
        import forecast.repo as repo
        old = repo._config
        repo._config = None
        with pytest.raises(RuntimeError, match="not initialized"):
            repo._cfg()
        repo._config = old  # restore

    def test_get_config_from_env(self):
        os.environ["MONGO_URL"] = "mongodb://env-test:27017"
        os.environ["DB_NAME"] = "test_env_db"
        os.environ["SYSTEM_FROZEN"] = "true"

        from forecast.module import get_config_from_env
        config = get_config_from_env()
        assert config.mongo_url == "mongodb://env-test:27017"
        assert config.db_name == "test_env_db"
        assert config.freeze_enabled is True

        # Cleanup
        del os.environ["SYSTEM_FROZEN"]


class TestJobDefinitions:
    """Test that job definitions export correctly."""

    def test_fractal_jobs_exported(self):
        # Init module first
        from forecast.config import FractalConfig
        from forecast.module import init_fractal_module
        import forecast.module as mod
        mod._initialized = False
        import forecast.repo as repo
        repo._config = None

        config = FractalConfig(mongo_url=os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        init_fractal_module(config)

        from forecast.jobs import get_fractal_jobs
        jobs = get_fractal_jobs()
        assert len(jobs) == 1
        assert jobs[0].name == "fractal:daily"
        assert jobs[0].schedule == "10 0 * * *"
        assert jobs[0].run_on_startup is True
        assert callable(jobs[0].handler)

    def test_job_handler_is_callable(self):
        from forecast.jobs import get_fractal_jobs
        jobs = get_fractal_jobs()
        for job in jobs:
            assert callable(job.handler), f"Job {job.name} handler is not callable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
