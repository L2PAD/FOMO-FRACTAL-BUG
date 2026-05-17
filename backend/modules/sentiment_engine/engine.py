"""
FOMO Multi-Provider Sentiment Engine
=====================================

Core engine for multi-provider sentiment analysis with consensus.
"""

import asyncio
import logging
import os
import json
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from openai import AsyncOpenAI

from .providers import (
    SentimentProvider, 
    ProviderType, 
    ProviderConfig,
    DEFAULT_PROVIDERS
)

logger = logging.getLogger(__name__)


@dataclass
class ProviderResult:
    """Individual provider result"""
    provider: str
    model: str
    score: float           # -1.0 to 1.0
    confidence: float      # 0.0 to 1.0
    label: str             # positive/neutral/negative
    factors: List[str] = field(default_factory=list)
    error: Optional[str] = None
    latency_ms: int = 0


@dataclass
class SentimentResult:
    """Multi-provider sentiment result with consensus"""
    # Consensus (weighted average)
    consensus_score: float
    consensus_confidence: float
    consensus_label: str
    
    # FOMO custom score (0 if not available)
    fomo_score: float
    fomo_confidence: float
    fomo_available: bool
    
    # Individual provider results
    providers: List[ProviderResult]
    
    # Metadata
    providers_used: int
    providers_available: int
    analyzed_at: str
    text_preview: str


class FOMOSentimentProvider(SentimentProvider):
    """
    FOMO Custom Sentiment Provider
    
    Uses rule-based + keyword analysis for crypto-specific sentiment.
    This is our proprietary sentiment model.
    """
    
    # Crypto-specific sentiment keywords
    POSITIVE_KEYWORDS = {
        'high': ['bullish', 'moon', 'pump', 'surge', 'rally', 'breakout', 'ath', 
                 'adoption', 'partnership', 'launch', 'approved', 'etf', 'institutional',
                 'upgrade', 'mainnet', 'integration', 'funding', 'raised'],
        'medium': ['growth', 'gain', 'profit', 'positive', 'strong', 'support',
                   'accumulation', 'buy', 'long', 'hodl', 'recovery']
    }
    
    NEGATIVE_KEYWORDS = {
        'high': ['bearish', 'crash', 'dump', 'plunge', 'hack', 'exploit', 'rug',
                 'scam', 'fraud', 'sec', 'lawsuit', 'ban', 'shutdown', 'bankrupt',
                 'liquidation', 'fud', 'sell-off'],
        'medium': ['decline', 'drop', 'loss', 'weak', 'resistance', 'concern',
                   'risk', 'warning', 'delay', 'postpone', 'uncertainty']
    }
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        
    async def analyze(self, text: str, context: Optional[dict] = None) -> dict:
        """Analyze using FOMO proprietary sentiment model"""
        text_lower = text.lower()
        
        # Calculate sentiment scores
        pos_score = 0
        neg_score = 0
        factors = []
        
        # High impact keywords (weight 2)
        for keyword in self.POSITIVE_KEYWORDS['high']:
            if keyword in text_lower:
                pos_score += 2
                factors.append(f"+{keyword}")
                
        for keyword in self.NEGATIVE_KEYWORDS['high']:
            if keyword in text_lower:
                neg_score += 2
                factors.append(f"-{keyword}")
                
        # Medium impact keywords (weight 1)
        for keyword in self.POSITIVE_KEYWORDS['medium']:
            if keyword in text_lower:
                pos_score += 1
                
        for keyword in self.NEGATIVE_KEYWORDS['medium']:
            if keyword in text_lower:
                neg_score += 1
        
        # Calculate final score (-1 to 1)
        total = pos_score + neg_score
        if total == 0:
            score = 0.0
            confidence = 0.3  # Low confidence for neutral
        else:
            raw_score = (pos_score - neg_score) / max(total, 1)
            score = max(-1.0, min(1.0, raw_score))
            confidence = min(0.95, 0.5 + (total * 0.05))
        
        # Determine label
        if score > 0.15:
            label = "positive"
        elif score < -0.15:
            label = "negative"
        else:
            label = "neutral"
            
        return {
            "score": round(score, 3),
            "confidence": round(confidence, 3),
            "label": label,
            "factors": factors[:5],  # Top 5 factors
            "provider": "fomo",
            "model": self.model
        }


