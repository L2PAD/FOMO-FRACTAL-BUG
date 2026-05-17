"""
Sentiment V1 Universal API Tests
================================
Testing the standalone, versioned sentiment analysis API.
Endpoints: /api/v1/sentiment/*

Features tested:
- Health check endpoint
- Capabilities endpoint  
- Single text analysis with validation
- Batch analysis with validation
- Sentiment accuracy for positive/negative/neutral texts
"""

import pytest
import requests
import os

# Use internal Node.js service URL (port 8003) for reliable testing
# The external URL times out, but internal service works perfectly
BASE_URL = "http://localhost:8003"
SENTIMENT_V1_PREFIX = f"{BASE_URL}/api/v1/sentiment"


class TestSentimentV1Health:
    """Health and capabilities endpoint tests"""
    
    def test_health_endpoint_returns_ok(self):
        """GET /api/v1/sentiment/health should return ok:true with status READY"""
        response = requests.get(f"{SENTIMENT_V1_PREFIX}/health", timeout=10)
        
        assert response.status_code == 200, f"Health endpoint returned {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Health check should return ok: true"
        assert "data" in data, "Response should have data field"
        
        health_data = data["data"]
        assert health_data.get("status") == "READY", f"Status should be READY, got {health_data.get('status')}"
        assert health_data.get("engineVersion") == "2.0.0", f"Engine version should be 2.0.0, got {health_data.get('engineVersion')}"
        assert "uptime" in health_data, "Should have uptime"
        assert "startedAt" in health_data, "Should have startedAt"
        
        print(f"✓ Health endpoint OK: status={health_data['status']}, engineVersion={health_data['engineVersion']}")
    
    def test_capabilities_endpoint(self):
        """GET /api/v1/sentiment/capabilities should return engine metadata"""
        response = requests.get(f"{SENTIMENT_V1_PREFIX}/capabilities", timeout=10)
        
        assert response.status_code == 200, f"Capabilities endpoint returned {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Capabilities should return ok: true"
        assert "data" in data, "Response should have data field"
        
        caps = data["data"]
        
        # Check required fields
        assert caps.get("engineVersion") == "2.0.0", f"Engine version mismatch: {caps.get('engineVersion')}"
        assert "lexiconStats" in caps, "Should have lexiconStats"
        assert "weights" in caps, "Should have weights"
        assert "thresholds" in caps, "Should have thresholds"
        assert "limits" in caps, "Should have limits"
        
        # Check lexiconStats structure
        lex_stats = caps["lexiconStats"]
        assert "positive" in lex_stats, "Should have positive count"
        assert "negative" in lex_stats, "Should have negative count"
        assert "neutral" in lex_stats, "Should have neutral count"
        assert lex_stats["positive"] > 0, "Should have positive words"
        assert lex_stats["negative"] > 0, "Should have negative words"
        
        # Check weights
        weights = caps["weights"]
        assert "cnn" in weights, "Should have cnn weight"
        assert "lexicon" in weights, "Should have lexicon weight"
        assert "rules" in weights, "Should have rules weight"
        
        # Check limits
        limits = caps["limits"]
        assert limits.get("maxTextLength") == 10000, f"Max text length should be 10000"
        assert limits.get("maxBatchSize") == 100, f"Max batch size should be 100"
        
        print(f"✓ Capabilities endpoint OK: lexicon={lex_stats}, limits={limits}")


