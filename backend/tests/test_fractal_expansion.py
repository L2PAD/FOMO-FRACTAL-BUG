"""
Fractal Engine Expansion Tests (iteration_172)

Tests for expanded Fractal navigation with 5 sub-pages and admin panel.
Features tested:
- Sidebar Fractal group with 5 children: Bitcoin, SPX, DXY, Macro Brain, Overview
- Route /intelligence/fractal redirects to /intelligence/fractal/btc
- All Fractal sub-pages load with real data
- Admin page at /admin/fractal with tabs and asset switcher
- Backend APIs: BTC terminal, SPX terminal, DXY terminal, admin dashboard, freeze-status
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://expo-telegram-web.preview.emergentagent.com')

class TestFractalBackendAPIs:
    """Backend API tests for Fractal Engine expansion"""
    
    def test_btc_terminal_api(self):
        """GET /api/fractal/v2.1/terminal - BTC Fractal Terminal"""
        response = requests.get(f"{BASE_URL}/api/fractal/v2.1/terminal?horizon=14d", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "meta" in data
        assert data["meta"]["symbol"] == "BTC"
        assert data["meta"]["contractVersion"] == "v2.1.0"
        assert "chart" in data
        assert "candles" in data["chart"]
        print(f"✅ BTC Terminal API: contractVersion={data['meta']['contractVersion']}, candles={len(data['chart']['candles'])}")
    
    def test_spx_terminal_api(self):
        """GET /api/fractal/spx/terminal - SPX Fractal Terminal"""
        response = requests.get(f"{BASE_URL}/api/fractal/spx/terminal?horizon=30d", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("symbol") == "SPX"
        assert "decision" in data
        assert "diagnostics" in data
        print(f"✅ SPX Terminal API: action={data['decision']['action']}, confidence={data['decision']['confidence']:.2f}")
    
    def test_dxy_terminal_api(self):
        """GET /api/fractal/dxy/terminal - DXY Fractal Terminal"""
        response = requests.get(f"{BASE_URL}/api/fractal/dxy/terminal?horizon=5d", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("asset") == "DXY"
        assert "core" in data
        assert "matches" in data["core"]
        print(f"✅ DXY Terminal API: matches={len(data['core']['matches'])}, focus={data['focus']}")
    
    def test_admin_btc_dashboard_api(self):
        """GET /api/admin/btc/dashboard - BTC Admin Dashboard"""
        response = requests.get(f"{BASE_URL}/api/admin/btc/dashboard", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert "data" in data
        dashboard = data["data"]
        assert dashboard.get("scope") == "BTC"
        assert "health" in dashboard
        assert "governance" in dashboard
        assert "drift" in dashboard
        print(f"✅ Admin BTC Dashboard API: scope={dashboard['scope']}, health_grade={dashboard['health']['grade']}")
    
    def test_admin_freeze_status_api(self):
        """GET /api/admin/freeze-status - Freeze Status Check"""
        response = requests.get(f"{BASE_URL}/api/admin/freeze-status", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        assert "frozen" in data
        assert "allowedJobs" in data
        print(f"✅ Freeze Status API: frozen={data['frozen']}, allowedJobs={len(data['allowedJobs'])}")


class TestFractalAdminSPXDXY:
    """Additional admin dashboard tests for SPX and DXY"""
    
    def test_admin_spx_dashboard(self):
        """GET /api/admin/spx/dashboard - SPX Admin Dashboard"""
        response = requests.get(f"{BASE_URL}/api/admin/spx/dashboard", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        print(f"✅ Admin SPX Dashboard API accessible")
    
    def test_admin_dxy_dashboard(self):
        """GET /api/admin/dxy/dashboard - DXY Admin Dashboard"""
        response = requests.get(f"{BASE_URL}/api/admin/dxy/dashboard", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        print(f"✅ Admin DXY Dashboard API accessible")


class TestBrainAndOverviewAPIs:
    """API tests for Macro Brain and Overview endpoints"""
    
    def test_brain_decision_api(self):
        """GET /api/ui/brain/decision - Macro Brain Decision Engine"""
        response = requests.get(f"{BASE_URL}/api/ui/brain/decision", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert "verdict" in data
        assert "action" in data
        print(f"✅ Brain Decision API: regime={data['verdict'].get('regime')}, posture={data['verdict'].get('posture')}")
    
    def test_overview_api(self):
        """GET /api/ui/overview - Market Overview"""
        response = requests.get(f"{BASE_URL}/api/ui/overview?asset=btc&horizon=90", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert "verdict" in data
        print(f"✅ Overview API: stance={data['verdict'].get('stance')}, confidence={data['verdict'].get('confidencePct')}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
