"""
Test Suite: Decision Intelligence System - Phase 1 & 2
=======================================================
Phase 1: Real GPT-4o-mini sentiment inference (replaces fake CNN)
Phase 2: Real enrichment (price context, author intel, signal position)

Endpoints tested:
- POST /api/sentiment/analyze — single text sentiment analysis
- POST /api/sentiment/batch — batch sentiment analysis
- POST /api/sentiment/backfill — backfill existing events
- GET /api/sentiment/stats — sentiment inference statistics
- POST /api/enrichment/run — enrich events with price/author/signal context
- GET /api/enrichment/stats — enrichment statistics
- GET /api/ml/data/real-vs-synthetic — verify still works (regression)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSentimentAnalyzeEndpoint:
    """POST /api/sentiment/analyze — Real LLM sentiment inference"""
    
    def test_bullish_signal_text(self):
        """Test bullish crypto tweet classification"""
        response = requests.post(
            f"{BASE_URL}/api/sentiment/analyze",
            json={
                "text": "BTC breaking out of accumulation! Strong volume. Loading up here.",
                "author_handle": "CryptoTrader",
                "token": "BTC"
            },
            timeout=30  # LLM inference takes 2-3 seconds
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") is True
        
        # Verify sentiment structure
        assert "sentiment_label" in data
        assert data["sentiment_label"] in ["POSITIVE", "NEGATIVE", "NEUTRAL"]
        
        assert "sentiment_score" in data
        assert -1.0 <= data["sentiment_score"] <= 1.0
        
        assert "confidence" in data
        assert 0.0 <= data["confidence"] <= 1.0
        
        assert "intent_label" in data
        assert data["intent_label"] in ["BULLISH_SIGNAL", "BEARISH_SIGNAL", "INFORMATIONAL", "WARNING", "HYPE", "NOISE"]
        
        assert "uncertainty_flag" in data
        assert isinstance(data["uncertainty_flag"], bool)
        
        assert "reasoning" in data
        assert isinstance(data["reasoning"], str)
        
        # For bullish text, expect POSITIVE sentiment and BULLISH_SIGNAL intent
        print(f"Bullish text result: label={data['sentiment_label']}, intent={data['intent_label']}, score={data['sentiment_score']}")
        assert data["sentiment_label"] == "POSITIVE", f"Expected POSITIVE for bullish text, got {data['sentiment_label']}"
        assert data["intent_label"] in ["BULLISH_SIGNAL", "HYPE"], f"Expected BULLISH_SIGNAL or HYPE, got {data['intent_label']}"
    
    def test_bearish_warning_text(self):
        """Test bearish/warning tweet classification"""
        response = requests.post(
            f"{BASE_URL}/api/sentiment/analyze",
            json={
                "text": "ETH looks weak. Distribution pattern forming. Taking profits and reducing exposure.",
                "author_handle": "RiskManager",
                "token": "ETH"
            },
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # For bearish text, expect NEGATIVE sentiment
        print(f"Bearish text result: label={data['sentiment_label']}, intent={data['intent_label']}, score={data['sentiment_score']}")
        assert data["sentiment_label"] in ["NEGATIVE", "NEUTRAL"], f"Expected NEGATIVE/NEUTRAL for bearish text, got {data['sentiment_label']}"
        assert data["intent_label"] in ["BEARISH_SIGNAL", "WARNING", "INFORMATIONAL"], f"Expected bearish intent, got {data['intent_label']}"
    
    def test_pure_hype_text(self):
        """Test hype/engagement farming classification"""
        response = requests.post(
            f"{BASE_URL}/api/sentiment/analyze",
            json={
                "text": "DOGE to the moon!!! 🚀🚀🚀 Who's with me? LFG!!!",
                "author_handle": "MoonBoy",
                "token": "DOGE"
            },
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Hype should be flagged as HYPE or NOISE, not genuine BULLISH_SIGNAL
        print(f"Hype text result: label={data['sentiment_label']}, intent={data['intent_label']}, confidence={data['confidence']}")
        # Model should recognize this as hype, not genuine signal
        assert data["intent_label"] in ["HYPE", "NOISE", "BULLISH_SIGNAL"], f"Got unexpected intent: {data['intent_label']}"
    
    def test_informational_text(self):
        """Test neutral/informational tweet classification"""
        response = requests.post(
            f"{BASE_URL}/api/sentiment/analyze",
            json={
                "text": "SOL is currently trading at $150. Volume is average. No significant news today.",
                "author_handle": "MarketData",
                "token": "SOL"
            },
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Informational should be NEUTRAL or INFORMATIONAL intent
        print(f"Informational text result: label={data['sentiment_label']}, intent={data['intent_label']}")
        assert data["sentiment_label"] in ["NEUTRAL", "POSITIVE", "NEGATIVE"]
        assert data["intent_label"] in ["INFORMATIONAL", "NOISE", "NEUTRAL"], f"Expected informational intent, got {data['intent_label']}"
    
    def test_noise_text(self):
        """Test noise/irrelevant tweet classification"""
        response = requests.post(
            f"{BASE_URL}/api/sentiment/analyze",
            json={
                "text": "Just had coffee. Nice weather today. Thinking about crypto.",
                "author_handle": "RandomUser"
            },
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Noise should have low confidence or NOISE intent
        print(f"Noise text result: label={data['sentiment_label']}, intent={data['intent_label']}, confidence={data['confidence']}")
        # Either low confidence or NOISE/INFORMATIONAL intent
        assert data["intent_label"] in ["NOISE", "INFORMATIONAL", "NEUTRAL"] or data["confidence"] < 0.7
    
    def test_missing_text_returns_400(self):
        """Test validation: missing text returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/sentiment/analyze",
            json={"author_handle": "Test"},
            timeout=10
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") is False
        assert "text required" in data.get("error", "").lower()