class LLMSentimentProvider(SentimentProvider):
    """
    LLM-based Sentiment Provider
    
    Uses direct provider SDK/API calls.
    """
    
    SYSTEM_PROMPT = """You are a crypto market sentiment analyzer. Analyze the given text and return sentiment in JSON format.

Output format (JSON only, no markdown):
{
    "score": <float from -1.0 (very bearish) to 1.0 (very bullish)>,
    "confidence": <float from 0.0 to 1.0>,
    "label": "<positive|neutral|negative>",
    "factors": ["<key factor 1>", "<key factor 2>", "<key factor 3>"]
}

Guidelines:
- Score > 0.3: positive sentiment (bullish news, adoption, gains)
- Score -0.3 to 0.3: neutral (informational, mixed signals)
- Score < -0.3: negative sentiment (bearish, hacks, regulatory concerns)
- Factors should be 2-4 key phrases that drove the sentiment"""

    def __init__(self, config: ProviderConfig, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        
    async def analyze(self, text: str, context: Optional[dict] = None) -> dict:
        """Analyze using LLM provider"""
        try:
            if self.provider_type != ProviderType.OPENAI:
                raise ValueError(f"Provider not supported without emergent: {self.provider_type.value}")

            client = AsyncOpenAI(api_key=self.api_key)
            completion = await client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze sentiment of this crypto news:\n\n{text[:2000]}"}
                ]
            )
            response = completion.choices[0].message.content or ""
            
            # Parse JSON response
            result = self._parse_response(response)
            result["provider"] = self.provider_type.value
            result["model"] = self.model
            
            return result
            
        except Exception as e:
            logger.error(f"[{self.provider_type}] Sentiment analysis failed: {e}")
            return {
                "score": 0.0,
                "confidence": 0.0,
                "label": "neutral",
                "factors": [],
                "provider": self.provider_type.value,
                "model": self.model,
                "error": str(e)
            }
    
    def _parse_response(self, response: str) -> dict:
        """Parse LLM response to extract sentiment data"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "score": float(data.get("score", 0)),
                    "confidence": float(data.get("confidence", 0.5)),
                    "label": data.get("label", "neutral"),
                    "factors": data.get("factors", [])[:5]
                }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            
        # Fallback: try to infer from text
        response_lower = response.lower()
        if any(word in response_lower for word in ['positive', 'bullish', 'optimistic']):
            return {"score": 0.5, "confidence": 0.5, "label": "positive", "factors": []}
        elif any(word in response_lower for word in ['negative', 'bearish', 'pessimistic']):
            return {"score": -0.5, "confidence": 0.5, "label": "negative", "factors": []}
        
        return {"score": 0.0, "confidence": 0.3, "label": "neutral", "factors": []}


class SentimentEngine:
    """
    Multi-Provider Sentiment Engine with Consensus
    
    Features:
    - Parallel analysis from multiple providers
    - Weighted consensus calculation
    - FOMO custom score always displayed (0 if unavailable)
    - Individual provider breakdowns
    """
    
    def __init__(self, db=None):
        self.db = db
        self.providers: Dict[ProviderType, SentimentProvider] = {}
        self._api_key_cache = None
        self._initialize_providers()
        
    async def _get_api_key(self) -> Optional[str]:
        """Get API key from llm_keys (primary) or sentiment_keys collection or environment."""
        if self._api_key_cache:
            return self._api_key_cache
            
        # Try to get from llm_keys collection FIRST (more reliable)
        if self.db is not None:
            try:
                # Priority 1: llm_keys with sentiment capability
                key_doc = await self.db.llm_keys.find_one({
                    "enabled": True,
                    "healthy": True,
                    "capabilities": "sentiment"
                })
                if key_doc and key_doc.get("api_key"):
                    self._api_key_cache = key_doc["api_key"]
                    logger.info(f"[SentimentEngine] Using key from llm_keys: {key_doc.get('name')}")
                    return self._api_key_cache
                
                # Priority 2: sentiment_keys collection
                key_doc = await self.db.sentiment_keys.find_one({
                    "enabled": True,
                    "provider": "openai"
                })
                if key_doc and key_doc.get("api_key"):
                    self._api_key_cache = key_doc["api_key"]
                    logger.info(f"[SentimentEngine] Using key from sentiment_keys: {key_doc.get('name')}")
                    return self._api_key_cache
            except Exception as e:
                logger.warning(f"[SentimentEngine] Failed to get key from DB: {e}")
        
        # Fallback to environment
        self._api_key_cache = os.environ.get('EMERGENT_LLM_KEY') or os.environ.get('OPENAI_API_KEY')
        return self._api_key_cache
        
    def _initialize_providers(self):
        """Initialize all configured providers"""
        # Always add FOMO provider
        fomo_config = DEFAULT_PROVIDERS[ProviderType.FOMO]
        self.providers[ProviderType.FOMO] = FOMOSentimentProvider(fomo_config)
        logger.info(f"[SentimentEngine] Initialized FOMO provider")
        
    async def initialize_llm_providers(self):
        """Initialize LLM providers with API key from database."""
        api_key = await self._get_api_key()
        if api_key:
            for provider_type in [ProviderType.OPENAI]:
                config = DEFAULT_PROVIDERS[provider_type]
                if config.enabled:
                    # Set API key in config so is_available() works
                    config.api_key = api_key
                    self.providers[provider_type] = LLMSentimentProvider(config, api_key)
                    logger.info(f"[SentimentEngine] Initialized {provider_type.value} provider with DB key")
                    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return [p.provider_type.value for p in self.providers.values() if p.is_available()]
    
    async def enable_provider(self, provider_type: ProviderType, enabled: bool = True):
        """Enable/disable a provider"""
        if provider_type in self.providers:
            self.providers[provider_type].enabled = enabled
            
        # Add provider if not exists and enabling
        api_key = await self._get_api_key()
        if enabled and provider_type not in self.providers and api_key:
            config = DEFAULT_PROVIDERS.get(provider_type)
            if config:
                config.enabled = True
                if provider_type == ProviderType.FOMO:
                    self.providers[provider_type] = FOMOSentimentProvider(config)
                else:
                    self.providers[provider_type] = LLMSentimentProvider(config, api_key)
                    
    async def analyze(self, text: str, context: Optional[dict] = None) -> SentimentResult:
        """
        Analyze text with all available providers.
        
        Returns:
            SentimentResult with consensus and individual scores
        """
        # Initialize LLM providers if not done yet
        if ProviderType.OPENAI not in self.providers:
            await self.initialize_llm_providers()
            
        start_time = datetime.now(timezone.utc)
        provider_results: List[ProviderResult] = []
        
        # Get available providers
        available = [p for p in self.providers.values() if p.is_available()]
        
        # Run analysis in parallel
        async def run_provider(provider: SentimentProvider) -> ProviderResult:
            t0 = datetime.now(timezone.utc)
            try:
                result = await provider.analyze(text, context)
                latency = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
                return ProviderResult(
                    provider=result.get("provider", provider.provider_type.value),
                    model=result.get("model", provider.model),
                    score=result.get("score", 0.0),
                    confidence=result.get("confidence", 0.0),
                    label=result.get("label", "neutral"),
                    factors=result.get("factors", []),
                    error=result.get("error"),
                    latency_ms=latency
                )
            except Exception as e:
                logger.error(f"Provider {provider.provider_type} failed: {e}")
                return ProviderResult(
                    provider=provider.provider_type.value,
                    model=provider.model,
                    score=0.0,
                    confidence=0.0,
                    label="neutral",
                    error=str(e),
                    latency_ms=0
                )
        
        # Execute all providers in parallel
        if available:
            tasks = [run_provider(p) for p in available]
            provider_results = await asyncio.gather(*tasks)
        
        # Calculate consensus (weighted average)
        consensus_score, consensus_confidence = self._calculate_consensus(provider_results)
        
        # Get FOMO result
        fomo_result = next((r for r in provider_results if r.provider == "fomo"), None)
        fomo_score = fomo_result.score if fomo_result else 0.0
        fomo_confidence = fomo_result.confidence if fomo_result else 0.0
        fomo_available = fomo_result is not None and fomo_result.error is None
        
        # Determine consensus label
        if consensus_score > 0.15:
            consensus_label = "positive"
        elif consensus_score < -0.15:
            consensus_label = "negative"
        else:
            consensus_label = "neutral"
            
        return SentimentResult(
            consensus_score=round(consensus_score, 3),
            consensus_confidence=round(consensus_confidence, 3),
            consensus_label=consensus_label,
            fomo_score=round(fomo_score, 3),
            fomo_confidence=round(fomo_confidence, 3),
            fomo_available=fomo_available,
            providers=provider_results,
            providers_used=len([r for r in provider_results if not r.error]),
            providers_available=len(self.providers),
            analyzed_at=start_time.isoformat(),
            text_preview=text[:100] + "..." if len(text) > 100 else text
        )
    
    def _calculate_consensus(self, results: List[ProviderResult]) -> tuple:
        """
        Calculate weighted consensus from all provider results.
        
        Formula: 
            consensus_score = sum(score * weight * confidence) / sum(weight * confidence)
            consensus_confidence = avg(confidence) * (1 + 0.1 * agreement_bonus)
        """
        valid_results = [r for r in results if not r.error and r.confidence > 0]
        
        if not valid_results:
            return 0.0, 0.0
            
        # Get weights from config
        weights = {}
        for pt, config in DEFAULT_PROVIDERS.items():
            weights[pt.value] = config.weight
            
        # Weighted average score
        total_weight = 0
        weighted_sum = 0
        
        for r in valid_results:
            w = weights.get(r.provider, 1.0) * r.confidence
            weighted_sum += r.score * w
            total_weight += w
            
        if total_weight == 0:
            return 0.0, 0.0
            
        consensus_score = weighted_sum / total_weight
        
        # Average confidence with agreement bonus
        avg_confidence = sum(r.confidence for r in valid_results) / len(valid_results)
        
        # Agreement bonus: if all providers agree on direction
        signs = [1 if r.score > 0.1 else (-1 if r.score < -0.1 else 0) for r in valid_results]
        if signs and all(s == signs[0] for s in signs) and signs[0] != 0:
            agreement_bonus = 0.15
        else:
            agreement_bonus = 0
            
        consensus_confidence = min(0.99, avg_confidence + agreement_bonus)
        
        return consensus_score, consensus_confidence
    
    async def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze multiple texts"""
        tasks = [self.analyze(text) for text in texts]
        return await asyncio.gather(*tasks)
    
    def get_status(self) -> dict:
        """Get engine status"""
        return {
            "providers_configured": len(self.providers),
            "providers_available": len(self.get_available_providers()),
            "providers": {
                pt.value: {
                    "model": p.model,
                    "weight": p.weight,
                    "enabled": p.enabled,
                    "available": p.is_available()
                }
                for pt, p in self.providers.items()
            },
            "has_api_key": bool(self._api_key_cache),
            "fomo_enabled": ProviderType.FOMO in self.providers
        }
