"""
Multi-Provider Sentiment Engine
================================
Analyzes sentiment using multiple providers in parallel and returns consensus.

Features:
- Parallel analysis from multiple providers (Custom, Emergent, OpenAI)
- Weighted consensus based on provider confidence
- Fallback chain if provider fails
- Comparison metrics

Usage:
    engine = MultiProviderSentiment(db)
    result = await engine.analyze_with_consensus(text)
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MultiProviderSentiment:
    """
    Sentiment analysis using multiple providers with consensus.
    
    Priority order (configurable):
    1. Custom API (your own model)
    2. Emergent (Universal Key)
    3. OpenAI
    4. Internal fallback
    """
    
    def __init__(self, db):
        self.db = db
        self._emergent_key = None
    
    async def get_active_providers(self) -> List[Dict[str, Any]]:
        """Get all active sentiment providers."""
        cursor = self.db.sentiment_keys.find({"enabled": True})
        providers = await cursor.to_list(20)
        return providers
    
    async def get_emergent_key(self) -> Optional[str]:
        """Get Emergent LLM Key from environment."""
        if self._emergent_key:
            return self._emergent_key
        
        import os
        self._emergent_key = os.environ.get("EMERGENT_API_KEY") or os.environ.get("LLM_API_KEY")
        return self._emergent_key
    
    async def analyze_with_provider(
        self, 
        text: str, 
        provider: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze text with a specific provider."""
        provider_type = provider.get("provider")
        api_key = provider.get("api_key")
        endpoint_url = provider.get("endpoint_url")
        
        try:
            if provider_type == "custom":
                return await self._analyze_custom(text, endpoint_url, api_key)
            elif provider_type == "emergent":
                return await self._analyze_emergent(text)
            elif provider_type == "openai":
                return await self._analyze_openai(text, api_key)
            elif provider_type == "anthropic":
                return await self._analyze_anthropic(text, api_key)
            else:
                return await self._analyze_fallback(text)
        except Exception as e:
            logger.error(f"[MultiSentiment] Provider {provider_type} failed: {e}")
            return {
                "provider": provider_type,
                "error": str(e),
                "sentiment": None
            }
    
    async def _analyze_custom(self, text: str, endpoint_url: str, api_key: str) -> Dict[str, Any]:
        """Analyze using custom API."""
        import httpx
        
        if not endpoint_url:
            raise ValueError("Custom provider requires endpoint_url")
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{endpoint_url}/api/v1/sentiment/analyze",
                headers=headers,
                json={"text": text[:2000], "source": "news"},
                timeout=15
            )
            data = response.json()
            
            if data.get("ok") and data.get("data"):
                result_data = data["data"]
                label = result_data.get("label", "NEUTRAL").upper()
                score = result_data.get("score", 0.5)
                
                # Convert score (0-1) to sentiment_score (-1 to 1)
                sentiment_score = (score - 0.5) * 2
                
                return {
                    "provider": "custom",
                    "sentiment": label.lower(),
                    "sentiment_score": sentiment_score,
                    "confidence": result_data.get("meta", {}).get("confidenceScore", 0.7),
                    "raw": result_data
                }
            
            raise ValueError(f"Invalid response: {data}")
    
    async def _analyze_emergent(self, text: str) -> Dict[str, Any]:
        """Analyze using legacy emergent key as OpenAI-compatible key."""
        emergent_key = await self.get_emergent_key()
        
        if not emergent_key:
            raise ValueError("Emergent API key not configured")
        
        try:
            result = await self._analyze_openai(text, emergent_key)
            result["provider"] = "emergent"
            return result
            
        except Exception as e:
            logger.error(f"[MultiSentiment] Emergent failed: {e}")
            raise
    
    async def _analyze_openai(self, text: str, api_key: str) -> Dict[str, Any]:
        """Analyze using OpenAI API directly."""
        import httpx
        
        if not api_key:
            raise ValueError("OpenAI API key required")
        
        prompt = f"""Analyze the sentiment of this crypto news text.
Return JSON: {{"sentiment": "positive"|"negative"|"neutral", "score": -1 to 1, "confidence": 0 to 1}}

Text: {text[:1500]}"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.3
                },
                timeout=30
            )
            data = response.json()
            
            if "choices" in data:
                content = data["choices"][0]["message"]["content"]
                import json
                import re
                
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return {
                        "provider": "openai",
                        "sentiment": result.get("sentiment", "neutral"),
                        "sentiment_score": result.get("score", 0),
                        "confidence": result.get("confidence", 0.8),
                        "raw": result
                    }
            
            raise ValueError(f"Invalid OpenAI response: {data}")
    
    async def _analyze_anthropic(self, text: str, api_key: str) -> Dict[str, Any]:
        """Analyze using Anthropic Claude."""
        import httpx
        
        if not api_key:
            raise ValueError("Anthropic API key required")
        
        prompt = f"""Analyze the sentiment of this crypto news. Return ONLY JSON:
{{"sentiment": "positive"|"negative"|"neutral", "score": -1 to 1, "confidence": 0 to 1}}

