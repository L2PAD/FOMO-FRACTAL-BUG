"""
MiniApp Admin Console API Tests (Sprint 1)
Tests for:
- GET /api/admin/miniapp/overview - Overview KPIs, funnel, charts, A/B stats
- GET /api/admin/miniapp/signals - Signals with filters
- GET /api/admin/miniapp/edges - Edges with priority data
- Regression: /api/miniapp/edge, /api/miniapp/scheduler/status, /api/miniapp/ab/stats
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMiniAppAdminOverview:
    """Tests for GET /api/admin/miniapp/overview"""
    
    def test_overview_returns_ok(self):
        """Overview endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print("PASS: Overview returns ok:true")
    
    def test_overview_has_user_kpis(self):
        """Overview has users_24h, users_7d, paid_users, conversion"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview", timeout=30)
        data = response.json()
        assert "users_24h" in data, "Missing users_24h"
        assert "users_7d" in data, "Missing users_7d"
        assert "paid_users" in data, "Missing paid_users"
        assert "conversion" in data, "Missing conversion"
        print(f"PASS: User KPIs present - users_24h={data['users_24h']}, users_7d={data['users_7d']}, paid_users={data['paid_users']}, conversion={data['conversion']}%")
    
    def test_overview_has_alert_kpis(self):
        """Overview has alerts_sent, alerts_opened, app_opens, alert_ctr"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview", timeout=30)
        data = response.json()
        assert "alerts_sent" in data, "Missing alerts_sent"
        assert "alerts_opened" in data, "Missing alerts_opened"
        assert "app_opens" in data, "Missing app_opens"
        assert "alert_ctr" in data, "Missing alert_ctr"
        print(f"PASS: Alert KPIs present - sent={data['alerts_sent']}, opened={data['alerts_opened']}, app_opens={data['app_opens']}, ctr={data['alert_ctr']}%")
    
    def test_overview_has_money_kpis(self):
        """Overview has revenue, accuracy, coverage, active_edges"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview", timeout=30)
        data = response.json()
        assert "revenue" in data, "Missing revenue"
        assert "accuracy" in data, "Missing accuracy"
        assert "coverage" in data, "Missing coverage"
        assert "active_edges" in data, "Missing active_edges"
        print(f"PASS: Money/System KPIs present - revenue=${data['revenue']}, accuracy={data['accuracy']}%, coverage={data['coverage']}%, active_edges={data['active_edges']}")
    
    def test_overview_has_funnel(self):
        """Overview has funnel array with label/value pairs"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview", timeout=30)
        data = response.json()
        assert "funnel" in data, "Missing funnel"
        assert isinstance(data["funnel"], list), "funnel should be a list"
        if len(data["funnel"]) > 0:
            assert "label" in data["funnel"][0], "funnel items should have label"
            assert "value" in data["funnel"][0], "funnel items should have value"
        print(f"PASS: Funnel present with {len(data['funnel'])} steps")
    
    def test_overview_has_daily_charts(self):
        """Overview has users_daily and revenue_daily arrays"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview", timeout=30)
        data = response.json()
        assert "users_daily" in data, "Missing users_daily"
        assert "revenue_daily" in data, "Missing revenue_daily"
        assert isinstance(data["users_daily"], list), "users_daily should be a list"
        assert isinstance(data["revenue_daily"], list), "revenue_daily should be a list"
        print(f"PASS: Daily charts present - users_daily={len(data['users_daily'])} days, revenue_daily={len(data['revenue_daily'])} days")
    
    def test_overview_has_ab_stats(self):
        """Overview has ab_stats object"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview", timeout=30)
        data = response.json()
        assert "ab_stats" in data, "Missing ab_stats"
        print(f"PASS: A/B stats present - variants: {list(data['ab_stats'].keys()) if isinstance(data['ab_stats'], dict) else 'N/A'}")


