"""
Article Normalizer
==================

Cleans and normalizes raw articles for processing.
"""

import re
import hashlib
import logging
from typing import Optional, List
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from ..models import RawArticle, NormalizedArticle

logger = logging.getLogger(__name__)

# Known crypto assets for quick detection
KNOWN_ASSETS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "AVAX", "MATIC",
    "LINK", "UNI", "ATOM", "LTC", "TRX", "USDT", "USDC", "DAI", "ARB", "OP",
    "NEAR", "APT", "SUI", "AAVE", "CRV", "MKR", "SNX", "COMP", "FTM", "ALGO",
    "TON", "PEPE", "SHIB", "BONK", "WIF", "FLOKI", "INJ", "TIA", "SEI", "STRK",
    "EIGEN", "ZRO", "ZK", "BLAST", "MODE", "MANTA", "DYM", "JUP", "W", "ETHFI",
    "Bitcoin", "Ethereum", "Solana", "Cardano", "Polkadot", "Avalanche", "Polygon"
}

# Known organizations
KNOWN_ORGS = {
    "SEC", "CFTC", "Fed", "Federal Reserve", "Treasury", "Congress", "Senate",
    "BlackRock", "Fidelity", "Grayscale", "ARK", "VanEck", "Invesco", "Franklin",
    "Binance", "Coinbase", "Kraken", "OKX", "Bybit", "Bitfinex", "Gemini", "Bitstamp",
    "a16z", "Paradigm", "Polychain", "Multicoin", "Pantera", "Galaxy", "DCG",
    "Circle", "Tether", "MakerDAO", "Uniswap", "Aave", "Compound", "Lido",
    "OpenAI", "Anthropic", "Google", "Microsoft", "Apple", "Meta", "Amazon",
    "JPMorgan", "Goldman", "Morgan Stanley", "Bank of America", "Citi",
}

# Event action verbs
EVENT_VERBS = [
    "launch", "announce", "release", "approve", "reject", "delay", "investigate",
    "list", "delist", "hack", "exploit", "raise", "invest", "acquire", "partner",
    "integrate", "upgrade", "fork", "airdrop", "unlock", "burn", "mint", "stake",
    "ban", "regulate", "legalize", "sue", "settle", "fine", "arrest",
]


