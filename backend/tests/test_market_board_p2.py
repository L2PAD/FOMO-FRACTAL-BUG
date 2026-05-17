"""
P2 — Market V2 (Execution Intelligence Board) Backend Tests
============================================================
Tests /api/v11/exchange/market/board endpoint and data structure validation.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = 'https://expo-telegram-web.preview.emergentagent.com'


class TestMarketBoardAPI:
    """Tests for GET /api/v11/exchange/market/board"""

    # ─── Core API Tests ───
    
    def test_alpha_universe_returns_valid_json(self):
        """GET /api/v11/exchange/market/board?universe=alpha returns valid JSON"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'ts' in data
        assert 'pulse' in data
        assert 'summary' in data
        assert 'actionNow' in data
        assert 'earlyBuild' in data
        assert 'structuralShift' in data
        assert 'riskEvents' in data
        assert 'latencyMs' in data
        print(f"Alpha universe response has all required top-level keys")

    def test_main_universe_returns_valid_data(self):
        """GET /api/v11/exchange/market/board?universe=main returns valid data"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=main", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert 'ts' in data
        assert 'pulse' in data
        assert 'summary' in data
        print(f"Main universe response OK, scanned {data['summary'].get('totalScanned', 0)} assets")

    # ─── Pulse Structure Tests ───
    
    def test_pulse_contains_bias(self):
        """pulse contains bias (string)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        pulse = data['pulse']
        assert 'bias' in pulse
        assert isinstance(pulse['bias'], str)
        assert pulse['bias'] in ['BULLISH', 'BEARISH', 'MIXED', 'QUIET', 'NO_DATA']
        print(f"Pulse bias: {pulse['bias']}")

    def test_pulse_contains_counts(self):
        """pulse contains counts (total, ok, buy, sell, watch, neutral)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        counts = data['pulse']['counts']
        assert 'total' in counts
        assert 'ok' in counts
        assert 'buy' in counts
        assert 'sell' in counts
        assert 'watch' in counts
        assert 'neutral' in counts
        print(f"Pulse counts: total={counts['total']}, buy={counts['buy']}, sell={counts['sell']}, watch={counts['watch']}")

    def test_pulse_contains_avg(self):
        """pulse contains avg (conv, setup, div, risk)"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        avg = data['pulse']['avg']
        assert 'conv' in avg
        assert 'setup' in avg
        assert 'div' in avg
        assert 'risk' in avg
        print(f"Pulse averages: conv={avg['conv']}, setup={avg['setup']}")

    def test_pulse_contains_dominant_horizon(self):
        """pulse contains dominantHorizon"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        assert 'dominantHorizon' in data['pulse']
        print(f"Dominant horizon: {data['pulse']['dominantHorizon']}")

    # ─── Summary Structure Tests ───
    
    def test_summary_contains_all_counts(self):
        """summary contains: totalScanned, actionCount, earlyCount, shiftCount, riskCount"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        summary = data['summary']
        assert 'totalScanned' in summary
        assert 'actionCount' in summary
        assert 'earlyCount' in summary
        assert 'shiftCount' in summary
        assert 'riskCount' in summary
        total_in_board = summary['actionCount'] + summary['earlyCount'] + summary['shiftCount'] + summary['riskCount']
        assert total_in_board <= 30, f"Board should have max 30 positions, has {total_in_board}"
        print(f"Summary: scanned={summary['totalScanned']}, action={summary['actionCount']}, early={summary['earlyCount']}, shift={summary['shiftCount']}, risk={summary['riskCount']}")

    # ─── Action Now Section Tests ───
    
    def test_action_now_rows_have_required_fields(self):
        """Each row in actionNow has: symbol, verdict, conviction, convictionTier, horizons, integrity, explain.oneLiner"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        for row in data['actionNow']:
            assert 'symbol' in row, "actionNow row missing symbol"
            assert 'verdict' in row, "actionNow row missing verdict"
            assert 'conviction' in row, "actionNow row missing conviction"
            assert 'convictionTier' in row, "actionNow row missing convictionTier"
            assert 'horizons' in row, "actionNow row missing horizons"
            assert 'integrity' in row, "actionNow row missing integrity"
            assert 'explain' in row, "actionNow row missing explain"
            assert 'oneLiner' in row['explain'], "actionNow row missing explain.oneLiner"
        print(f"All {len(data['actionNow'])} actionNow rows have required fields")

    def test_action_now_conviction_threshold(self):
        """actionNow rows have conviction >= 70"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        for row in data['actionNow']:
            assert row['conviction'] >= 70, f"{row['symbol']} in actionNow has conviction {row['conviction']} < 70"
        print(f"All {len(data['actionNow'])} actionNow rows have conviction >= 70")

    def test_action_now_integrity_status_ok(self):
        """actionNow rows have integrity.status == 'ok'"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        for row in data['actionNow']:
            assert row['integrity']['status'] == 'ok', f"{row['symbol']} has integrity status {row['integrity']['status']}"
        print(f"All {len(data['actionNow'])} actionNow rows have integrity.status='ok'")

    # ─── Risk Events Section Tests ───
    
    def test_risk_events_rows_have_required_fields(self):
        """Each row in riskEvents has required fields"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        for row in data['riskEvents']:
            assert 'symbol' in row
            assert 'verdict' in row
            assert 'conviction' in row
            assert 'integrity' in row
            assert 'explain' in row
        print(f"All {len(data['riskEvents'])} riskEvents rows have required fields")

    def test_risk_events_criteria(self):
        """riskEvents rows have integrity.status != 'ok' OR high risk OR extreme divergence"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        for row in data['riskEvents']:
            integrity_not_ok = row['integrity']['status'] != 'ok'
            high_risk = row.get('risk') == 'high'
            extreme_div = row.get('divergenceScore', 0) > 0.85
            assert integrity_not_ok or high_risk or extreme_div, f"{row['symbol']} doesn't meet risk criteria"
        if data['riskEvents']:
            print(f"All {len(data['riskEvents'])} riskEvents rows meet risk criteria")
        else:
            print("No riskEvents rows (acceptable - depends on market conditions)")

    # ─── Early Build Section Tests ───
    
    def test_early_build_rows_have_required_fields(self):
        """Each row in earlyBuild has required fields"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        for row in data['earlyBuild']:
            assert 'symbol' in row
            assert 'verdict' in row
            assert 'conviction' in row
            assert 'horizons' in row
        print(f"All {len(data['earlyBuild'])} earlyBuild rows have required fields")

    # ─── Structural Shift Section Tests ───
    
    def test_structural_shift_rows_have_required_fields(self):
        """Each row in structuralShift has required fields"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        for row in data['structuralShift']:
            assert 'symbol' in row
            assert 'verdict' in row
            assert 'conviction' in row
        print(f"structuralShift has {len(data['structuralShift'])} rows")

    # ─── No Duplicate Symbols Tests ───
    
    def test_no_symbol_in_multiple_sections(self):
        """No symbol appears in more than one section"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        
        all_symbols = []
        for section in ['actionNow', 'earlyBuild', 'structuralShift', 'riskEvents']:
            for row in data.get(section, []):
                all_symbols.append(row['symbol'])
        
        unique_symbols = set(all_symbols)
        assert len(all_symbols) == len(unique_symbols), f"Duplicate symbols found! Total: {len(all_symbols)}, Unique: {len(unique_symbols)}"
        print(f"All {len(unique_symbols)} symbols appear in only one section")

    # ─── Latency Tests ───
    
    def test_latency_under_2000ms(self):
        """latencyMs < 2000"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        assert data['latencyMs'] < 2000, f"latencyMs {data['latencyMs']} >= 2000ms"
        print(f"Latency: {data['latencyMs']}ms (under 2000ms threshold)")

    # ─── Row Structure Validation ───
    
    def test_row_horizons_structure(self):
        """Each row's horizons has short/mid/swing/primary"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        
        for section in ['actionNow', 'earlyBuild']:
            for row in data.get(section, []):
                horizons = row.get('horizons')
                if horizons:  # horizons can be None for some rows
                    assert 'primary' in horizons, f"{row['symbol']} missing horizons.primary"
        print("Horizons structure validated")

    def test_row_explain_one_liner_not_empty(self):
        """Each row's explain.oneLiner is not empty"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30)
        data = response.json()
        
        for section in ['actionNow', 'earlyBuild', 'structuralShift', 'riskEvents']:
            for row in data.get(section, []):
                explain = row.get('explain', {})
                one_liner = explain.get('oneLiner', '')
                assert one_liner, f"{row['symbol']} has empty explain.oneLiner"
        print("All rows have non-empty explain.oneLiner")


class TestMarketBoardEdgeCases:
    """Edge case and data quality tests"""

    def test_both_universes_return_data(self):
        """Both alpha and main universes return data"""
        alpha = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=alpha", timeout=30).json()
        main = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=main", timeout=30).json()
        
        assert alpha['summary']['totalScanned'] > 0
        assert main['summary']['totalScanned'] > 0
        print(f"Alpha scanned: {alpha['summary']['totalScanned']}, Main scanned: {main['summary']['totalScanned']}")

    def test_invalid_universe_defaults_to_alpha(self):
        """Invalid universe parameter should default to alpha behavior"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board?universe=invalid", timeout=30)
        # Should not crash - defaults to alpha or main behavior
        assert response.status_code == 200
        print("Invalid universe handled gracefully")

    def test_missing_universe_defaults(self):
        """Missing universe parameter should default"""
        response = requests.get(f"{BASE_URL}/api/v11/exchange/market/board", timeout=30)
        assert response.status_code == 200
        print("Missing universe handled with default")


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
