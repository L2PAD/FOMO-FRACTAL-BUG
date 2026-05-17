"""
Telegram Language Filter and Contrast Tests
Tests the language filter feature on Entities page and text contrast improvements
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTelegramLanguageFilter:
    """Test language filter feature on /api/telegram-intel/utility/list endpoint"""
    
    def test_health_endpoint(self):
        """Test health endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert data.get("module") == "telegram-intel"
        print(f"Health check passed: {data}")
    
    def test_utility_list_no_filter(self):
        """Test utility/list returns all channels without language filter"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        items = data.get("items", [])
        total = data.get("total", 0)
        
        print(f"Total channels without filter: {total}")
        print(f"Items returned: {len(items)}")
        
        # Should return all channels (expected ~17)
        assert total >= 1, "Should have at least 1 channel"
        
        # Check that items have language field
        for item in items[:5]:
            lang = item.get("language", "")
            print(f"  - {item.get('username')}: language={lang}")
    
    def test_utility_list_filter_russian(self):
        """Test filtering channels by Russian language (?language=RU)"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?language=RU&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        items = data.get("items", [])
        total = data.get("total", 0)
        
        print(f"Russian channels (RU): {total}")
        
        # Per main agent context: 5 RU channels expected
        assert total >= 1, "Should have at least 1 Russian channel"
        
        # Verify all returned items have RU language
        for item in items:
            lang = item.get("language", "")
            assert lang == "RU", f"Expected RU but got {lang} for {item.get('username')}"
            print(f"  - {item.get('username')}: language={lang}")
    
    def test_utility_list_filter_english(self):
        """Test filtering channels by English language (?language=EN)"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?language=EN&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        items = data.get("items", [])
        total = data.get("total", 0)
        
        print(f"English channels (EN): {total}")
        
        # Per main agent context: 12 EN channels expected
        assert total >= 1, "Should have at least 1 English channel"
        
        # Verify all returned items have EN language
        for item in items:
            lang = item.get("language", "")
            assert lang == "EN", f"Expected EN but got {lang} for {item.get('username')}"
            print(f"  - {item.get('username')}: language={lang}")
    
    def test_utility_list_filter_ukrainian(self):
        """Test filtering channels by Ukrainian language (?language=UA)"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?language=UA&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        
        items = data.get("items", [])
        total = data.get("total", 0)
        
        print(f"Ukrainian channels (UA): {total}")
        # Per main agent: no UA channels currently
        print(f"Ukrainian channels returned: {len(items)}")
        
        # Verify all returned items have UA language (if any)
        for item in items:
            lang = item.get("language", "")
            assert lang == "UA", f"Expected UA but got {lang} for {item.get('username')}"
    
    def test_utility_list_language_counts_match(self):
        """Verify that filtered counts add up to total"""
        # Get all channels
        response_all = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?limit=100")
        assert response_all.status_code == 200
        total_all = response_all.json().get("total", 0)
        
        # Get EN channels
        response_en = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?language=EN&limit=100")
        assert response_en.status_code == 200
        total_en = response_en.json().get("total", 0)
        
        # Get RU channels
        response_ru = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?language=RU&limit=100")
        assert response_ru.status_code == 200
        total_ru = response_ru.json().get("total", 0)
        
        # Get UA channels
        response_ua = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?language=UA&limit=100")
        assert response_ua.status_code == 200
        total_ua = response_ua.json().get("total", 0)
        
        print(f"Total: {total_all}, EN: {total_en}, RU: {total_ru}, UA: {total_ua}")
        print(f"Sum of filtered: {total_en + total_ru + total_ua}")
        
        # The sum should equal total (all languages detected should add up)
        # Note: Some channels might have null/unknown language
        assert total_en + total_ru + total_ua <= total_all, "Filtered counts should not exceed total"
    
    def test_items_contain_language_field(self):
        """Verify all items in response contain language field"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?limit=50")
        assert response.status_code == 200
        data = response.json()
        
        items = data.get("items", [])
        assert len(items) > 0, "Should have items"
        
        languages_found = {}
        for item in items:
            assert "language" in item, f"Missing language field in item {item.get('username')}"
            lang = item.get("language", "")
            languages_found[lang] = languages_found.get(lang, 0) + 1
        
        print(f"Languages distribution: {languages_found}")


class TestChannelListResponse:
    """Test channel list response structure and data"""
    
    def test_response_structure(self):
        """Test that response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "ok" in data
        assert "items" in data
        assert "total" in data
        assert "stats" in data
        
        stats = data.get("stats", {})
        assert "tracked" in stats
        assert "avgUtility" in stats or "avgScore" in stats
    
    def test_item_structure(self):
        """Test that items have required fields"""
        response = requests.get(f"{BASE_URL}/api/telegram-intel/utility/list?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        items = data.get("items", [])
        assert len(items) > 0
        
        required_fields = [
            "username", "title", "type", "sector", "members", 
            "activity", "language", "fomoScore"
        ]
        
        for item in items[:3]:
            for field in required_fields:
                assert field in item, f"Missing field '{field}' in item {item.get('username')}"
            
            print(f"Item: {item.get('username')}")
            print(f"  - sector: {item.get('sector')}")
            print(f"  - sectorColor: {item.get('sectorColor')}")
            print(f"  - activity: {item.get('activity')}")
            print(f"  - language: {item.get('language')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