class ArticleNormalizer:
    """Normalizes raw articles."""
    
    def __init__(self, db):
        self.db = db
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        
        # Remove HTML tags
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _extract_assets(self, text: str) -> List[str]:
        """Extract crypto asset mentions."""
        found = []
        text_upper = text.upper()
        
        for asset in KNOWN_ASSETS:
            if asset.upper() in text_upper:
                # Normalize to ticker
                normalized = asset.upper()
                if normalized == "BITCOIN":
                    normalized = "BTC"
                elif normalized == "ETHEREUM":
                    normalized = "ETH"
                elif normalized == "SOLANA":
                    normalized = "SOL"
                elif normalized == "CARDANO":
                    normalized = "ADA"
                elif normalized == "POLKADOT":
                    normalized = "DOT"
                elif normalized == "AVALANCHE":
                    normalized = "AVAX"
                elif normalized == "POLYGON":
                    normalized = "MATIC"
                
                if normalized not in found:
                    found.append(normalized)
        
        return found[:10]
    
    def _extract_organizations(self, text: str) -> List[str]:
        """Extract organization mentions."""
        found = []
        
        for org in KNOWN_ORGS:
            if org.lower() in text.lower():
                if org not in found:
                    found.append(org)
        
        return found[:10]
    
    def _extract_event_hints(self, text: str) -> List[str]:
        """Extract event type hints from text."""
        hints = []
        text_lower = text.lower()
        
        for verb in EVENT_VERBS:
            if verb in text_lower:
                hints.append(verb)
        
        return hints[:5]
    
    def _extract_amounts(self, text: str) -> List[str]:
        """Extract monetary amounts."""
        amounts = []
        
        # Pattern for amounts like $100M, $1.5B, $50 million
        patterns = [
            r'\$[\d,]+\.?\d*\s*(?:million|billion|M|B|K)?',
            r'[\d,]+\.?\d*\s*(?:million|billion)\s*(?:dollars|USD)?',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            amounts.extend(matches)
        
        return amounts[:5]
    
    def _extract_regions(self, text: str) -> List[str]:
        """Extract geographic regions."""
        regions = []
        
        region_keywords = {
            "US": ["United States", "U.S.", "USA", "American", "Washington", "SEC", "CFTC"],
            "EU": ["European Union", "Europe", "EU", "ECB", "MiCA"],
            "UK": ["United Kingdom", "UK", "Britain", "FCA"],
            "China": ["China", "Chinese", "Beijing", "Hong Kong", "HK"],
            "Japan": ["Japan", "Japanese", "FSA Japan"],
            "Korea": ["South Korea", "Korean"],
            "Singapore": ["Singapore", "MAS"],
            "UAE": ["UAE", "Dubai", "Abu Dhabi"],
        }
        
        text_lower = text.lower()
        for region, keywords in region_keywords.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    if region not in regions:
                        regions.append(region)
                    break
        
        return regions
    
    def _generate_summary(self, title: str, content: str) -> str:
        """Generate simple summary from content."""
        if not content:
            return title
        
        # Take first 2 sentences or 300 chars
        sentences = content.split('.')
        summary = '. '.join(sentences[:2])
        
        if len(summary) > 300:
            summary = summary[:297] + "..."
        
        return summary
    
    def _generate_content_hash(self, title: str, content: str) -> str:
        """Generate content hash for dedup."""
        text = f"{title.lower()}:{content[:500].lower() if content else ''}"
        return hashlib.md5(text.encode()).hexdigest()
    
    async def normalize_article(self, raw: RawArticle) -> Optional[NormalizedArticle]:
        """Normalize a raw article."""
        try:
            now = datetime.now(timezone.utc)
            
            # Clean content
            clean_text = self._clean_text(raw.content_raw or "")
            title = self._clean_text(raw.title_raw)
            
            if not title:
                return None
            
            # Parse published date
            published_at = None
            if raw.published_at_raw:
                try:
                    # Try ISO format
                    published_at = datetime.fromisoformat(
                        raw.published_at_raw.replace('Z', '+00:00')
                    )
                except:
                    pass
            
            # Extract entities
            full_text = f"{title} {clean_text}"
            assets = self._extract_assets(full_text)
            organizations = self._extract_organizations(full_text)
            event_hints = self._extract_event_hints(full_text)
            amounts = self._extract_amounts(full_text)
            regions = self._extract_regions(full_text)
            
            # Generate summary
            summary = self._generate_summary(title, clean_text)
            
            normalized = NormalizedArticle(
                id=f"norm_{raw.id}",
                raw_article_id=raw.id,
                source_id=raw.source_id,
                source_name=raw.source_name,
                canonical_url=raw.url,
                title=title,
                clean_text=clean_text,
                summary=summary,
                language=raw.language_detected,
                published_at=published_at,
                author=raw.author_raw,
                image_url=raw.image_url_raw,
                tags=raw.tags_raw,
                entities=assets + organizations,
                assets=assets,
                organizations=organizations,
                persons=[],  # TODO: NER for persons
                regions=regions,
                amounts=amounts,
                event_hints=event_hints,
                embedding=None,  # Set later by embedding module
                content_hash=self._generate_content_hash(title, clean_text),
                created_at=now,
                is_duplicate=False,
                duplicate_of=None
            )
            
            return normalized
            
        except Exception as e:
            logger.error(f"[Normalizer] Error normalizing article {raw.id}: {e}")
            return None
    
    async def process_pending_articles(self, limit: int = 100) -> dict:
        """Process pending raw articles."""
        results = {
            "processed": 0,
            "normalized": 0,
            "duplicates": 0,
            "errors": 0
        }
        
        cursor = self.db.raw_articles.find({"status": "pending"}).limit(limit)
        
        async for raw_doc in cursor:
            results["processed"] += 1
            
            try:
                raw = RawArticle(**raw_doc)
                
                # Check for duplicate by content hash
                existing = await self.db.normalized_articles.find_one({
                    "content_hash": raw.content_hash
                })
                
                if existing:
                    results["duplicates"] += 1
                    await self.db.raw_articles.update_one(
                        {"id": raw.id},
                        {"$set": {"status": "duplicate"}}
                    )
                    continue
                
                # Normalize
                normalized = await self.normalize_article(raw)
                
                if normalized:
                    await self.db.normalized_articles.insert_one(normalized.model_dump())
                    results["normalized"] += 1
                    
                    await self.db.raw_articles.update_one(
                        {"id": raw.id},
                        {"$set": {"status": "processed"}}
                    )
                else:
                    results["errors"] += 1
                    await self.db.raw_articles.update_one(
                        {"id": raw.id},
                        {"$set": {"status": "error"}}
                    )
                    
            except Exception as e:
                results["errors"] += 1
                logger.error(f"[Normalizer] Error processing article: {e}")
        
        return results
