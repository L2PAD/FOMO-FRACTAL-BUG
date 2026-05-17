"""
MiniApp Admin Sprint 2 Tests — Users, Billing, Alerts, Settings tabs
=====================================================================
Tests 4 new backend endpoints:
- GET /api/admin/miniapp/users (with filters: status, variant, active_only, has_revenue, sort_by, sort_dir)
- GET /api/admin/miniapp/billing (KPIs by source, transactions, daily chart)
- GET /api/admin/miniapp/alerts (KPIs, A/B stats, CTR over time, recent alerts)
- GET /api/admin/miniapp/settings (read default settings)
- PUT /api/admin/miniapp/settings (save settings to MongoDB)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestMiniAppAdminUsers:
    """Users tab — who brings money?"""

    def test_users_endpoint_returns_ok(self):
        """GET /api/admin/miniapp/users returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/users")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Users endpoint returns ok:true")

    def test_users_has_kpis(self):
        """Users endpoint returns KPIs: total, active_24h, paid, conversion, linked_pct, tg_only_pct"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/users")
        assert response.status_code == 200
        data = response.json()
        kpis = data.get("kpis", {})
        required_kpis = ["total", "active_24h", "paid", "conversion", "linked_pct", "tg_only_pct"]
        for kpi in required_kpis:
            assert kpi in kpis, f"Missing KPI: {kpi}"
        print(f"PASS: Users KPIs present: {list(kpis.keys())}")

    def test_users_has_users_list(self):
        """Users endpoint returns users array with funnel stats"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/users")
        assert response.status_code == 200
        data = response.json()
        users = data.get("users", [])
        assert isinstance(users, list)
        print(f"PASS: Users list returned with {len(users)} users")

    def test_users_filter_by_status_telegram(self):
        """Filter users by status=telegram"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/users?status=telegram")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        users = data.get("users", [])
        for u in users:
            assert u.get("status") == "telegram", f"User {u.get('user')} has status {u.get('status')}"
        print(f"PASS: Filter by status=telegram works, {len(users)} users")

    def test_users_filter_by_variant_a(self):
        """Filter users by variant=A"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/users?variant=A")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        users = data.get("users", [])
        for u in users:
            assert u.get("variant") == "A", f"User {u.get('user')} has variant {u.get('variant')}"
        print(f"PASS: Filter by variant=A works, {len(users)} users")

    def test_users_filter_by_variant_b(self):
        """Filter users by variant=B"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/users?variant=B")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        users = data.get("users", [])
        for u in users:
            assert u.get("variant") == "B", f"User {u.get('user')} has variant {u.get('variant')}"
        print(f"PASS: Filter by variant=B works, {len(users)} users")

    def test_users_sort_by_revenue(self):
        """Sort users by revenue descending"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/users?sort_by=revenue&sort_dir=desc")
        assert response.status_code == 200
        data = response.json()
        users = data.get("users", [])
        if len(users) >= 2:
            for i in range(len(users) - 1):
                assert users[i].get("revenue", 0) >= users[i + 1].get("revenue", 0)
        print(f"PASS: Sort by revenue desc works")

    def test_users_sort_by_clicks(self):
        """Sort users by clicks descending"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/users?sort_by=clicks&sort_dir=desc")
        assert response.status_code == 200
        data = response.json()
        users = data.get("users", [])
        if len(users) >= 2:
            for i in range(len(users) - 1):
                assert users[i].get("clicks", 0) >= users[i + 1].get("clicks", 0)
        print(f"PASS: Sort by clicks desc works")

    def test_users_user_has_funnel_stats(self):
        """Each user has funnel stats: alerts_received, alerts_opened, edge_views, clicks, payments, revenue"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/users")
        assert response.status_code == 200
        data = response.json()
        users = data.get("users", [])
        if users:
            u = users[0]
            required_fields = ["alerts_received", "alerts_opened", "edge_views", "clicks", "payments", "revenue"]
            for field in required_fields:
                assert field in u, f"Missing field: {field}"
            print(f"PASS: User has funnel stats: {required_fields}")
        else:
            print(f"SKIP: No users to verify funnel stats")