Text: {text[:1500]}"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            data = response.json()
            
            if "content" in data:
                content = data["content"][0]["text"]
                import json
                import re
                
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return {
                        "provider": "anthropic",
                        "sentiment": result.get("sentiment", "neutral"),
                        "sentiment_score": result.get("score", 0),
                        "confidence": result.get("confidence", 0.8),
                        "raw": result
                    }
            
            raise ValueError(f"Invalid Anthropic response")
    
    async def _analyze_fallback(self, text: str) -> Dict[str, Any]:
        """Simple keyword-based fallback."""
        text_lower = text.lower()
        
        positive_words = ['surge', 'rally', 'bull', 'gain', 'rise', 'up', 'high', 'growth', 'profit', 'boom', 'soar', 'jump', 'approve', 'bullish', 'breakout']
        negative_words = ['crash', 'dump', 'bear', 'loss', 'fall', 'down', 'low', 'decline', 'drop', 'plunge', 'hack', 'exploit', 'fail', 'bearish', 'collapse']
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        if pos_count > neg_count:
            sentiment = "positive"
            score = min(0.5, pos_count * 0.15)
        elif neg_count > pos_count:
            sentiment = "negative"
            score = max(-0.5, -neg_count * 0.15)
        else:
            sentiment = "neutral"
            score = 0
        
        return {
            "provider": "fallback",
            "sentiment": sentiment,
            "sentiment_score": score,
            "confidence": 0.4,
            "raw": {"pos": pos_count, "neg": neg_count}
        }
    
    async def analyze_with_consensus(
        self, 
        text: str,
        use_providers: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze using multiple providers and return consensus.
        
        Args:
            text: Text to analyze
            use_providers: List of provider types to use, or None for all active
        
        Returns:
            Consensus result with individual provider results
        """
        providers = await self.get_active_providers()
        
        # Filter by requested providers
        if use_providers:
            providers = [p for p in providers if p.get("provider") in use_providers]
        
        # Add Emergent if available and requested
        emergent_key = await self.get_emergent_key()
        if emergent_key and (not use_providers or "emergent" in use_providers):
            # Check if emergent not already in providers
            if not any(p.get("provider") == "emergent" for p in providers):
                providers.append({"provider": "emergent", "api_key": emergent_key})
        
        if not providers:
            # Use fallback
            fallback_result = await self._analyze_fallback(text)
            return {
                "consensus": fallback_result,
                "providers_used": ["fallback"],
                "provider_results": [fallback_result],
                "agreement": 1.0
            }
        
        # Run all providers in parallel
        tasks = [self.analyze_with_provider(text, p) for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        successful_results = []
        for r in results:
            if isinstance(r, dict) and r.get("sentiment") and not r.get("error"):
                successful_results.append(r)
        
        if not successful_results:
            # All failed, use fallback
            fallback_result = await self._analyze_fallback(text)
            return {
                "consensus": fallback_result,
                "providers_used": ["fallback"],
                "provider_results": results,
                "agreement": 1.0,
                "note": "All providers failed, using fallback"
            }
        
        # Calculate consensus
        consensus = self._calculate_consensus(successful_results)
        
        # Calculate agreement score
        agreement = self._calculate_agreement(successful_results)
        
        return {
            "consensus": consensus,
            "providers_used": [r["provider"] for r in successful_results],
            "provider_results": successful_results,
            "agreement": agreement,
            "total_providers": len(successful_results)
        }
    
    def _calculate_consensus(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate weighted consensus from multiple results."""
        if not results:
            return {"sentiment": "neutral", "sentiment_score": 0, "confidence": 0}
        
        # Weight by confidence
        total_weight = sum(r.get("confidence", 0.5) for r in results)
        
        weighted_score = sum(
            r.get("sentiment_score", 0) * r.get("confidence", 0.5) 
            for r in results
        ) / total_weight if total_weight > 0 else 0
        
        # Determine sentiment from weighted score
        if weighted_score > 0.1:
            sentiment = "positive"
        elif weighted_score < -0.1:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        # Average confidence
        avg_confidence = total_weight / len(results)
        
        return {
            "sentiment": sentiment,
            "sentiment_score": round(weighted_score, 3),
            "confidence": round(avg_confidence, 3),
            "method": "weighted_consensus"
        }
    
    def _calculate_agreement(self, results: List[Dict[str, Any]]) -> float:
        """Calculate how much providers agree (0-1)."""
        if len(results) <= 1:
            return 1.0
        
        sentiments = [r.get("sentiment") for r in results]
        
        # Count most common sentiment
        from collections import Counter
        counts = Counter(sentiments)
        most_common_count = counts.most_common(1)[0][1]
        
        return most_common_count / len(results)


# ═══════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════

_multi_sentiment: Optional[MultiProviderSentiment] = None


def get_multi_provider_sentiment(db) -> MultiProviderSentiment:
    """Get or create MultiProviderSentiment singleton."""
    global _multi_sentiment
    if _multi_sentiment is None:
        _multi_sentiment = MultiProviderSentiment(db)
    return _multi_sentiment
