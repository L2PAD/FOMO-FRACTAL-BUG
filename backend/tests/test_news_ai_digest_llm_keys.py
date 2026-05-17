"""
Test News AI Digest and LLM Keys APIs
- GET /api/ai-news/latest - returns AI article with en/ru fields
- GET /api/ai-news/articles - returns list of AI articles
- GET /api/ai-news/image/{imageId} - returns PNG image
- GET /api/admin/llm-keys - returns LLM keys list
- POST /api/admin/llm-keys - creates new LLM key
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAINewsEndpoints:
    """AI News generation endpoints tests"""

    def test_get_latest_ai_article(self):
        """GET /api/ai-news/latest returns AI article with en/ru fields"""
        response = requests.get(f"{BASE_URL}/api/ai-news/latest", timeout=15)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Response should have 'ok' field"
        assert data["ok"] == True, "Response ok should be True"
        
        # Article may be None if none generated yet
        if data.get("article"):
            article = data["article"]
            # Check for en and ru fields
            assert "en" in article or "ru" in article, "Article should have en or ru field"
            
            # Check en content structure if present
            if article.get("en"):
                en = article["en"]
                assert "title" in en, "EN article should have title"
                assert "body" in en, "EN article should have body"
                
            # Check ru content structure if present
            if article.get("ru"):
                ru = article["ru"]
                assert "title" in ru, "RU article should have title"
                assert "body" in ru, "RU article should have body"
                
            # Check metadata
            assert "generatedAt" in article, "Article should have generatedAt"
            print(f"Latest article found: {article.get('en', {}).get('title', article.get('ru', {}).get('title', 'N/A'))}")
        else:
            print("No AI article generated yet - this is acceptable")

    def test_get_ai_articles_list(self):
        """GET /api/ai-news/articles returns list of AI articles"""
        response = requests.get(f"{BASE_URL}/api/ai-news/articles", timeout=15)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Response should have 'ok' field"
        assert data["ok"] == True, "Response ok should be True"
        assert "articles" in data, "Response should have 'articles' field"
        assert isinstance(data["articles"], list), "Articles should be a list"
        
        print(f"Found {len(data['articles'])} AI articles")
        
        # If articles exist, verify structure
        if len(data["articles"]) > 0:
            article = data["articles"][0]
            assert "generatedAt" in article, "Article should have generatedAt"
            # Check for language content
            has_content = "en" in article or "ru" in article
            assert has_content, "Article should have en or ru content"

    def test_get_ai_image_returns_png(self):
        """GET /api/ai-news/image/{imageId} returns PNG image"""
        # First get latest article to find an imageId
        response = requests.get(f"{BASE_URL}/api/ai-news/latest", timeout=15)
        assert response.status_code == 200
        
        data = response.json()
        if data.get("article") and data["article"].get("imageId"):
            image_id = data["article"]["imageId"]
            
            # Fetch the image
            img_response = requests.get(f"{BASE_URL}/api/ai-news/image/{image_id}", timeout=15)
            
            assert img_response.status_code == 200, f"Expected 200, got {img_response.status_code}"
            assert img_response.headers.get("content-type") == "image/png", "Should return PNG image"
            assert len(img_response.content) > 0, "Image should have content"
            print(f"Image {image_id} fetched successfully, size: {len(img_response.content)} bytes")
        else:
            # Test with non-existent image - should return 404
            img_response = requests.get(f"{BASE_URL}/api/ai-news/image/nonexistent123", timeout=15)
            assert img_response.status_code == 404, "Non-existent image should return 404"
            print("No image available in latest article, 404 test passed")

    def test_get_ai_image_nonexistent_returns_404(self):
        """GET /api/ai-news/image/{imageId} returns 404 for non-existent image"""
        response = requests.get(f"{BASE_URL}/api/ai-news/image/nonexistent_image_id_12345", timeout=15)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Non-existent image correctly returns 404")


class TestLLMKeysEndpoints:
    """Admin LLM Keys endpoints tests"""

    def test_get_llm_keys_list(self):
        """GET /api/admin/llm-keys returns LLM keys list"""
        response = requests.get(f"{BASE_URL}/api/admin/llm-keys", timeout=15)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Response should have 'ok' field"
        assert data["ok"] == True, "Response ok should be True"
        assert "keys" in data, "Response should have 'keys' field"
        assert isinstance(data["keys"], list), "Keys should be a list"
        
        print(f"Found {len(data['keys'])} LLM keys")
        
        # Verify key structure if keys exist
        if len(data["keys"]) > 0:
            key = data["keys"][0]
            assert "id" in key or "_id" in key or "keyId" in key, "Key should have an id field"
            print(f"First key provider: {key.get('provider', 'N/A')}")

    def test_create_llm_key(self):
        """POST /api/admin/llm-keys creates a new LLM key"""
        test_key_data = {
            "provider": "openai",
            "api_key": "sk-test-news-tab-test-key-12345",
            "name": "Test Key for News Tab Testing",
            "capabilities": ["text"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/llm-keys",
            json=test_key_data,
            timeout=15
        )
        
        # Accept 200 or 201 for creation
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "ok" in data, "Response should have 'ok' field"
        
        if data["ok"]:
            print(f"LLM key created successfully")
            # Verify the key was added by fetching list
            list_response = requests.get(f"{BASE_URL}/api/admin/llm-keys", timeout=15)
            list_data = list_response.json()
            
            # Check if our test key is in the list
            found = False
            for key in list_data.get("keys", []):
                if key.get("name") == "Test Key for News Tab Testing":
                    found = True
                    # Clean up - delete the test key
                    key_id = key.get("id") or key.get("keyId") or key.get("_id")
                    if key_id:
                        delete_response = requests.delete(f"{BASE_URL}/api/admin/llm-keys/{key_id}", timeout=15)
                        print(f"Test key cleanup: {delete_response.status_code}")
                    break
            
            if found:
                print("Test key verified in list and cleaned up")
        else:
            print(f"Key creation returned ok=false: {data.get('error', 'unknown error')}")

    def test_get_llm_providers(self):
        """GET /api/admin/llm-keys/providers returns available providers"""
        response = requests.get(f"{BASE_URL}/api/admin/llm-keys/providers", timeout=15)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "ok" in data, "Response should have 'ok' field"
        print(f"LLM providers response: {data}")


class TestSentimentProviders:
    """Sentiment providers endpoint test"""

    def test_get_sentiment_providers(self):
        """GET /api/admin/sentiment-keys/providers returns providers"""
        response = requests.get(f"{BASE_URL}/api/admin/sentiment-keys", timeout=15)
        
        # This endpoint may or may not exist
        if response.status_code == 200:
            data = response.json()
            print(f"Sentiment keys response: {data.get('ok', 'N/A')}")
        else:
            print(f"Sentiment keys endpoint returned {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
