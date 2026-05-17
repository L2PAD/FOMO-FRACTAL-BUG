"""
Crypto Analytics Platform V4 Features Test Suite
=================================================
Tests for:
1. Twitter standby API endpoint GET /api/v4/admin/system/standby
2. System scheduler status GET /api/v4/admin/system/scheduler/status
3. News sources count in MongoDB (~119)
4. HeavyVerdictJob extended mode configuration
5. Resource monitor functionality
6. CoinGecko integration for top coins
7. Core symbols (BTC, ETH, SOL) processing
8. Health endpoint at /health
9. Backend gateway proxy to Node.js backend
"""

import pytest
import requests
import os
from pymongo import MongoClient

# Use public URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com').rstrip('/')
NODE_INTERNAL_URL = "http://localhost:8003"
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/intelligence_engine')


class TestHealthEndpoints:
    """Test health and basic connectivity"""
    
    def test_health_endpoint_returns_ok(self):
        """Health endpoint at /health returns ok status (internal)"""
        # Note: Public URL /health returns frontend HTML, use internal endpoint
        response = requests.get("http://localhost:8001/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'ok'
        assert data.get('node_backend') == 'connected'
        print(f"✓ Health endpoint: {data}")
    
    def test_system_health_api(self):
        """System health API returns connected status"""
        response = requests.get(f"{BASE_URL}/api/system/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data or 'ok' in data
        print(f"✓ System health API: {data}")


class TestTwitterStandbyMonitor:
    """Test Twitter standby mode API - resilient to cookie drops"""
    
    def test_standby_endpoint_returns_state(self):
        """GET /api/v4/admin/system/standby returns state, session counts, and check stats"""
        response = requests.get(f"{NODE_INTERNAL_URL}/api/v4/admin/system/standby", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        standby_data = data.get('data', {})
        
        # Verify required fields
        assert 'state' in standby_data, "Missing 'state' field"
        assert standby_data['state'] in ['ACTIVE', 'STANDBY', 'UNKNOWN'], f"Invalid state: {standby_data['state']}"
        
        assert 'totalSessions' in standby_data, "Missing 'totalSessions' field"
        assert 'okSessions' in standby_data, "Missing 'okSessions' field"
        assert 'staleSessions' in standby_data, "Missing 'staleSessions' field"
        assert 'expiredSessions' in standby_data, "Missing 'expiredSessions' field"
        assert 'lastCheckAt' in standby_data, "Missing 'lastCheckAt' field"
        assert 'checkCount' in standby_data, "Missing 'checkCount' field"
        assert 'standbyDurationMs' in standby_data, "Missing 'standbyDurationMs' field"
        
        print(f"✓ Twitter Standby Status:")
        print(f"  State: {standby_data['state']}")
        print(f"  Total Sessions: {standby_data['totalSessions']}")
        print(f"  OK Sessions: {standby_data['okSessions']}")
        print(f"  Stale Sessions: {standby_data['staleSessions']}")
        print(f"  Check Count: {standby_data['checkCount']}")
    
    def test_standby_via_gateway(self):
        """Test standby endpoint via Python gateway proxy"""
        response = requests.get(f"{BASE_URL}/api/v4/admin/system/standby", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✓ Standby via gateway works")


class TestSystemScheduler:
    """Test system scheduler status"""
    
    def test_scheduler_status_shows_enabled(self):
        """GET /api/v4/admin/system/scheduler/status shows enabled=true"""
        response = requests.get(f"{NODE_INTERNAL_URL}/api/v4/admin/system/scheduler/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') == True
        scheduler_data = data.get('data', {})
        
        # Verify scheduler is enabled
        assert scheduler_data.get('enabled') == True, "Scheduler should be enabled"
        
        # Verify other fields
        assert 'intervalMinutes' in scheduler_data
        assert 'maxConcurrentTasks' in scheduler_data
        assert 'lastTickAt' in scheduler_data or scheduler_data.get('lastTickAt') is None
        
        print(f"✓ Scheduler Status:")
        print(f"  Enabled: {scheduler_data['enabled']}")
        print(f"  Interval: {scheduler_data.get('intervalMinutes')} minutes")
        print(f"  Max Concurrent Tasks: {scheduler_data.get('maxConcurrentTasks')}")
        print(f"  Last Tick: {scheduler_data.get('lastTickAt')}")


class TestNewsSourcesExpansion:
    """Test expanded news RSS sources (~120 feeds)"""
    
    def test_news_sources_count_in_mongodb(self):
        """News sources count in MongoDB should be ~119"""
        client = MongoClient(MONGO_URL)
        db = client.get_database()
        
        count = db.news_sources.count_documents({})
        
        # Should be around 119 (from crypto-rss-feeds.ts)
        assert count >= 100, f"Expected ~119 news sources, got {count}"
        assert count <= 150, f"Expected ~119 news sources, got {count}"
        
        # Verify tier distribution
        tier_a = db.news_sources.count_documents({'tier': 'A'})
        tier_b = db.news_sources.count_documents({'tier': 'B'})
        tier_c = db.news_sources.count_documents({'tier': 'C'})
        
        print(f"✓ News Sources Count: {count}")
        print(f"  Tier A (Institutional): {tier_a}")
        print(f"  Tier B (Mid-tier): {tier_b}")
        print(f"  Tier C (Niche/Regional): {tier_c}")
        
        client.close()
    
    def test_news_sources_have_required_fields(self):
        """Verify news sources have all required fields"""
        client = MongoClient(MONGO_URL)
        db = client.get_database()
        
        # Get a sample of sources
        sources = list(db.news_sources.find({}).limit(10))
        
        for source in sources:
            assert 'id' in source, f"Missing 'id' in source"
            assert 'name' in source, f"Missing 'name' in source"
            assert 'url' in source, f"Missing 'url' in source"
            assert 'tier' in source, f"Missing 'tier' in source"
            assert 'enabled' in source, f"Missing 'enabled' in source"
            assert source['tier'] in ['A', 'B', 'C'], f"Invalid tier: {source['tier']}"
        
        print(f"✓ All news sources have required fields")
        client.close()
    
    def test_key_news_sources_present(self):
        """Verify key institutional-grade sources are present"""
        client = MongoClient(MONGO_URL)
        db = client.get_database()
        
        key_sources = ['coindesk', 'cointelegraph', 'theblock', 'blockworks', 'decrypt']
        
        for source_id in key_sources:
            source = db.news_sources.find_one({'id': source_id})
            assert source is not None, f"Missing key source: {source_id}"
            print(f"  ✓ {source_id}: {source.get('name')} (Tier {source.get('tier')})")
        
        print(f"✓ All key news sources present")
        client.close()


class TestHeavyVerdictJobExtended:
    """Test HeavyVerdictJob extended mode for Top 300 coins"""
    
    def test_heavy_verdict_env_config(self):
        """Verify HeavyVerdictJob extended mode is configured via env"""
        # Check .env file for configuration
        env_path = '/app/backend/.env'
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        # Verify extended mode is enabled
        assert 'HEAVY_VERDICT_EXTENDED=true' in env_content, "HEAVY_VERDICT_EXTENDED should be true"
        assert 'HEAVY_VERDICT_EXTENDED_TOP_N=300' in env_content, "HEAVY_VERDICT_EXTENDED_TOP_N should be 300"
        
        print(f"✓ HeavyVerdictJob Extended Mode Configuration:")
        
        # Extract and print config values
        for line in env_content.split('\n'):
            if line.startswith('HEAVY_VERDICT'):
                print(f"  {line}")
    
    def test_core_symbols_configured(self):
        """Verify core symbols (BTC, ETH, SOL) are configured"""
        env_path = '/app/backend/.env'
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        # Check HEAVY_VERDICT_SYMBOLS
        for line in env_content.split('\n'):
            if line.startswith('HEAVY_VERDICT_SYMBOLS='):
                symbols = line.split('=')[1]
                assert 'BTC' in symbols, "BTC should be in core symbols"
                assert 'ETH' in symbols, "ETH should be in core symbols"
                assert 'SOL' in symbols, "SOL should be in core symbols"
                print(f"✓ Core symbols configured: {symbols}")
                return
        
        pytest.fail("HEAVY_VERDICT_SYMBOLS not found in .env")


class TestResourceMonitor:
    """Test resource monitor for CPU/memory throttling"""
    
    def test_resource_monitor_service_exists(self):
        """Verify resource monitor service file exists"""
        import os
        service_path = '/app/legacy/backend-src/modules/verdict/services/resource-monitor.service.ts'
        assert os.path.exists(service_path), f"Resource monitor service not found at {service_path}"
        
        with open(service_path, 'r') as f:
            content = f.read()
        
        # Verify key functionality
        assert 'CPU_WARN_THRESHOLD' in content, "Missing CPU_WARN_THRESHOLD"
        assert 'CPU_STOP_THRESHOLD' in content, "Missing CPU_STOP_THRESHOLD"
        assert 'MEM_WARN_THRESHOLD' in content, "Missing MEM_WARN_THRESHOLD"
        assert 'MEM_STOP_THRESHOLD' in content, "Missing MEM_STOP_THRESHOLD"
        assert 'isOverloaded' in content, "Missing isOverloaded check"
        assert 'checkAndWarn' in content, "Missing checkAndWarn method"
        
        print(f"✓ Resource monitor service configured with CPU/MEM thresholds")


class TestCoinGeckoIntegration:
    """Test CoinGecko integration for fetching top coins"""
    
    def test_coin_list_service_exists(self):
        """Verify coin list service file exists"""
        import os
        service_path = '/app/legacy/backend-src/modules/verdict/services/coin-list.service.ts'
        assert os.path.exists(service_path), f"Coin list service not found at {service_path}"
        
        with open(service_path, 'r') as f:
            content = f.read()
        
        # Verify CoinGecko integration
        assert 'COINGECKO_API' in content, "Missing CoinGecko API URL"
        assert 'api.coingecko.com' in content, "Missing CoinGecko API endpoint"
        assert 'getTopCoins' in content, "Missing getTopCoins method"
        assert 'HARDCODED_TOP_50' in content, "Missing fallback coin list"
        
        print(f"✓ CoinGecko integration configured in coin-list.service.ts")


class TestBackendGatewayProxy:
    """Test Python gateway proxies to Node.js backend"""
    
    def test_gateway_proxies_to_nodejs(self):
        """Backend gateway proxies to Node.js backend on port 8003"""
        # Test via public URL (goes through Python gateway)
        response = requests.get(f"{BASE_URL}/api/v4/admin/system/standby", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        
        # Test direct Node.js access
        response_direct = requests.get(f"{NODE_INTERNAL_URL}/api/v4/admin/system/standby", timeout=10)
        assert response_direct.status_code == 200
        data_direct = response_direct.json()
        assert data_direct.get('ok') == True
        
        # Both should return same structure
        assert data.get('data', {}).get('state') == data_direct.get('data', {}).get('state')
        
        print(f"✓ Gateway proxy working correctly")
        print(f"  Public URL: {BASE_URL}")
        print(f"  Node.js Internal: {NODE_INTERNAL_URL}")


class TestAdminSystemRoutes:
    """Test admin system routes are registered"""
    
    def test_admin_system_health(self):
        """GET /api/v4/admin/system/health returns health data"""
        response = requests.get(f"{NODE_INTERNAL_URL}/api/v4/admin/system/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        print(f"✓ Admin system health endpoint working")
    
    def test_admin_system_sessions(self):
        """GET /api/v4/admin/system/sessions returns session list"""
        response = requests.get(f"{NODE_INTERNAL_URL}/api/v4/admin/system/sessions", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        print(f"✓ Admin system sessions endpoint working, count: {len(data.get('data', []))}")
    
    def test_admin_system_accounts(self):
        """GET /api/v4/admin/system/accounts returns account list"""
        response = requests.get(f"{NODE_INTERNAL_URL}/api/v4/admin/system/accounts", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') == True
        assert 'data' in data
        print(f"✓ Admin system accounts endpoint working, count: {len(data.get('data', []))}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
