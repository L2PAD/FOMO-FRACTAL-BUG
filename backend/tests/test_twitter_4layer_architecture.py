"""
Twitter 4-Layer Ingestion Architecture Tests
=============================================
Tests for the complete rebuild from 3-layer to 4-layer:
L0 = public syndication scrape (primary, no cookies)
L1 = cookies (secondary, auto-rotate)
L2 = Playwright persistent context (recovery)
L3 = inference (backup)
"""
import pytest
import requests
import subprocess
from pymongo import MongoClient

BASE_URL = "http://localhost:8001"
PARSER_URL = "http://localhost:5001"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "intelligence_engine"


class TestTwitterHealthEndpoint:
    """Tests for GET /api/twitter/health endpoint"""

    def test_twitter_health_returns_ok(self):
        """Health endpoint should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/twitter/health", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Twitter health: ok={data.get('ok')}")

    def test_twitter_health_has_status_field(self):
        """Health endpoint should have status field (OK/DEGRADED/DEAD)"""
        response = requests.get(f"{BASE_URL}/api/twitter/health", timeout=30)
        data = response.json()
        assert "status" in data
        assert data["status"] in ["OK", "DEGRADED", "DEAD"]
        print(f"Twitter health status: {data['status']}")

    def test_twitter_health_has_tweets_1h(self):
        """Health endpoint should have tweets_1h count"""
        response = requests.get(f"{BASE_URL}/api/twitter/health", timeout=30)
        data = response.json()
        assert "tweets_1h" in data
        assert isinstance(data["tweets_1h"], int)
        print(f"Tweets in last 1h: {data['tweets_1h']}")

    def test_twitter_health_has_sources_6h_breakdown(self):
        """Health endpoint should have sources_6h with L0/L1/L2/L3 breakdown"""
        response = requests.get(f"{BASE_URL}/api/twitter/health", timeout=30)
        data = response.json()
        assert "sources_6h" in data
        sources = data["sources_6h"]
        assert "L0_public" in sources
        assert "L1_cookies" in sources
        assert "L2_playwright" in sources
        assert "L3_inference" in sources
        print(f"Sources 6h: L0={sources['L0_public']}, L1={sources['L1_cookies']}, L2={sources['L2_playwright']}, L3={sources['L3_inference']}")

    def test_twitter_health_has_sessions_info(self):
        """Health endpoint should have sessions info"""
        response = requests.get(f"{BASE_URL}/api/twitter/health", timeout=30)
        data = response.json()
        assert "sessions" in data
        sessions = data["sessions"]
        assert "active" in sessions
        assert "stale" in sessions
        assert "total" in sessions
        print(f"Sessions: active={sessions['active']}, stale={sessions['stale']}, total={sessions['total']}")

    def test_twitter_health_has_parser_alive(self):
        """Health endpoint should have parser_alive field"""
        response = requests.get(f"{BASE_URL}/api/twitter/health", timeout=30)
        data = response.json()
        assert "parser_alive" in data
        assert isinstance(data["parser_alive"], bool)
        print(f"Parser alive: {data['parser_alive']}")


class TestTwitterParserSupervisor:
    """Tests for twitter-parser-v2 supervisor process"""

    def test_twitter_parser_running_in_supervisor(self):
        """twitter-parser should be RUNNING under supervisor"""
        result = subprocess.run(
            ["sudo", "supervisorctl", "status", "twitter-parser"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "RUNNING" in result.stdout
        print(f"Supervisor status: {result.stdout.strip()}")

    def test_twitter_parser_health_endpoint(self):
        """twitter-parser-v2 /health should return ok=true"""
        response = requests.get(f"{PARSER_URL}/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"Parser health: {data}")


class TestBackendHealth:
    """Tests for backend health"""

    def test_backend_health_ok(self):
        """Backend /health should return ok"""
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print(f"Backend health: {data}")


class Test4LayerArchitectureFiles:
    """Tests for 4-layer architecture file existence"""

    def test_public_scraper_exists(self):
        """L0 public_scraper.py should exist"""
        import os
        path = "/app/backend/twitter_ingestion/public_scraper.py"
        assert os.path.exists(path)
        print(f"L0 file exists: {path}")

    def test_cookie_client_exists(self):
        """L1 cookie_client.py should exist"""
        import os
        path = "/app/backend/twitter_ingestion/cookie_client.py"
        assert os.path.exists(path)
        print(f"L1 file exists: {path}")

    def test_playwright_client_exists(self):
        """L2 playwright_client.py should exist"""
        import os
        path = "/app/backend/twitter_ingestion/playwright_client.py"
        assert os.path.exists(path)
        print(f"L2 file exists: {path}")

    def test_hybrid_service_exists(self):
        """Unified hybrid_service.py should exist"""
        import os
        path = "/app/backend/twitter_ingestion/hybrid_service.py"
        assert os.path.exists(path)
        print(f"Hybrid service file exists: {path}")

    def test_watchdog_exists(self):
        """Active recovery watchdog.py should exist"""
        import os
        path = "/app/backend/twitter_ingestion/watchdog.py"
        assert os.path.exists(path)
        print(f"Watchdog file exists: {path}")


class TestMLSourceFilter:
    """Tests for ML source filter in enrichment_layer.py"""

    def test_allowed_ml_sources_includes_public_scrape(self):
        """ALLOWED_ML_SOURCES should include public_scrape"""
        with open("/app/backend/enrichment_layer.py", "r") as f:
            content = f.read()
        assert "public_scrape" in content
        assert "ALLOWED_ML_SOURCES" in content
        print("public_scrape found in ALLOWED_ML_SOURCES")

    def test_allowed_ml_sources_includes_playwright_scrape(self):
        """ALLOWED_ML_SOURCES should include playwright_scrape"""
        with open("/app/backend/enrichment_layer.py", "r") as f:
            content = f.read()
        assert "playwright_scrape" in content
        print("playwright_scrape found in ALLOWED_ML_SOURCES")


class TestDatabaseSourceData:
    """Tests for data presence in actor_signal_events by source"""

    @pytest.fixture(scope="class")
    def db(self):
        client = MongoClient(MONGO_URL)
        return client[DB_NAME]

    def test_l0_public_scrape_data_present(self, db):
        """actor_signal_events should have records with source=public_scrape (L0)"""
        count = db.actor_signal_events.count_documents({"source": "public_scrape"})
        assert count > 0, "No L0 (public_scrape) data found"
        print(f"L0 (public_scrape) records: {count}")

    def test_l1_twitter_kol_data_present(self, db):
        """actor_signal_events should have records with source=twitter_kol (L1)"""
        count = db.actor_signal_events.count_documents({"source": "twitter_kol"})
        assert count > 0, "No L1 (twitter_kol) data found"
        print(f"L1 (twitter_kol) records: {count}")

    def test_l2_playwright_scrape_data_present(self, db):
        """actor_signal_events should have records with source=playwright_scrape (L2)"""
        count = db.actor_signal_events.count_documents({"source": "playwright_scrape"})
        assert count > 0, "No L2 (playwright_scrape) data found"
        print(f"L2 (playwright_scrape) records: {count}")

    def test_l3_graph_inference_data_present(self, db):
        """actor_signal_events should have records with source=graph_inference (L3)"""
        count = db.actor_signal_events.count_documents({"source": "graph_inference"})
        assert count > 0, "No L3 (graph_inference) data found"
        print(f"L3 (graph_inference) records: {count}")


class TestLegacyImports:
    """Tests for legacy module re-exports"""

    def test_check_parser_health_import(self):
        """check_parser_health should be importable from twitter_ingestion"""
        import sys
        sys.path.insert(0, "/app/backend")
        from twitter_ingestion import check_parser_health
        assert callable(check_parser_health)
        print("check_parser_health import OK")

    def test_ingest_actor_tweets_import(self):
        """ingest_actor_tweets should be importable from twitter_ingestion"""
        import sys
        sys.path.insert(0, "/app/backend")
        from twitter_ingestion import ingest_actor_tweets
        assert callable(ingest_actor_tweets)
        print("ingest_actor_tweets import OK")

    def test_mass_ingest_actors_import(self):
        """mass_ingest_actors should be importable from twitter_ingestion"""
        import sys
        sys.path.insert(0, "/app/backend")
        from twitter_ingestion import mass_ingest_actors
        assert callable(mass_ingest_actors)
        print("mass_ingest_actors import OK")

    def test_get_ingestion_status_import(self):
        """get_ingestion_status should be importable from twitter_ingestion"""
        import sys
        sys.path.insert(0, "/app/backend")
        from twitter_ingestion import get_ingestion_status
        assert callable(get_ingestion_status)
        print("get_ingestion_status import OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