class TestSentimentV1Analyze:
    """Single text analysis endpoint tests"""
    
    def test_analyze_positive_text(self):
        """POST /api/v1/sentiment/analyze with positive text should return POSITIVE"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={"text": "Bitcoin is looking extremely bullish! Moon incoming, pump it up!"},
            timeout=10
        )
        
        assert response.status_code == 200, f"Analyze returned {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Should return ok: true"
        
        result = data["data"]
        assert result.get("label") == "POSITIVE", f"Expected POSITIVE, got {result.get('label')}"
        assert "score" in result, "Should have score"
        assert 0 <= result["score"] <= 1, f"Score should be 0-1, got {result['score']}"
        
        # Check meta structure
        meta = result["meta"]
        assert meta.get("engineVersion") == "2.0.0", "Should have correct engine version"
        assert "confidence" in meta, "Should have confidence level"
        assert "breakdown" in meta, "Should have breakdown"
        assert "detected" in meta, "Should have detected words"
        
        detected = meta["detected"]
        assert len(detected.get("positiveWords", [])) > 0, "Should detect positive words"
        
        print(f"✓ Positive text analysis: label={result['label']}, score={result['score']}, positive_words={detected.get('positiveWords')}")
    
    def test_analyze_negative_text(self):
        """POST /api/v1/sentiment/analyze with negative text should return NEGATIVE"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={"text": "Market is crashing hard! Panic selling, dump everything. Fear is spreading."},
            timeout=10
        )
        
        assert response.status_code == 200, f"Analyze returned {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        
        result = data["data"]
        assert result.get("label") == "NEGATIVE", f"Expected NEGATIVE, got {result.get('label')}"
        
        detected = result["meta"]["detected"]
        assert len(detected.get("negativeWords", [])) > 0, "Should detect negative words"
        
        print(f"✓ Negative text analysis: label={result['label']}, score={result['score']}, negative_words={detected.get('negativeWords')}")
    
    def test_analyze_neutral_text(self):
        """POST /api/v1/sentiment/analyze with neutral text should return NEUTRAL"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={"text": "The market remains stable and unchanged. Trading volume is flat and sideways."},
            timeout=10
        )
        
        assert response.status_code == 200, f"Analyze returned {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        
        result = data["data"]
        assert result.get("label") == "NEUTRAL", f"Expected NEUTRAL, got {result.get('label')}"
        
        detected = result["meta"]["detected"]
        assert len(detected.get("neutralWords", [])) > 0, "Should detect neutral words"
        
        print(f"✓ Neutral text analysis: label={result['label']}, score={result['score']}, neutral_words={detected.get('neutralWords')}")
    
    def test_analyze_single_word_returns_neutral_low_confidence(self):
        """Single word text should return NEUTRAL with LOW confidence"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={"text": "hello"},
            timeout=10
        )
        
        assert response.status_code == 200
        
        data = response.json()
        result = data["data"]
        
        assert result.get("label") == "NEUTRAL", f"Single word should be NEUTRAL, got {result.get('label')}"
        
        meta = result["meta"]
        assert meta.get("confidence") == "LOW", f"Single word should have LOW confidence, got {meta.get('confidence')}"
        assert meta["detected"].get("singleWord") is True, "Should detect single word"
        
        print(f"✓ Single word analysis: label={result['label']}, confidence={meta['confidence']}, singleWord=True")
    
    def test_analyze_validation_empty_body(self):
        """POST /api/v1/sentiment/analyze with empty body should return 400 INVALID_INPUT"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={},
            timeout=10
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is False, "Should return ok: false"
        assert data.get("error") == "INVALID_INPUT", f"Error should be INVALID_INPUT, got {data.get('error')}"
        
        print(f"✓ Empty body validation: status=400, error={data.get('error')}")
    
    def test_analyze_validation_text_too_long(self):
        """POST /api/v1/sentiment/analyze with text >10000 chars should return 400 TEXT_TOO_LONG"""
        long_text = "a" * 10001  # Exceeds 10000 char limit
        
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={"text": long_text},
            timeout=10
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "TEXT_TOO_LONG", f"Error should be TEXT_TOO_LONG, got {data.get('error')}"
        
        print(f"✓ Text too long validation: status=400, error={data.get('error')}")
    
    def test_analyze_response_has_meta_breakdown(self):
        """Analyze response should include meta breakdown with scores"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={"text": "This is a test message about crypto markets"},
            timeout=10
        )
        
        assert response.status_code == 200
        
        data = response.json()
        result = data["data"]
        meta = result["meta"]
        
        # Check breakdown structure
        breakdown = meta.get("breakdown", {})
        assert "cnnScore" in breakdown, "Should have cnnScore"
        assert "cnnContribution" in breakdown, "Should have cnnContribution"
        assert "lexScoreNorm" in breakdown, "Should have lexScoreNorm"
        assert "lexContribution" in breakdown, "Should have lexContribution"
        assert "rulesBias" in breakdown, "Should have rulesBias"
        assert "rulesContribution" in breakdown, "Should have rulesContribution"
        
        # Check all scores are numeric
        for key, value in breakdown.items():
            assert isinstance(value, (int, float)), f"{key} should be numeric"
        
        print(f"✓ Meta breakdown present: {breakdown}")