class TestMiniAppAdminBilling:
    """Billing tab — where does money come from?"""

    def test_billing_endpoint_returns_ok(self):
        """GET /api/admin/miniapp/billing returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/billing")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Billing endpoint returns ok:true")

    def test_billing_has_kpis(self):
        """Billing endpoint returns KPIs: revenue_miniapp, revenue_web, revenue_direct, miniapp_pct, conversion, avg_check"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/billing")
        assert response.status_code == 200
        data = response.json()
        kpis = data.get("kpis", {})
        required_kpis = ["revenue_miniapp", "revenue_web", "revenue_direct", "miniapp_pct", "conversion", "avg_check"]
        for kpi in required_kpis:
            assert kpi in kpis, f"Missing KPI: {kpi}"
        print(f"PASS: Billing KPIs present: {list(kpis.keys())}")

    def test_billing_has_transactions(self):
        """Billing endpoint returns transactions array"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/billing")
        assert response.status_code == 200
        data = response.json()
        transactions = data.get("transactions", [])
        assert isinstance(transactions, list)
        print(f"PASS: Transactions list returned with {len(transactions)} items")

    def test_billing_has_daily_chart_data(self):
        """Billing endpoint returns daily array for stacked bar chart"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/billing")
        assert response.status_code == 200
        data = response.json()
        daily = data.get("daily", [])
        assert isinstance(daily, list)
        assert len(daily) == 7, f"Expected 7 days, got {len(daily)}"
        if daily:
            d = daily[0]
            assert "date" in d
            assert "miniapp" in d
            assert "web" in d
            assert "direct" in d
        print(f"PASS: Daily chart data has 7 days with miniapp/web/direct breakdown")