class TestMiniAppAdminSignals:
    """Tests for GET /api/admin/miniapp/signals"""
    
    def test_signals_returns_ok(self):
        """Signals endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/signals", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print("PASS: Signals returns ok:true")
    
    def test_signals_has_kpis(self):
        """Signals has kpis object with total, high_priority, with_edge, with_alert"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/signals", timeout=30)
        data = response.json()
        assert "kpis" in data, "Missing kpis"
        kpis = data["kpis"]
        assert "total" in kpis, "Missing kpis.total"
        assert "high_priority" in kpis, "Missing kpis.high_priority"
        assert "with_edge" in kpis, "Missing kpis.with_edge"
        assert "with_alert" in kpis, "Missing kpis.with_alert"
        print(f"PASS: Signals KPIs present - total={kpis['total']}, high={kpis['high_priority']}, with_edge={kpis['with_edge']}, with_alert={kpis['with_alert']}")
    
    def test_signals_has_signals_array(self):
        """Signals has signals array"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/signals", timeout=30)
        data = response.json()
        assert "signals" in data, "Missing signals"
        assert isinstance(data["signals"], list), "signals should be a list"
        print(f"PASS: Signals array present with {len(data['signals'])} items")
    
    def test_signals_filter_by_asset(self):
        """Signals can be filtered by asset=BTC"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/signals?asset=BTC", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        # All signals should be BTC if any exist
        for s in data.get("signals", []):
            assert s.get("asset") == "BTC", f"Expected BTC, got {s.get('asset')}"
        print(f"PASS: Asset filter works - {len(data.get('signals', []))} BTC signals")


class TestMiniAppAdminEdges:
    """Tests for GET /api/admin/miniapp/edges"""
    
    def test_edges_returns_ok(self):
        """Edges endpoint returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print("PASS: Edges returns ok:true")
    
    def test_edges_has_kpis(self):
        """Edges has kpis with active, elite, live, strong"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges", timeout=30)
        data = response.json()
        assert "kpis" in data, "Missing kpis"
        kpis = data["kpis"]
        assert "active" in kpis, "Missing kpis.active"
        assert "elite" in kpis, "Missing kpis.elite"
        assert "live" in kpis, "Missing kpis.live"
        assert "strong" in kpis, "Missing kpis.strong"
        print(f"PASS: Edge KPIs present - active={kpis['active']}, elite={kpis['elite']}, live={kpis['live']}, strong={kpis['strong']}")
    
    def test_edges_has_edges_array(self):
        """Edges has edges array"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges", timeout=30)
        data = response.json()
        assert "edges" in data, "Missing edges"
        assert isinstance(data["edges"], list), "edges should be a list"
        print(f"PASS: Edges array present with {len(data['edges'])} items")
    
    def test_edges_have_priority_data(self):
        """Each edge has priorityScore and priorityLabel"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges", timeout=30)
        data = response.json()
        edges = data.get("edges", [])
        if len(edges) > 0:
            edge = edges[0]
            assert "priorityScore" in edge, "Missing priorityScore"
            assert "priorityLabel" in edge, "Missing priorityLabel"
            assert isinstance(edge["priorityScore"], (int, float)), "priorityScore should be numeric"
            print(f"PASS: Edge priority data present - first edge: score={edge['priorityScore']}, label={edge['priorityLabel']}")
        else:
            print("PASS: No edges to check (empty array)")
    
    def test_edges_has_priority_distribution(self):
        """Edges has priority_distribution object"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges", timeout=30)
        data = response.json()
        assert "priority_distribution" in data, "Missing priority_distribution"
        assert isinstance(data["priority_distribution"], dict), "priority_distribution should be a dict"
        print(f"PASS: Priority distribution present - {data['priority_distribution']}")


class TestMiniAppRegressionAPIs:
    """Regression tests for existing MiniApp APIs"""
    
    def test_edge_api_still_works(self):
        """GET /api/miniapp/edge still returns edges with priorityScore"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        markets = data.get("markets", [])
        if len(markets) > 0:
            assert "priorityScore" in markets[0], "Missing priorityScore in edge"
        print(f"PASS: /api/miniapp/edge works - {len(markets)} markets")
    
    def test_scheduler_status_still_works(self):
        """GET /api/miniapp/scheduler/status still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/scheduler/status", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "running" in data, "Missing running field"
        print(f"PASS: /api/miniapp/scheduler/status works - running={data.get('running')}")
    
    def test_ab_stats_still_works(self):
        """GET /api/miniapp/ab/stats still works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/ab/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        print(f"PASS: /api/miniapp/ab/stats works - variants: {list(data.get('stats', {}).keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