class TestSentimentV1Batch:
    """Batch analysis endpoint tests"""
    
    def test_batch_analyze_multiple_items(self):
        """POST /api/v1/sentiment/batch with multiple items should return results per item"""
        items = [
            {"id": "item-1", "text": "Bitcoin is bullish, moon soon!"},
            {"id": "item-2", "text": "Market crash incoming, panic!"},
            {"id": "item-3", "text": "Prices remain stable and flat"},
        ]
        
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/batch",
            json={"items": items},
            timeout=15
        )
        
        assert response.status_code == 200, f"Batch returned {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True
        
        batch_result = data["data"]
        assert "results" in batch_result, "Should have results array"
        assert "meta" in batch_result, "Should have meta"
        
        results = batch_result["results"]
        assert len(results) == 3, f"Should have 3 results, got {len(results)}"
        
        # Check each result has correct id
        result_ids = [r["id"] for r in results]
        assert "item-1" in result_ids
        assert "item-2" in result_ids
        assert "item-3" in result_ids
        
        # Check meta
        meta = batch_result["meta"]
        assert meta.get("totalItems") == 3
        assert meta.get("successCount") == 3
        assert meta.get("errorCount") == 0
        assert meta.get("engineVersion") == "2.0.0"
        
        # Verify sentiment labels make sense
        for r in results:
            if r["id"] == "item-1":
                assert r["result"]["label"] == "POSITIVE", f"item-1 should be POSITIVE"
            elif r["id"] == "item-2":
                assert r["result"]["label"] == "NEGATIVE", f"item-2 should be NEGATIVE"
            elif r["id"] == "item-3":
                assert r["result"]["label"] == "NEUTRAL", f"item-3 should be NEUTRAL"
        
        print(f"✓ Batch analysis OK: {len(results)} items processed, meta={meta}")
    
    def test_batch_validation_empty_items(self):
        """POST /api/v1/sentiment/batch with empty items array should return 400 EMPTY_BATCH"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/batch",
            json={"items": []},
            timeout=10
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "EMPTY_BATCH", f"Error should be EMPTY_BATCH, got {data.get('error')}"
        
        print(f"✓ Empty batch validation: status=400, error={data.get('error')}")
    
    def test_batch_validation_item_missing_id(self):
        """POST /api/v1/sentiment/batch with item missing id should return 400 INVALID_ITEM"""
        items = [
            {"text": "This item has no id"}  # Missing id field
        ]
        
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/batch",
            json={"items": items},
            timeout=10
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "INVALID_ITEM", f"Error should be INVALID_ITEM, got {data.get('error')}"
        
        print(f"✓ Missing id validation: status=400, error={data.get('error')}")
    
    def test_batch_validation_too_many_items(self):
        """POST /api/v1/sentiment/batch with >100 items should return 400 BATCH_TOO_LARGE"""
        # Create 101 items
        items = [{"id": f"item-{i}", "text": f"Test text {i}"} for i in range(101)]
        
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/batch",
            json={"items": items},
            timeout=30
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is False
        assert data.get("error") == "BATCH_TOO_LARGE", f"Error should be BATCH_TOO_LARGE, got {data.get('error')}"
        
        print(f"✓ Batch too large validation: status=400, error={data.get('error')}")


class TestSentimentAccuracy:
    """Sentiment accuracy tests for specific word categories"""
    
    def test_positive_words_bullish_pump_moon(self):
        """Text with bullish, pump, moon should return POSITIVE"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={"text": "This coin is bullish! Expecting a massive pump to the moon!"},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        result = data["data"]
        
        assert result["label"] == "POSITIVE", f"Expected POSITIVE for bullish/pump/moon, got {result['label']}"
        
        detected = result["meta"]["detected"]["positiveWords"]
        assert "bullish" in detected or "pump" in detected or "moon" in detected, f"Should detect positive keywords"
        
        print(f"✓ Positive keywords detected: {detected}, label={result['label']}")
    
    def test_negative_words_crash_dump_panic(self):
        """Text with crash, dump, panic should return NEGATIVE"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={"text": "The market will crash soon! Everyone is in panic, time to dump!"},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        result = data["data"]
        
        assert result["label"] == "NEGATIVE", f"Expected NEGATIVE for crash/dump/panic, got {result['label']}"
        
        detected = result["meta"]["detected"]["negativeWords"]
        assert "crash" in detected or "dump" in detected or "panic" in detected, f"Should detect negative keywords"
        
        print(f"✓ Negative keywords detected: {detected}, label={result['label']}")
    
    def test_neutral_words_stable_sideways(self):
        """Text with stable, sideways should return NEUTRAL"""
        response = requests.post(
            f"{SENTIMENT_V1_PREFIX}/analyze",
            json={"text": "The price has been stable and trading sideways for weeks"},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        result = data["data"]
        
        assert result["label"] == "NEUTRAL", f"Expected NEUTRAL for stable/sideways, got {result['label']}"
        
        detected = result["meta"]["detected"]["neutralWords"]
        assert "stable" in detected or "sideways" in detected, f"Should detect neutral keywords"
        
        print(f"✓ Neutral keywords detected: {detected}, label={result['label']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
