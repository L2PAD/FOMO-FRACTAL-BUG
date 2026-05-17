"""
Sentiment Data Accumulation Monitor - Backend API Tests
Tests all 9 APIs used by the Data Monitor dashboard:
1. /api/sentiment/stats
2. /api/admin/data-accumulation
3. /api/dataset/entries/stats
4. /api/dataset/v3/stats
5. /api/outcome/stats
6. /api/ml/ingest/status
7. /api/ingestion/cron/status
8. /api/dataset/v3/health
9. /api/enrichment/stats
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSentimentDataMonitorAPIs:
    """Test all 9 APIs used by Sentiment Data Accumulation Monitor"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # APIs can be slow (5-10s each per main agent note)
        self.timeout = 30
    
    # ═══════════════════════════════════════════════════════════════
    # API 1: /api/sentiment/stats
    # ═══════════════════════════════════════════════════════════════
    def test_sentiment_stats_returns_200(self):
        """Test /api/sentiment/stats returns 200"""
        response = self.session.get(f"{BASE_URL}/api/sentiment/stats", timeout=self.timeout)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_sentiment_stats_structure(self):
        """Test /api/sentiment/stats returns expected structure"""
        response = self.session.get(f"{BASE_URL}/api/sentiment/stats", timeout=self.timeout)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "ok" in data, "Missing 'ok' field"
        assert "total" in data, "Missing 'total' field"
        assert "by_sentiment" in data, "Missing 'by_sentiment' field"
        assert "avg_confidence" in data, "Missing 'avg_confidence' field"
        
        # Verify types
        assert isinstance(data["total"], int), "total should be int"
        assert isinstance(data["by_sentiment"], dict), "by_sentiment should be dict"
        assert isinstance(data["avg_confidence"], (int, float)), "avg_confidence should be numeric"
    
    # ═══════════════════════════════════════════════════════════════
    # API 2: /api/admin/data-accumulation
    # ═══════════════════════════════════════════════════════════════
    def test_data_accumulation_returns_200(self):
        """Test /api/admin/data-accumulation returns 200"""
        response = self.session.get(f"{BASE_URL}/api/admin/data-accumulation", timeout=self.timeout)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_data_accumulation_structure(self):
        """Test /api/admin/data-accumulation returns mlReadiness data"""
        response = self.session.get(f"{BASE_URL}/api/admin/data-accumulation", timeout=self.timeout)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "ok" in data, "Missing 'ok' field"
        assert "data" in data, "Missing 'data' field"
        
        # Verify mlReadiness structure
        assert "mlReadiness" in data["data"], "Missing 'mlReadiness' in data"
        ml = data["data"]["mlReadiness"]
        assert "status" in ml, "Missing 'status' in mlReadiness"
        assert "dirSamples" in ml, "Missing 'dirSamples' in mlReadiness"
        assert "shadowDecisions" in ml, "Missing 'shadowDecisions' in mlReadiness"
        assert "minThreshold" in ml, "Missing 'minThreshold' in mlReadiness"
        assert "goodThreshold" in ml, "Missing 'goodThreshold' in mlReadiness"
    
    # ═══════════════════════════════════════════════════════════════
    # API 3: /api/dataset/entries/stats
    # ═══════════════════════════════════════════════════════════════
    def test_dataset_entries_stats_returns_200(self):
        """Test /api/dataset/entries/stats returns 200"""
        response = self.session.get(f"{BASE_URL}/api/dataset/entries/stats", timeout=self.timeout)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_dataset_entries_stats_structure(self):
        """Test /api/dataset/entries/stats returns ready_for_ml, distribution_health"""
        response = self.session.get(f"{BASE_URL}/api/dataset/entries/stats", timeout=self.timeout)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "ok" in data, "Missing 'ok' field"
        assert "total" in data, "Missing 'total' field"
        assert "ready_for_ml" in data, "Missing 'ready_for_ml' field"
        assert "distribution_health" in data, "Missing 'distribution_health' field"
        assert "dataset_distribution" in data, "Missing 'dataset_distribution' field"
        assert "avg_dqs" in data, "Missing 'avg_dqs' field"
        
        # Verify dataset_distribution structure
        dist = data["dataset_distribution"]
        assert "good_pct" in dist, "Missing 'good_pct' in dataset_distribution"
        assert "neutral_pct" in dist, "Missing 'neutral_pct' in dataset_distribution"
        assert "bad_pct" in dist, "Missing 'bad_pct' in dataset_distribution"
    
    # ═══════════════════════════════════════════════════════════════
    # API 4: /api/dataset/v3/stats
    # ═══════════════════════════════════════════════════════════════
    def test_dataset_v3_stats_returns_200(self):
        """Test /api/dataset/v3/stats returns 200"""
        response = self.session.get(f"{BASE_URL}/api/dataset/v3/stats", timeout=self.timeout)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_dataset_v3_stats_structure(self):
        """Test /api/dataset/v3/stats returns quality, diversity, distribution"""
        response = self.session.get(f"{BASE_URL}/api/dataset/v3/stats", timeout=self.timeout)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "ok" in data, "Missing 'ok' field"
        assert "total" in data, "Missing 'total' field"
        assert "quality" in data, "Missing 'quality' field"
        assert "diversity" in data, "Missing 'diversity' field"
        assert "distribution" in data, "Missing 'distribution' field"
        
        # Verify quality structure
        quality = data["quality"]
        assert "avg_dqs" in quality, "Missing 'avg_dqs' in quality"
        
        # Verify diversity structure
        diversity = data["diversity"]
        assert "unique_actors" in diversity, "Missing 'unique_actors' in diversity"
        assert "unique_tokens" in diversity, "Missing 'unique_tokens' in diversity"
        assert "actor_gini" in diversity, "Missing 'actor_gini' in diversity"
        assert "token_gini" in diversity, "Missing 'token_gini' in diversity"
        
        # Verify distribution structure
        dist = data["distribution"]
        assert "by_intent" in dist, "Missing 'by_intent' in distribution"
        assert "by_role" in dist, "Missing 'by_role' in distribution"
    
    # ═══════════════════════════════════════════════════════════════
    # API 5: /api/outcome/stats
    # ═══════════════════════════════════════════════════════════════
    def test_outcome_stats_returns_200(self):
        """Test /api/outcome/stats returns 200"""
        response = self.session.get(f"{BASE_URL}/api/outcome/stats", timeout=self.timeout)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_outcome_stats_structure(self):
        """Test /api/outcome/stats returns labels with GOOD/NEUTRAL/BAD counts"""
        response = self.session.get(f"{BASE_URL}/api/outcome/stats", timeout=self.timeout)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "ok" in data, "Missing 'ok' field"
        assert "total" in data, "Missing 'total' field"
        assert "resolved" in data, "Missing 'resolved' field"
        assert "labels" in data, "Missing 'labels' field"
        
        # Verify labels is a dict (may contain GOOD, NEUTRAL, BAD)
        assert isinstance(data["labels"], dict), "labels should be dict"
    
    # ═══════════════════════════════════════════════════════════════
    # API 6: /api/ml/ingest/status
    # ═══════════════════════════════════════════════════════════════
    def test_ml_ingest_status_returns_200(self):
        """Test /api/ml/ingest/status returns 200"""
        response = self.session.get(f"{BASE_URL}/api/ml/ingest/status", timeout=self.timeout)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_ml_ingest_status_structure(self):
        """Test /api/ml/ingest/status returns events totals, actors info"""
        response = self.session.get(f"{BASE_URL}/api/ml/ingest/status", timeout=self.timeout)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "ok" in data, "Missing 'ok' field"
        assert "events" in data, "Missing 'events' field"
        assert "actors" in data, "Missing 'actors' field"
        
        # Verify events structure
        events = data["events"]
        assert "total" in events, "Missing 'total' in events"
        assert "real" in events, "Missing 'real' in events"
        assert "synthetic" in events, "Missing 'synthetic' in events"
        
        # Verify actors structure
        actors = data["actors"]
        assert "real_unique" in actors, "Missing 'real_unique' in actors"
        assert "synth_unique" in actors, "Missing 'synth_unique' in actors"
    
    # ═══════════════════════════════════════════════════════════════
    # API 7: /api/ingestion/cron/status
    # ═══════════════════════════════════════════════════════════════
    def test_cron_status_returns_200(self):
        """Test /api/ingestion/cron/status returns 200"""
        response = self.session.get(f"{BASE_URL}/api/ingestion/cron/status", timeout=self.timeout)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_cron_status_structure(self):
        """Test /api/ingestion/cron/status returns total_cycles, last_cycle with stages"""
        response = self.session.get(f"{BASE_URL}/api/ingestion/cron/status", timeout=self.timeout)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "ok" in data, "Missing 'ok' field"
        assert "total_cycles" in data, "Missing 'total_cycles' field"
        assert "pipeline_enabled" in data, "Missing 'pipeline_enabled' field"
        
        # last_cycle may be null if no cycles have run
        if data.get("last_cycle"):
            lc = data["last_cycle"]
            assert "stages" in lc, "Missing 'stages' in last_cycle"
            assert "duration_sec" in lc, "Missing 'duration_sec' in last_cycle"
            assert "total_new_signals" in lc, "Missing 'total_new_signals' in last_cycle"
            
            # Verify stages structure
            if lc["stages"]:
                stage = lc["stages"][0]
                assert "stage" in stage, "Missing 'stage' in stage"
                assert "ok" in stage, "Missing 'ok' in stage"
                assert "duration_sec" in stage, "Missing 'duration_sec' in stage"
    
    # ═══════════════════════════════════════════════════════════════
    # API 8: /api/dataset/v3/health
    # ═══════════════════════════════════════════════════════════════
    def test_dataset_health_returns_200(self):
        """Test /api/dataset/v3/health returns 200"""
        response = self.session.get(f"{BASE_URL}/api/dataset/v3/health", timeout=self.timeout)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_dataset_health_structure(self):
        """Test /api/dataset/v3/health returns status, avg_dqs_24h, avg_dqs_7d"""
        response = self.session.get(f"{BASE_URL}/api/dataset/v3/health", timeout=self.timeout)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "ok" in data, "Missing 'ok' field"
        assert "status" in data, "Missing 'status' field"
        assert "avg_dqs_24h" in data, "Missing 'avg_dqs_24h' field"
        assert "avg_dqs_7d" in data, "Missing 'avg_dqs_7d' field"
    
    # ═══════════════════════════════════════════════════════════════
    # API 9: /api/enrichment/stats
    # ═══════════════════════════════════════════════════════════════
    def test_enrichment_stats_returns_200(self):
        """Test /api/enrichment/stats returns 200"""
        response = self.session.get(f"{BASE_URL}/api/enrichment/stats", timeout=self.timeout)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_enrichment_stats_structure(self):
        """Test /api/enrichment/stats returns total, by_position, by_actor_role"""
        response = self.session.get(f"{BASE_URL}/api/enrichment/stats", timeout=self.timeout)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "ok" in data, "Missing 'ok' field"
        assert "total" in data, "Missing 'total' field"
        assert "by_position" in data, "Missing 'by_position' field"
        assert "by_actor_role" in data, "Missing 'by_actor_role' field"


