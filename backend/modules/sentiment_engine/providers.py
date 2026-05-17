"""
Sentiment Providers Configuration
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import os


class ProviderType(str, Enum):
    FOMO = "fomo"           # Custom FOMO sentiment
    OPENAI = "openai"       # GPT models
    ANTHROPIC = "anthropic" # Claude models
    GEMINI = "gemini"       # Google Gemini
    

@dataclass
class ProviderConfig:
    """Provider configuration"""
    provider_type: ProviderType
    model: str
    weight: float = 1.0
    enabled: bool = True
    api_key: Optional[str] = None
    

# Default provider configurations
DEFAULT_PROVIDERS = {
    ProviderType.FOMO: ProviderConfig(
        provider_type=ProviderType.FOMO,
        model="fomo-sentiment-v1",
        weight=1.5,  # Higher weight for our custom model
        enabled=True
    ),
    ProviderType.OPENAI: ProviderConfig(
        provider_type=ProviderType.OPENAI,
        model="gpt-4o",
        weight=1.0,
        enabled=True
    ),
    ProviderType.ANTHROPIC: ProviderConfig(
        provider_type=ProviderType.ANTHROPIC,
        model="claude-sonnet-4-5-20250929",
        weight=1.0,
        enabled=False  # Disabled by default
    ),
    ProviderType.GEMINI: ProviderConfig(
        provider_type=ProviderType.GEMINI,
        model="gemini-2.5-flash",
        weight=0.8,
        enabled=False  # Disabled by default
    )
}


class SentimentProvider:
    """Base sentiment provider interface"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.provider_type = config.provider_type
        self.model = config.model
        self.weight = config.weight
        self.enabled = config.enabled
        
    async def analyze(self, text: str, context: Optional[dict] = None) -> dict:
        """
        Analyze text sentiment.
        
        Returns:
            {
                "score": float,        # -1.0 to 1.0
                "confidence": float,   # 0.0 to 1.0
                "label": str,          # "positive", "neutral", "negative"
                "factors": list,       # Key sentiment factors
                "provider": str,       # Provider name
                "model": str           # Model used
            }
        """
        raise NotImplementedError
        
    def is_available(self) -> bool:
        """Check if provider is available"""
        return self.enabled and self._has_credentials()
        
    def _has_credentials(self) -> bool:
        """Check if provider has required credentials"""
        if self.provider_type == ProviderType.FOMO:
            # FOMO uses internal logic, always available if enabled
            return True
        # Other providers need API key (passed via config or from environment)
        return bool(self.config.api_key or os.environ.get('EMERGENT_LLM_KEY') or os.environ.get('OPENAI_API_KEY'))