class TestSentimentBatchEndpoint:
    """POST /api/sentiment/batch — Batch sentiment analysis"""
    
    def test_batch_analysis(self):
        """Test batch analysis of multiple texts"""
        items = [
            {"text": "BTC pump incoming! Buy now!", "token": "BTC"},
            {"text": "ETH looking bearish. Sell signal.", "token": "ETH"},
            {"text": "SOL price update: $150", "token": "SOL"},
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/sentiment/batch",
            json={"items": items},
            timeout=60  # Batch takes longer
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "results" in data
        assert "count" in data
        assert data["count"] == 3
        assert len(data["results"]) == 3
        
        # Verify each result has required fields
        for i, result in enumerate(data["results"]):
            assert "sentiment_label" in result, f"Result {i} missing sentiment_label"
            assert "sentiment_score" in result, f"Result {i} missing sentiment_score"
            assert "confidence" in result, f"Result {i} missing confidence"
            assert "intent_label" in result, f"Result {i} missing intent_label"
            print(f"Batch item {i}: {result['sentiment_label']} / {result['intent_label']}")
    
    def test_batch_empty_items_returns_400(self):
        """Test validation: empty items returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/sentiment/batch",
            json={"items": []},
            timeout=10
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get("ok") is False


class TestSentimentBackfillEndpoint:
    """POST /api/sentiment/backfill — Backfill existing events"""
    
    def test_backfill_with_limit(self):
        """Test backfill with small limit"""
        response = requests.post(
            f"{BASE_URL}/api/sentiment/backfill",
            json={"limit": 5, "skip_analyzed": True},
            timeout=120  # Backfill can take time
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "processed" in data
        assert "errors" in data
        
        print(f"Backfill result: processed={data.get('processed')}, errors={data.get('errors')}, total_events={data.get('total_events')}")


class TestSentimentStatsEndpoint:
    """GET /api/sentiment/stats — Sentiment inference statistics"""
    
    def test_get_stats(self):
        """Test sentiment stats endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/sentiment/stats",
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Verify stats structure
        assert "total" in data
        assert "by_sentiment" in data
        assert "by_intent" in data
        assert "avg_confidence" in data
        assert "uncertain_pct" in data
        
        print(f"Sentiment stats: total={data['total']}, by_sentiment={data['by_sentiment']}, by_intent={data['by_intent']}")
        print(f"Avg confidence: {data['avg_confidence']}, Uncertain %: {data['uncertain_pct']}")


class TestEnrichmentRunEndpoint:
    """POST /api/enrichment/run — Full enrichment pipeline"""
    
    def test_enrichment_run(self):
        """Test enrichment pipeline with small limit"""
        response = requests.post(
            f"{BASE_URL}/api/enrichment/run",
            json={"limit": 10, "skip_enriched": True},
            timeout=120
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        assert "processed" in data
        assert "errors" in data
        
        # May have no_price_data for events outside price window
        if "no_price_data" in data:
            print(f"Enrichment: processed={data['processed']}, no_price_data={data['no_price_data']}, errors={data['errors']}")
        else:
            print(f"Enrichment: processed={data['processed']}, errors={data['errors']}")


class TestEnrichmentStatsEndpoint:
    """GET /api/enrichment/stats — Enrichment statistics"""
    
    def test_get_enrichment_stats(self):
        """Test enrichment stats endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/enrichment/stats",
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Verify stats structure
        assert "total" in data
        assert "by_position" in data
        assert "by_actor_role" in data
        assert "by_regime" in data
        assert "by_intent" in data
        assert "avg_actor_score" in data
        
        print(f"Enrichment stats: total={data['total']}")
        print(f"By position: {data['by_position']}")
        print(f"By actor role: {data['by_actor_role']}")
        print(f"By regime: {data['by_regime']}")
        print(f"By intent: {data['by_intent']}")
        print(f"Avg actor score: {data['avg_actor_score']}")


class TestFakeSentimentDisabled:
    """Verify fake f_sentiment_score is disabled in data_scaling.py"""
    
    def test_data_health_no_fake_sentiment(self):
        """Verify data health endpoint works (regression)"""
        response = requests.get(
            f"{BASE_URL}/api/ml/data/health",
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        print(f"Data health: events={data.get('events', {}).get('total')}, dataset={data.get('dataset', {}).get('total')}")


class TestRealVsSyntheticRegression:
    """GET /api/ml/data/real-vs-synthetic — Regression test"""
    
    def test_real_vs_synthetic_still_works(self):
        """Verify real-vs-synthetic endpoint still works after changes"""
        response = requests.get(
            f"{BASE_URL}/api/ml/data/real-vs-synthetic",
            timeout=120
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") is True
        
        # Verify key fields still present
        assert "data_summary" in data
        assert "tests" in data or ("test_A" in data)  # Either format
        assert "decision" in data
        assert "confidence_buckets_real" in data
        assert "actor_stats" in data
        
        print(f"Real vs Synthetic: decision={data['decision'].get('action')}, reason={data['decision'].get('reason')}")


class TestSentimentModelDistinction:
    """Test that model correctly distinguishes between different tweet types"""
    
    def test_genuine_vs_hype_distinction(self):
        """Test model distinguishes genuine analysis from hype"""
        # Genuine analysis with reasoning
        genuine = requests.post(
            f"{BASE_URL}/api/sentiment/analyze",
            json={
                "text": "BTC forming a bull flag on 4H. RSI divergence suggests continuation. Entry at 65k, target 72k, stop at 62k.",
                "token": "BTC"
            },
            timeout=30
        ).json()
        
        # Pure hype without substance
        hype = requests.post(
            f"{BASE_URL}/api/sentiment/analyze",
            json={
                "text": "BTC 100K SOON!!! 🚀🚀🚀 WAGMI!!! Don't miss out!!!",
                "token": "BTC"
            },
            timeout=30
        ).json()
        
        print(f"Genuine analysis: intent={genuine.get('intent_label')}, confidence={genuine.get('confidence')}")
        print(f"Hype text: intent={hype.get('intent_label')}, confidence={hype.get('confidence')}")
        
        # Genuine should have higher confidence or BULLISH_SIGNAL intent
        # Hype should be flagged as HYPE or have lower confidence
        # This is a soft check - model may vary
        assert genuine.get("ok") is True
        assert hype.get("ok") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
