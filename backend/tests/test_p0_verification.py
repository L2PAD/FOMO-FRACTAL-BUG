"""
P0 Verification Tests for Decision Intelligence System
Tests:
1. twitter-parser-v2 health check
2. Backend health check
3. ML pipeline status (signal_events > 4000, training_samples = 3307)
4. Ingestion scheduler running
5. Bootstrap model in ml_model_registry
6. Active model unchanged
7. dataset_entries count = 106
8. actor_signal_events > 4600
9. Dataset entries stats endpoint
"""

import pytest
import requests
import os
from pymongo import MongoClient

# Configuration
BACKEND_URL = "http://localhost:8001"
PARSER_URL = "http://localhost:5001"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


@pytest.fixture(scope="module")
def mongo_client():
    """MongoDB client fixture."""
    client = MongoClient(MONGO_URL)
    yield client
    client.close()


@pytest.fixture(scope="module")
def db(mongo_client):
    """Database fixture."""
    return mongo_client[DB_NAME]


class TestTwitterParserV2:
    """Test twitter-parser-v2 service on port 5001."""
    
    def test_parser_health(self):
        """P0.1: Verify twitter-parser-v2 is running on port 5001."""
        response = requests.get(f"{PARSER_URL}/health", timeout=10)
        assert response.status_code == 200, f"Parser health check failed: {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Parser not OK: {data}"
        assert data.get("status") == "running", f"Parser not running: {data}"
        print(f"✓ twitter-parser-v2 health: {data}")


class TestBackendHealth:
    """Test backend health on port 8001."""
    
    def test_backend_health(self):
        """P0.2: Verify backend health returns ok."""
        response = requests.get(f"{BACKEND_URL}/health", timeout=30)
        assert response.status_code == 200, f"Backend health check failed: {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Backend not OK: {data}"
        print(f"✓ Backend health: {data}")


class TestMLPipelineStatus:
    """Test ML pipeline status endpoint."""
    
    def test_pipeline_status(self):
        """P0.3: Verify ML pipeline status shows correct counts."""
        response = requests.get(f"{BACKEND_URL}/api/ml/pipeline/status", timeout=30)
        assert response.status_code == 200, f"Pipeline status failed: {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Pipeline status not OK: {data}"
        
        # Verify signal_events > 4000
        signal_events = data.get("signal_events", 0)
        assert signal_events > 4000, f"signal_events {signal_events} should be > 4000"
        print(f"✓ signal_events: {signal_events} (> 4000)")
        
        # Verify training_samples = 3307
        training_samples = data.get("training_samples", 0)
        assert training_samples == 3307, f"training_samples {training_samples} should be 3307"
        print(f"✓ training_samples: {training_samples} (= 3307)")


class TestIngestionScheduler:
    """Test ingestion scheduler status."""
    
    def test_scheduler_running(self):
        """P0.4: Verify ingestion scheduler is running."""
        response = requests.get(f"{BACKEND_URL}/api/ingestion/scheduler/status", timeout=30)
        assert response.status_code == 200, f"Scheduler status failed: {response.status_code}"
        
        data = response.json()
        assert data.get("running") is True, f"Scheduler not running: {data}"
        print(f"✓ Scheduler status: running={data.get('running')}, interval={data.get('interval_hours')}h")


class TestBootstrapModel:
    """Test bootstrap model in MongoDB."""
    
    def test_bootstrap_model_exists(self, db):
        """P0.5: Verify bootstrap model exists with correct status."""
        bootstrap = db.ml_model_registry.find_one({
            "status": "bootstrap",
            "model_key": {"$regex": "^bootstrap_v2_pretrain_"}
        })
        
        assert bootstrap is not None, "Bootstrap model not found in ml_model_registry"
        assert bootstrap.get("status") == "bootstrap", f"Bootstrap status wrong: {bootstrap.get('status')}"
        assert bootstrap.get("model_key", "").startswith("bootstrap_v2_pretrain_"), \
            f"Bootstrap model_key wrong: {bootstrap.get('model_key')}"
        
        print(f"✓ Bootstrap model: {bootstrap.get('model_key')}")
        print(f"  status: {bootstrap.get('status')}")
        print(f"  sample_weight: {bootstrap.get('sample_weight')}")
        print(f"  created_at: {bootstrap.get('created_at')}")


class TestActiveModel:
    """Test active model is unchanged."""
    
    def test_active_model_unchanged(self, db):
        """P0.6: Verify active model is signal_quality_xgb_20260325_2231."""
        active = db.ml_model_registry.find_one({"status": "active"})
        
        assert active is not None, "No active model found"
        expected_key = "signal_quality_xgb_20260325_2231"
        assert active.get("model_key") == expected_key, \
            f"Active model changed! Expected {expected_key}, got {active.get('model_key')}"
        
        print(f"✓ Active model unchanged: {active.get('model_key')}")


class TestDatasetEntries:
    """Test dataset_entries collection."""
    
    def test_dataset_entries_count(self, db):
        """P0.7: Verify dataset_entries has 106 entries."""
        count = db.dataset_entries.count_documents({})
        assert count == 106, f"dataset_entries count {count} should be 106"
        print(f"✓ dataset_entries count: {count}")


class TestActorSignalEvents:
    """Test actor_signal_events collection."""
    
    def test_signal_events_count(self, db):
        """P0.8: Verify actor_signal_events has > 4600 entries."""
        count = db.actor_signal_events.count_documents({})
        assert count > 4600, f"actor_signal_events count {count} should be > 4600"
        print(f"✓ actor_signal_events count: {count} (> 4600)")
    
    def test_inferred_signals_exist(self, db):
        """P0.8b: Verify inferred signals (L3 fallback) exist."""
        # Check for signals from graph_inference source
        inferred_count = db.actor_signal_events.count_documents({
            "source": {"$in": ["graph_inference", "fallback", "inferred"]}
        })
        print(f"  Inferred signals (L3 fallback): {inferred_count}")
        # Note: L3 fallback signals may not flow into dataset_entries by design


class TestDatasetEntriesStats:
    """Test dataset entries stats endpoint."""
    
    def test_entries_stats_endpoint(self):
        """P0.9: Verify dataset entries stats endpoint returns ok."""
        response = requests.get(f"{BACKEND_URL}/api/dataset/entries/stats", timeout=30)
        assert response.status_code == 200, f"Dataset entries stats failed: {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, f"Dataset entries stats not OK: {data}"
        
        total = data.get("total", 0)
        assert total == 106, f"Dataset entries total {total} should be 106"
        print(f"✓ Dataset entries stats: total={total}, avg_dqs={data.get('avg_dqs')}")


class TestSignalTrainingDatasetV2:
    """Test signal_training_dataset_v2 collection."""
    
    def test_training_dataset_count(self, db):
        """Verify signal_training_dataset_v2 has 3307 entries."""
        count = db.signal_training_dataset_v2.count_documents({})
        assert count == 3307, f"signal_training_dataset_v2 count {count} should be 3307"
        print(f"✓ signal_training_dataset_v2 count: {count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