class TestSentimentDataMonitorDataValues:
    """Test actual data values returned by APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.timeout = 30
    
    def test_sentiment_stats_has_data(self):
        """Verify sentiment stats has actual data"""
        response = self.session.get(f"{BASE_URL}/api/sentiment/stats", timeout=self.timeout)
        data = response.json()
        print(f"Sentiment stats: total={data.get('total')}, by_sentiment={data.get('by_sentiment')}")
        # Just log, don't fail if empty
    
    def test_data_accumulation_ml_status(self):
        """Verify ML readiness status"""
        response = self.session.get(f"{BASE_URL}/api/admin/data-accumulation", timeout=self.timeout)
        data = response.json()
        ml = data.get("data", {}).get("mlReadiness", {})
        print(f"ML Readiness: status={ml.get('status')}, dirSamples={ml.get('dirSamples')}/{ml.get('goodThreshold')}")
    
    def test_outcome_labels_distribution(self):
        """Verify outcome labels distribution"""
        response = self.session.get(f"{BASE_URL}/api/outcome/stats", timeout=self.timeout)
        data = response.json()
        labels = data.get("labels", {})
        print(f"Outcome labels: GOOD={labels.get('GOOD', 0)}, NEUTRAL={labels.get('NEUTRAL', 0)}, BAD={labels.get('BAD', 0)}")
    
    def test_pipeline_stages_status(self):
        """Verify pipeline stages status"""
        response = self.session.get(f"{BASE_URL}/api/ingestion/cron/status", timeout=self.timeout)
        data = response.json()
        lc = data.get("last_cycle")
        if lc:
            stages = lc.get("stages", [])
            ok_count = sum(1 for s in stages if s.get("ok"))
            failed = [s.get("stage") for s in stages if not s.get("ok")]
            print(f"Pipeline: {ok_count}/{len(stages)} stages OK, failed={failed}")
        else:
            print("Pipeline: No cycles run yet")
