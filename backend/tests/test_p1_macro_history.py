"""
P1 Market Context Layer Tests - Fear & Greed History Endpoint
Tests historical Fear & Greed data API (7 days default, custom days parameter)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFearGreedHistoryEndpoint:
    """Test /api/v10/macro/fear-greed/history endpoint"""
    
    def test_history_default_7_days(self):
        """GET /api/v10/macro/fear-greed/history returns 7 days by default"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/fear-greed/history")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, "Response should have ok=true"
        assert 'data' in data, "Response should have data field"
        assert 'history' in data['data'], "Data should have history array"
        assert 'quality' in data['data'], "Data should have quality info"
        assert 'days' in data['data'], "Data should have days count"
        
        # Verify 7 days default
        history = data['data']['history']
        assert len(history) == 7, f"Expected 7 days, got {len(history)}"
        print(f"✅ History returned {len(history)} days")
    
    def test_history_custom_days_14(self):
        """GET /api/v10/macro/fear-greed/history?days=14 returns 14 days"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/fear-greed/history?days=14")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        
        history = data['data']['history']
        assert len(history) == 14, f"Expected 14 days, got {len(history)}"
        print(f"✅ Custom days=14 returned {len(history)} days")
    
    def test_history_data_structure(self):
        """Each history point has required fields: value, label, timestamp, date"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/fear-greed/history")
        assert response.status_code == 200
        
        data = response.json()
        history = data['data']['history']
        
        for point in history:
            assert 'value' in point, "History point should have value"
            assert 'label' in point, "History point should have label"
            assert 'timestamp' in point, "History point should have timestamp"
            assert 'date' in point, "History point should have date"
            
            # Verify value is numeric 0-100
            assert isinstance(point['value'], int), "Value should be integer"
            assert 0 <= point['value'] <= 100, f"Value should be 0-100, got {point['value']}"
            
            # Verify label is valid
            valid_labels = ['EXTREME_FEAR', 'FEAR', 'NEUTRAL', 'GREED', 'EXTREME_GREED']
            assert point['label'] in valid_labels, f"Invalid label: {point['label']}"
            
            # Verify timestamp is numeric (milliseconds)
            assert isinstance(point['timestamp'], int), "Timestamp should be integer"
            
            # Verify date format YYYY-MM-DD
            assert len(point['date']) == 10, f"Date should be YYYY-MM-DD format: {point['date']}"
            
        print(f"✅ All {len(history)} history points have valid structure")
    
    def test_history_quality_info(self):
        """Quality info should have mode, missing fields"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/fear-greed/history")
        assert response.status_code == 200
        
        data = response.json()
        quality = data['data']['quality']
        
        assert 'mode' in quality, "Quality should have mode"
        valid_modes = ['LIVE', 'CACHED', 'DEGRADED', 'NO_DATA']
        assert quality['mode'] in valid_modes, f"Invalid mode: {quality['mode']}"
        
        assert 'missing' in quality, "Quality should have missing array"
        
        print(f"✅ Quality mode: {quality['mode']}")
    
    def test_history_max_30_days(self):
        """days parameter should be capped at 30"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/fear-greed/history?days=50")
        assert response.status_code == 200
        
        data = response.json()
        history = data['data']['history']
        
        # Should cap at 30 max
        assert len(history) <= 30, f"Expected max 30 days, got {len(history)}"
        print(f"✅ days=50 request returned {len(history)} days (capped)")
    
    def test_history_min_1_day(self):
        """days parameter should have minimum of 1"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/fear-greed/history?days=0")
        assert response.status_code == 200
        
        data = response.json()
        history = data['data']['history']
        
        # Should have at least 1 day
        assert len(history) >= 1, f"Expected at least 1 day, got {len(history)}"
        print(f"✅ days=0 request returned {len(history)} day(s) (min 1)")


class TestMacroImpactEndpoint:
    """Test /api/v10/macro/impact endpoint for Macro Context in ReasonTree"""
    
    def test_impact_endpoint(self):
        """GET /api/v10/macro/impact returns signal and impact"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
        assert 'signal' in data['data'], "Should have signal object"
        assert 'impact' in data['data'], "Should have impact object"
        
        print("✅ Impact endpoint returns signal and impact")
    
    def test_signal_has_flags(self):
        """Signal should have flags array for ReasonTree display"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        
        signal = data['data']['signal']
        assert 'flags' in signal, "Signal should have flags"
        assert isinstance(signal['flags'], list), "Flags should be list"
        
        print(f"✅ Signal has flags: {signal['flags']}")
    
    def test_signal_has_explain(self):
        """Signal should have explanation for ReasonTree display"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        
        signal = data['data']['signal']
        assert 'explain' in signal, "Signal should have explain"
        assert 'summary' in signal['explain'], "Explain should have summary"
        assert 'bullets' in signal['explain'], "Explain should have bullets"
        
        print(f"✅ Signal has explanation: {signal['explain']['summary'][:50]}...")
    
    def test_impact_confidence_multiplier(self):
        """Impact should have confidenceMultiplier for penalty display"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        
        impact = data['data']['impact']
        assert 'confidenceMultiplier' in impact, "Impact should have confidenceMultiplier"
        assert isinstance(impact['confidenceMultiplier'], (int, float)), "Should be numeric"
        assert 0 <= impact['confidenceMultiplier'] <= 1, "Should be 0-1"
        
        print(f"✅ Confidence multiplier: {impact['confidenceMultiplier']}")
    
    def test_impact_blocked_strong(self):
        """Impact should have blockedStrong for BLOCKED status"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        
        impact = data['data']['impact']
        assert 'blockedStrong' in impact, "Impact should have blockedStrong"
        assert isinstance(impact['blockedStrong'], bool), "Should be boolean"
        
        print(f"✅ blockedStrong: {impact['blockedStrong']}")
    
    def test_fear_greed_in_explain(self):
        """Signal explanation should contain Fear & Greed value for ReasonTree"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        
        signal = data['data']['signal']
        bullets = signal['explain']['bullets']
        
        # First bullet should have Fear & Greed info
        fg_bullet = bullets[0] if bullets else ''
        assert 'Fear & Greed' in fg_bullet, "First bullet should contain Fear & Greed"
        
        print(f"✅ Fear & Greed in explanation: {fg_bullet}")


class TestMacroFlags:
    """Test macro flags for ReasonTree display"""
    
    def test_panic_flag_triggers_on_extreme_fear(self):
        """MACRO_PANIC flag should be present in extreme fear conditions"""
        response = requests.get(f"{BASE_URL}/api/v10/macro/impact")
        data = response.json()
        
        signal = data['data']['signal']
        fg_value = None
        
        # Parse F&G value from bullets
        for bullet in signal['explain']['bullets']:
            if 'Fear & Greed' in bullet:
                import re
                match = re.search(r'Fear & Greed: (\d+)', bullet)
                if match:
                    fg_value = int(match.group(1))
                    break
        
        if fg_value is not None and fg_value <= 20:
            assert 'MACRO_PANIC' in signal['flags'], "MACRO_PANIC should be flagged for extreme fear"
            print(f"✅ MACRO_PANIC flag present for F&G={fg_value}")
        else:
            print(f"⚠️ F&G={fg_value} - not in extreme fear, skipping MACRO_PANIC check")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
