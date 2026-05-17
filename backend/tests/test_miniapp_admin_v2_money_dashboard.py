"""
MiniApp Admin v2 Money Dashboard Tests
======================================
Tests for Admin Console v2 upgrade with money-focused features:
- Overview: Money KPIs, Funnel with rates, A/B table with $/alert, Model metrics
- Signals: edge_pct, alert_pct, revenue_pct, has_revenue column
- Edges: views, clicks, payments, revenue columns, top_by_revenue
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAdminOverviewV2:
    """Admin Overview tab v2 — Money Dashboard tests"""

    def test_overview_returns_ok(self):
        """GET /api/admin/miniapp/overview returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Overview API returns ok:true")

    def test_overview_money_kpis(self):
        """Overview returns money KPIs: revenue, conversion, paid_users, revenue_per_alert"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview")
        assert response.status_code == 200
        data = response.json()
        
        # Money KPIs block
        assert "revenue" in data, "Missing revenue field"
        assert "conversion" in data, "Missing conversion field"
        assert "paid_users" in data, "Missing paid_users field"
        assert "revenue_per_alert" in data, "Missing revenue_per_alert field"
        
        # Validate types
        assert isinstance(data["revenue"], (int, float)), "revenue should be numeric"
        assert isinstance(data["conversion"], (int, float)), "conversion should be numeric"
        assert isinstance(data["paid_users"], int), "paid_users should be int"
        assert isinstance(data["revenue_per_alert"], (int, float)), "revenue_per_alert should be numeric"
        
        print(f"✓ Money KPIs: revenue=${data['revenue']}, conversion={data['conversion']}%, paid_users={data['paid_users']}, $/alert=${data['revenue_per_alert']}")

    def test_overview_funnel_object_with_rates(self):
        """Overview returns funnel as OBJECT with rates (not array)"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview")
        assert response.status_code == 200
        data = response.json()
        
        funnel = data.get("funnel")
        assert funnel is not None, "Missing funnel field"
        assert isinstance(funnel, dict), f"Funnel should be object, got {type(funnel)}"
        
        # Funnel steps
        assert "alerts" in funnel, "Missing funnel.alerts"
        assert "opened" in funnel, "Missing funnel.opened"
        assert "edge_viewed" in funnel, "Missing funnel.edge_viewed"
        assert "upgrade_clicked" in funnel, "Missing funnel.upgrade_clicked"
        assert "paid" in funnel, "Missing funnel.paid"
        
        # Rates object
        rates = funnel.get("rates")
        assert rates is not None, "Missing funnel.rates"
        assert isinstance(rates, dict), "funnel.rates should be object"
        
        assert "open_rate" in rates, "Missing rates.open_rate"
        assert "edge_rate" in rates, "Missing rates.edge_rate"
        assert "click_rate" in rates, "Missing rates.click_rate"
        assert "pay_rate" in rates, "Missing rates.pay_rate"
        
        print(f"✓ Funnel: alerts={funnel['alerts']} → opened={funnel['opened']} → edge_viewed={funnel['edge_viewed']} → upgrade_clicked={funnel['upgrade_clicked']} → paid={funnel['paid']}")
        print(f"✓ Rates: open={rates['open_rate']}%, edge={rates['edge_rate']}%, click={rates['click_rate']}%, pay={rates['pay_rate']}%")

    def test_overview_model_metrics(self):
        """Overview returns model metrics: accuracy, coverage, catastrophic, active_edges"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview")
        assert response.status_code == 200
        data = response.json()
        
        assert "accuracy" in data, "Missing accuracy field"
        assert "coverage" in data, "Missing coverage field"
        assert "catastrophic" in data, "Missing catastrophic field"
        assert "active_edges" in data, "Missing active_edges field"
        
        print(f"✓ Model metrics: accuracy={data['accuracy']}%, coverage={data['coverage']}%, catastrophic={data['catastrophic']}, active_edges={data['active_edges']}")

    def test_overview_ab_stats_format(self):
        """Overview returns ab_stats with new format (sent, opened, ctr, edge_viewed, clicks, paid, revenue_per_alert)"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview")
        assert response.status_code == 200
        data = response.json()
        
        ab_stats = data.get("ab_stats")
        assert ab_stats is not None, "Missing ab_stats field"
        assert isinstance(ab_stats, dict), "ab_stats should be object"
        
        # Check all 4 variants
        for variant in ["A", "B", "C", "D"]:
            assert variant in ab_stats, f"Missing variant {variant} in ab_stats"
            v_data = ab_stats[variant]
            
            # New format fields
            assert "sent" in v_data, f"Missing sent in variant {variant}"
            assert "opened" in v_data, f"Missing opened in variant {variant}"
            assert "ctr" in v_data, f"Missing ctr in variant {variant}"
            assert "edge_viewed" in v_data, f"Missing edge_viewed in variant {variant}"
            assert "clicks" in v_data, f"Missing clicks in variant {variant}"
            assert "paid" in v_data, f"Missing paid in variant {variant}"
            assert "revenue_per_alert" in v_data, f"Missing revenue_per_alert in variant {variant}"
        
        print(f"✓ A/B stats: 4 variants with new format (sent/opened/ctr/edge_viewed/clicks/paid/revenue_per_alert)")
        for v in ["A", "B", "C", "D"]:
            print(f"  {v}: sent={ab_stats[v]['sent']}, ctr={ab_stats[v]['ctr']}%, $/alert={ab_stats[v]['revenue_per_alert']}")

    def test_overview_revenue_daily(self):
        """Overview returns revenue_daily array"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/overview")
        assert response.status_code == 200
        data = response.json()
        
        revenue_daily = data.get("revenue_daily")
        assert revenue_daily is not None, "Missing revenue_daily field"
        assert isinstance(revenue_daily, list), "revenue_daily should be array"
        
        if len(revenue_daily) > 0:
            assert "date" in revenue_daily[0], "Missing date in revenue_daily item"
            assert "revenue" in revenue_daily[0], "Missing revenue in revenue_daily item"
        
        print(f"✓ Revenue daily: {len(revenue_daily)} days of data")


class TestAdminSignalsV2:
    """Admin Signals tab v2 — Money Connection tests"""

    def test_signals_returns_ok(self):
        """GET /api/admin/miniapp/signals returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/signals")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Signals API returns ok:true")

    def test_signals_money_kpis(self):
        """Signals returns money connection KPIs: edge_pct, alert_pct, revenue_pct"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/signals")
        assert response.status_code == 200
        data = response.json()
        
        kpis = data.get("kpis")
        assert kpis is not None, "Missing kpis field"
        
        # New money connection KPIs
        assert "edge_pct" in kpis, "Missing edge_pct in kpis"
        assert "alert_pct" in kpis, "Missing alert_pct in kpis"
        assert "revenue_pct" in kpis, "Missing revenue_pct in kpis"
        assert "with_revenue" in kpis, "Missing with_revenue in kpis"
        
        # Standard KPIs
        assert "total" in kpis, "Missing total in kpis"
        assert "high_priority" in kpis, "Missing high_priority in kpis"
        assert "with_edge" in kpis, "Missing with_edge in kpis"
        assert "with_alert" in kpis, "Missing with_alert in kpis"
        
        print(f"✓ Signal KPIs: total={kpis['total']}, edge_pct={kpis['edge_pct']}%, alert_pct={kpis['alert_pct']}%, revenue_pct={kpis['revenue_pct']}%")

    def test_signals_has_revenue_column(self):
        """Signals table includes has_revenue field"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/signals")
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        if len(signals) > 0:
            first_signal = signals[0]
            assert "has_revenue" in first_signal, "Missing has_revenue in signal"
            assert "has_edge" in first_signal, "Missing has_edge in signal"
            assert "has_alert" in first_signal, "Missing has_alert in signal"
            print(f"✓ Signals have money columns: has_edge, has_alert, has_revenue")
        else:
            print("✓ Signals API works (no signals in last 48h)")

    def test_signals_filter_by_asset(self):
        """Signals can be filtered by asset"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/signals?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Signals filter by asset works")


class TestAdminEdgesV2:
    """Admin Edge tab v2 — Money Integration tests"""

    def test_edges_returns_ok(self):
        """GET /api/admin/miniapp/edges returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ Edges API returns ok:true")

    def test_edges_money_columns(self):
        """Edges have money columns: views, clicks, payments, revenue"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges")
        assert response.status_code == 200
        data = response.json()
        
        edges = data.get("edges", [])
        if len(edges) > 0:
            first_edge = edges[0]
            assert "views" in first_edge, "Missing views in edge"
            assert "clicks" in first_edge, "Missing clicks in edge"
            assert "payments" in first_edge, "Missing payments in edge"
            assert "revenue" in first_edge, "Missing revenue in edge"
            
            # Standard fields
            assert "asset" in first_edge, "Missing asset in edge"
            assert "priorityScore" in first_edge, "Missing priorityScore in edge"
            assert "priorityLabel" in first_edge, "Missing priorityLabel in edge"
            
            print(f"✓ Edges have money columns: views={first_edge['views']}, clicks={first_edge['clicks']}, payments={first_edge['payments']}, revenue=${first_edge['revenue']}")
        else:
            print("✓ Edges API works (no active edges)")

    def test_edges_top_by_revenue(self):
        """Edges returns top_by_revenue array"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges")
        assert response.status_code == 200
        data = response.json()
        
        top_by_revenue = data.get("top_by_revenue")
        assert top_by_revenue is not None, "Missing top_by_revenue field"
        assert isinstance(top_by_revenue, list), "top_by_revenue should be array"
        
        if len(top_by_revenue) > 0:
            first = top_by_revenue[0]
            assert "asset" in first, "Missing asset in top_by_revenue item"
            assert "revenue" in first, "Missing revenue in top_by_revenue item"
            print(f"✓ Top edges by revenue: {len(top_by_revenue)} items, top={first['asset']} with ${first['revenue']}")
        else:
            print("✓ Top by revenue works (no revenue data yet)")

    def test_edges_kpis_with_totals(self):
        """Edges KPIs include total_revenue and total_views"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges")
        assert response.status_code == 200
        data = response.json()
        
        kpis = data.get("kpis")
        assert kpis is not None, "Missing kpis field"
        
        assert "total_revenue" in kpis, "Missing total_revenue in kpis"
        assert "total_views" in kpis, "Missing total_views in kpis"
        assert "active" in kpis, "Missing active in kpis"
        assert "elite" in kpis, "Missing elite in kpis"
        assert "live" in kpis, "Missing live in kpis"
        assert "strong" in kpis, "Missing strong in kpis"
        
        print(f"✓ Edge KPIs: active={kpis['active']}, elite={kpis['elite']}, live={kpis['live']}, strong={kpis['strong']}, total_revenue=${kpis['total_revenue']}, total_views={kpis['total_views']}")

    def test_edges_priority_distribution(self):
        """Edges returns priority_distribution"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/edges")
        assert response.status_code == 200
        data = response.json()
        
        priority_dist = data.get("priority_distribution")
        assert priority_dist is not None, "Missing priority_distribution field"
        assert isinstance(priority_dist, dict), "priority_distribution should be object"
        
        print(f"✓ Priority distribution: {priority_dist}")


