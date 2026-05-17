"""
Fact Extraction Engine
======================

Uses GPT-4o-mini to extract structured facts from articles.
"""

import logging
import json
import os
from typing import Dict, Any, List, Optional

from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a crypto news analyst. Extract structured facts from this article.

Article Title: {title}
Article Text: {text}

Extract the following in JSON format:
{{
    "event_type": "one of: regulation, funding, listing, delisting, partnership, hack, launch, airdrop, unlock, governance, market_move, legal, news",
    "subject": "main entity/organization doing the action",
    "action": "what action was taken",
    "object": "target of the action (if any)",
    "assets": ["list of crypto assets mentioned"],
    "organizations": ["list of organizations mentioned"],
    "persons": ["list of people mentioned"],
    "amounts": ["any monetary amounts with currency"],
    "dates": ["any specific dates mentioned"],
    "regions": ["geographic regions involved"],
    "key_facts": ["3-5 most important facts from the article"],
    "confidence": 0.0-1.0 (how confident you are in the extraction),
    "is_rumor": true/false (is this confirmed or just a rumor),
    "market_relevance": 0.0-1.0 (how relevant to crypto markets)
}}

Return ONLY valid JSON, no explanation."""


class FactExtractor:
    """Extracts structured facts using LLM."""
    
    def __init__(self):
        self.api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
        self.model = "gpt-4o-mini"
        self.provider = "openai"
    
    async def extract_facts(self, title: str, text: str) -> Optional[Dict[str, Any]]:
        """Extract facts from article text."""
        if not self.api_key:
            logger.error("[FactExtractor] No API key configured")
            return None
        
        try:
            client = AsyncOpenAI(api_key=self.api_key)
            
            prompt = EXTRACTION_PROMPT.format(
                title=title,
                text=text[:3000]  # Limit text length
            )
            
            completion = await client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                max_tokens=1200,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise fact extractor for crypto news. Always return valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            response = (completion.choices[0].message.content or "").strip()
            
            # Parse JSON response
            try:
                # Clean response
                response_text = response
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                facts = json.loads(response_text.strip())
                return facts
                
            except json.JSONDecodeError as e:
                logger.error(f"[FactExtractor] JSON parse error: {e}")
                return None
                
        except Exception as e:
            logger.error(f"[FactExtractor] Error: {e}")
            return None
    
    async def extract_for_event(self, db, event_id: str) -> Dict[str, Any]:
        """Extract facts for all articles in an event."""
        event = await db.news_events.find_one({"id": event_id})
        if not event:
            return {"ok": False, "error": "Event not found"}
        
        all_facts = []
        
        for article_id in event.get("article_ids", [])[:5]:  # Limit to 5 articles
            article = await db.normalized_articles.find_one({"id": article_id})
            if not article:
                continue
            
            facts = await self.extract_facts(
                article.get("title", ""),
                article.get("clean_text", "")
            )
            
            if facts:
                facts["article_id"] = article_id
                facts["source_id"] = article.get("source_id")
                all_facts.append(facts)
        
        if not all_facts:
            return {"ok": False, "error": "No facts extracted"}
        
        # Merge facts
        merged = self._merge_facts(all_facts)
        
        # Update event
        await db.news_events.update_one(
            {"id": event_id},
            {"$set": {
                "extracted_facts": all_facts,
                "event_type": merged.get("event_type", "news"),
                "primary_assets": merged.get("assets", [])[:8],
                "organizations": merged.get("organizations", [])[:8],
                "persons": merged.get("persons", [])[:5],
                "regions": merged.get("regions", [])[:5]
            }}
        )
        
        return {"ok": True, "facts_count": len(all_facts), "merged": merged}
    
    def _merge_facts(self, facts_list: List[Dict]) -> Dict[str, Any]:
        """Merge facts from multiple articles."""
        merged = {
            "event_type": "news",
            "assets": [],
            "organizations": [],
            "persons": [],
            "amounts": [],
            "regions": [],
            "key_facts": [],
            "confidence": 0.0,
            "is_rumor": True
        }
        
        event_types = {}
        
        for facts in facts_list:
            # Count event types
            et = facts.get("event_type", "news")
            event_types[et] = event_types.get(et, 0) + 1
            
            # Merge lists
            merged["assets"].extend(facts.get("assets", []))
            merged["organizations"].extend(facts.get("organizations", []))
            merged["persons"].extend(facts.get("persons", []))
            merged["amounts"].extend(facts.get("amounts", []))
            merged["regions"].extend(facts.get("regions", []))
            merged["key_facts"].extend(facts.get("key_facts", []))
            
            # Average confidence
            merged["confidence"] += facts.get("confidence", 0.5)
            
            # If any source confirms, it's not a rumor
            if not facts.get("is_rumor", True):
                merged["is_rumor"] = False
        
        # Most common event type
        if event_types:
            merged["event_type"] = max(event_types, key=event_types.get)
        
        # Average confidence
        if facts_list:
            merged["confidence"] /= len(facts_list)
        
        # Dedupe lists
        merged["assets"] = list(dict.fromkeys(merged["assets"]))[:10]
        merged["organizations"] = list(dict.fromkeys(merged["organizations"]))[:10]
        merged["persons"] = list(dict.fromkeys(merged["persons"]))[:8]
        merged["amounts"] = list(dict.fromkeys(merged["amounts"]))[:5]
        merged["regions"] = list(dict.fromkeys(merged["regions"]))[:5]
        merged["key_facts"] = list(dict.fromkeys(merged["key_facts"]))[:10]
        
        return merged


class EventFactProcessor:
    """Processes events for fact extraction."""
    
    def __init__(self, db):
        self.db = db
        self.extractor = FactExtractor()
    
    async def process_pending_events(self, limit: int = 10) -> Dict[str, Any]:
        """Process events that need fact extraction."""
        results = {
            "processed": 0,
            "success": 0,
            "errors": 0
        }
        
        # Find events with enough sources but no facts
        cursor = self.db.news_events.find({
            "source_count": {"$gte": 2},
            "extracted_facts": {"$size": 0}
        }).limit(limit)
        
        async for event in cursor:
            results["processed"] += 1
            
            try:
                result = await self.extractor.extract_for_event(self.db, event["id"])
                
                if result.get("ok"):
                    results["success"] += 1
                else:
                    results["errors"] += 1
                    
            except Exception as e:
                results["errors"] += 1
                logger.error(f"[FactProcessor] Error: {e}")
        
        return results