class TestMiniAppAdminAlerts:
    """Alerts tab — what sells?"""

    def test_alerts_endpoint_returns_ok(self):
        """GET /api/admin/miniapp/alerts returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/alerts")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Alerts endpoint returns ok:true")

    def test_alerts_has_kpis(self):
        """Alerts endpoint returns 7 KPIs including $/alert"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/alerts")
        assert response.status_code == 200
        data = response.json()
        kpis = data.get("kpis", {})
        required_kpis = ["alerts_sent", "alerts_opened", "ctr", "edge_views", "clicks", "payments", "revenue_per_alert"]
        for kpi in required_kpis:
            assert kpi in kpis, f"Missing KPI: {kpi}"
        print(f"PASS: Alerts KPIs present: {list(kpis.keys())}")

    def test_alerts_has_ab_stats(self):
        """Alerts endpoint returns ab_stats with 4 variants"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/alerts")
        assert response.status_code == 200
        data = response.json()
        ab_stats = data.get("ab_stats", {})
        assert isinstance(ab_stats, dict)
        # Should have A, B, C, D variants
        for v in ["A", "B", "C", "D"]:
            assert v in ab_stats, f"Missing variant: {v}"
            variant_data = ab_stats[v]
            assert "sent" in variant_data
            assert "opened" in variant_data
            assert "ctr" in variant_data
            assert "revenue_per_alert" in variant_data
        print(f"PASS: A/B stats has 4 variants with $/alert")

    def test_alerts_has_ctr_over_time(self):
        """Alerts endpoint returns ctr_over_time with 7 days and 4 variant lines"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/alerts")
        assert response.status_code == 200
        data = response.json()
        ctr_over_time = data.get("ctr_over_time", [])
        assert isinstance(ctr_over_time, list)
        assert len(ctr_over_time) == 7, f"Expected 7 days, got {len(ctr_over_time)}"
        if ctr_over_time:
            d = ctr_over_time[0]
            assert "date" in d
            for v in ["A", "B", "C", "D"]:
                assert v in d, f"Missing variant {v} in CTR over time"
        print(f"PASS: CTR over time has 7 days with 4 variant lines")

    def test_alerts_has_recent_alerts(self):
        """Alerts endpoint returns recent_alerts with opened/clicked/paid booleans"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/alerts")
        assert response.status_code == 200
        data = response.json()
        recent_alerts = data.get("recent_alerts", [])
        assert isinstance(recent_alerts, list)
        if recent_alerts:
            a = recent_alerts[0]
            assert "time" in a
            assert "user" in a
            assert "variant" in a
            assert "asset" in a
            assert "opened" in a
            assert "clicked" in a
            assert "paid" in a
            assert isinstance(a["opened"], bool)
            assert isinstance(a["clicked"], bool)
            assert isinstance(a["paid"], bool)
        print(f"PASS: Recent alerts has {len(recent_alerts)} items with opened/clicked/paid booleans")


class TestMiniAppAdminSettings:
    """Settings tab — what to control?"""

    def test_settings_get_returns_ok(self):
        """GET /api/admin/miniapp/settings returns ok:true"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/settings")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        print(f"PASS: Settings GET returns ok:true")

    def test_settings_has_default_structure(self):
        """Settings returns default structure with alerts/scheduler/monetization sections"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/settings")
        assert response.status_code == 200
        data = response.json()
        settings = data.get("settings", {})
        
        # Alerts section
        alerts = settings.get("alerts", {})
        assert "edge_threshold" in alerts
        assert "priority_threshold" in alerts
        assert "daily_limit" in alerts
        assert "extreme_bypass" in alerts
        
        # Scheduler section
        scheduler = settings.get("scheduler", {})
        assert "ingest_interval" in scheduler
        assert "digest_hour" in scheduler
        assert "digest_enabled" in scheduler
        
        # Monetization section
        monetization = settings.get("monetization", {})
        assert "free_edge_limit" in monetization
        assert "paywall_enabled" in monetization
        assert "teaser_mode" in monetization
        
        print(f"PASS: Settings has alerts/scheduler/monetization sections with all fields")

    def test_settings_default_values(self):
        """Settings returns correct default values"""
        response = requests.get(f"{BASE_URL}/api/admin/miniapp/settings")
        assert response.status_code == 200
        data = response.json()
        settings = data.get("settings", {})
        
        # Check default values
        alerts = settings.get("alerts", {})
        assert alerts.get("edge_threshold") == 0.10
        assert alerts.get("priority_threshold") == 0.68
        assert alerts.get("daily_limit") == 5
        assert alerts.get("extreme_bypass") is True
        
        scheduler = settings.get("scheduler", {})
        assert scheduler.get("ingest_interval") == 30
        assert scheduler.get("digest_hour") == 9
        assert scheduler.get("digest_enabled") is True
        
        monetization = settings.get("monetization", {})
        assert monetization.get("free_edge_limit") == 3
        assert monetization.get("paywall_enabled") is True
        assert monetization.get("teaser_mode") is True
        
        print(f"PASS: Settings default values are correct")

    def test_settings_put_saves_to_mongodb(self):
        """PUT /api/admin/miniapp/settings saves settings and returns updated"""
        # First get current settings
        get_response = requests.get(f"{BASE_URL}/api/admin/miniapp/settings")
        assert get_response.status_code == 200
        original_settings = get_response.json().get("settings", {})
        
        # Modify a value
        new_settings = original_settings.copy()
        new_settings["alerts"] = new_settings.get("alerts", {}).copy()
        new_settings["alerts"]["daily_limit"] = 10
        
        # PUT the new settings
        put_response = requests.put(
            f"{BASE_URL}/api/admin/miniapp/settings",
            json={"settings": new_settings},
            headers={"Content-Type": "application/json"}
        )
        assert put_response.status_code == 200
        put_data = put_response.json()
        assert put_data.get("ok") is True
        
        # Verify the change persisted
        verify_response = requests.get(f"{BASE_URL}/api/admin/miniapp/settings")
        assert verify_response.status_code == 200
        verify_settings = verify_response.json().get("settings", {})
        assert verify_settings.get("alerts", {}).get("daily_limit") == 10
        
        # Restore original value
        original_settings["alerts"]["daily_limit"] = 5
        requests.put(
            f"{BASE_URL}/api/admin/miniapp/settings",
            json={"settings": original_settings},
            headers={"Content-Type": "application/json"}
        )
        
        print(f"PASS: Settings PUT saves to MongoDB and persists")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