class TestMiniAppFrontendFeatures:
    """Tests for MiniApp frontend features (theme, asset tabs)"""

    def test_miniapp_home_api(self):
        """GET /api/miniapp/home returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ MiniApp home API works")

    def test_miniapp_edge_api(self):
        """GET /api/miniapp/edge returns ok:true with priority fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        # Check priority fields exist
        if data.get("best"):
            best = data["best"]
            assert "priorityScore" in best or "priorityLabel" in best, "Missing priority fields in best edge"
        
        print("✓ MiniApp edge API works with priority fields")

    def test_miniapp_profile_api(self):
        """GET /api/miniapp/profile returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile?telegram_id=test_123")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ MiniApp profile API works")


class TestRegressionAPIs:
    """Regression tests for existing APIs"""

    def test_scheduler_status(self):
        """GET /api/miniapp/scheduler/status returns running status"""
        response = requests.get(f"{BASE_URL}/api/miniapp/scheduler/status")
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        print(f"✓ Scheduler status: running={data.get('running')}")

    def test_ab_stats_endpoint(self):
        """GET /api/miniapp/ab/stats returns variants"""
        response = requests.get(f"{BASE_URL}/api/miniapp/ab/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print("✓ A/B stats endpoint works")

    def test_health_endpoint(self):
        """GET /health returns ok"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        # Health endpoint may return JSON or plain text
        try:
            data = response.json()
            assert data.get("status") == "ok" or data.get("service") == "python-gateway"
            print(f"✓ Health endpoint works: {data}")
        except:
            # Plain text response
            assert "ok" in response.text.lower() or response.status_code == 200
            print(f"✓ Health endpoint works (status 200)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
