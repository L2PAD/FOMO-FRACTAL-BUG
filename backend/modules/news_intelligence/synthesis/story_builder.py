"""
Story Synthesis Engine
======================

Uses GPT-5.2 to generate FOMO news stories from events.
Includes caching for intermediate results to avoid redundant LLM calls.
"""

import logging
import os
import hashlib
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# GENERATION CACHE
# ═══════════════════════════════════════════════════════════════

class GenerationCache:
    """
    Cache for intermediate story generation results.
    Stores in MongoDB for persistence across restarts.
    """
    
    def __init__(self, db=None):
        self.db = db
        self.collection_name = "generation_cache"
        self._memory_cache = {}  # In-memory fallback
    
    def _generate_key(self, event_id: str, component: str, language: str) -> str:
        """Generate unique cache key."""
        return f"{event_id}_{component}_{language}"
    
    def _hash_content(self, content: str) -> str:
        """Generate hash of content for change detection."""
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    async def get(self, event_id: str, component: str, language: str = "en") -> Optional[str]:
        """
        Get cached component if exists.
        Components: headline, summary, story, ai_view
        """
        key = self._generate_key(event_id, component, language)
        
        # Check memory cache first
        if key in self._memory_cache:
            logger.debug(f"[Cache] Memory hit: {key}")
            return self._memory_cache[key].get("content")
        
        # Check MongoDB
        if self.db is not None:
            try:
                cached = await self.db[self.collection_name].find_one({"key": key})
                if cached and cached.get("content"):
                    # Store in memory for faster subsequent access
                    self._memory_cache[key] = cached
                    logger.info(f"[Cache] DB hit: {component}/{language} for {event_id[:20]}")
                    return cached["content"]
            except Exception as e:
                logger.error(f"[Cache] DB read error: {e}")
        
        return None
    
    async def set(self, event_id: str, component: str, language: str, content: str, 
                  metadata: Dict = None) -> bool:
        """
        Cache a generated component.
        """
        if not content:
            return False
        
        key = self._generate_key(event_id, component, language)
        now = datetime.now(timezone.utc)
        
        cache_entry = {
            "key": key,
            "event_id": event_id,
            "component": component,
            "language": language,
            "content": content,
            "content_hash": self._hash_content(content),
            "char_count": len(content),
            "created_at": now.isoformat(),
            "metadata": metadata or {}
        }
        
        # Store in memory
        self._memory_cache[key] = cache_entry
        
        # Store in MongoDB
        if self.db is not None:
            try:
                await self.db[self.collection_name].update_one(
                    {"key": key},
                    {"$set": cache_entry},
                    upsert=True
                )
                logger.info(f"[Cache] Stored: {component}/{language} ({len(content)} chars)")
                return True
            except Exception as e:
                logger.error(f"[Cache] DB write error: {e}")
        
        return True  # Memory cache succeeded
    
    async def get_event_cache(self, event_id: str) -> Dict[str, str]:
        """Get all cached components for an event."""
        result = {}
        
        if self.db is not None:
            try:
                cursor = self.db[self.collection_name].find({"event_id": event_id})
                async for doc in cursor:
                    component = doc.get("component", "")
                    language = doc.get("language", "en")
                    field_name = f"{component}_{language}" if language != "en" else component
                    result[field_name] = doc.get("content", "")
            except Exception as e:
                logger.error(f"[Cache] Get event cache error: {e}")
        
        return result
    
    async def invalidate(self, event_id: str, component: str = None):
        """Invalidate cache for event (all components or specific one)."""
        if self.db is not None:
            try:
                query = {"event_id": event_id}
                if component:
                    query["component"] = component
                
                await self.db[self.collection_name].delete_many(query)
                
                # Clear memory cache
                keys_to_remove = [k for k in self._memory_cache if k.startswith(event_id)]
                for k in keys_to_remove:
                    del self._memory_cache[k]
                
                logger.info(f"[Cache] Invalidated: {event_id[:20]} / {component or 'all'}")
            except Exception as e:
                logger.error(f"[Cache] Invalidate error: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "memory_entries": len(self._memory_cache),
            "db_entries": 0,
            "total_chars_cached": 0
        }
        
        if self.db is not None:
            try:
                stats["db_entries"] = await self.db[self.collection_name].count_documents({})
                pipeline = [
                    {"$group": {"_id": None, "total": {"$sum": "$char_count"}}}
                ]
                async for doc in self.db[self.collection_name].aggregate(pipeline):
                    stats["total_chars_cached"] = doc.get("total", 0)
            except Exception as e:
                logger.error(f"[Cache] Stats error: {e}")
        
        return stats


# ═══════════════════════════════════════════════════════════════
# STORY GENERATION PROMPTS
# ═══════════════════════════════════════════════════════════════

HEADLINE_PROMPT = """Generate a compelling, professional headline for this crypto news event.

Event Type: {event_type}
Original Title: {title_seed}
Assets: {assets}
Organizations: {organizations}
Key Facts: {key_facts}

Requirements:
- Maximum 80 characters
- Professional, factual tone
- No sensationalism
- Include main asset/org if relevant
- Write in {language} language

Return ONLY the headline text, nothing else."""


SUMMARY_PROMPT = """Write a concise 2-3 sentence summary for this crypto news event.

Event Type: {event_type}
Headline: {headline}
Sources: {source_count} sources confirmed
Key Facts:
{key_facts}

Requirements:
- Be factual and precise
- Mention key entities involved
- Include numbers/amounts if available
- Maximum 280 characters
- Write in {language} language

Return ONLY the summary text, nothing else."""


STORY_PROMPT = """Write a comprehensive crypto news article for FOMO platform.

Event Type: {event_type}
Headline: {headline}
Summary: {summary}
Assets Involved: {assets}
Organizations: {organizations}
Persons: {persons}
Key Facts:
{key_facts}

Source Articles Context:
{source_context}

Requirements:
1. Write in {language} language
2. Professional, analytical, and engaging tone
3. Write 6-8 substantial paragraphs (approximately 3000-4000 characters total)
4. Structure:
   - Opening paragraph: Catchy lead with the main news hook
   - Paragraph 2: Detailed explanation of what happened with specific numbers
   - Paragraph 3: Who is involved (key organizations, people)
   - Paragraph 4: Background context and history relevant to this event
   - Paragraph 5: Market implications and expert analysis
   - Paragraph 6: Technical details (if applicable) or regulatory context
   - Paragraph 7-8: Future outlook and what to watch next
5. Include:
   - Specific numbers, amounts, percentages
   - Direct implications for traders and investors
   - Comparison with similar past events if relevant
6. No speculation - only confirmed facts
7. No references to source names (rewrite in your own words)
8. Each paragraph should be 3-5 sentences long

Return ONLY the article text, nothing else."""


AI_VIEW_PROMPT = """As FOMO AI analyst, provide a brief market insight on this event.

Event: {headline}
Summary: {summary}
Assets: {assets}
Event Type: {event_type}

Write 2-3 sentences of analysis:
- What this means for the market
- Potential impact on mentioned assets
- Risk level (if applicable)

Requirements:
- Be analytical, not promotional
- {language} language
- Start with "FOMO AI View:"
- Maximum 200 characters

Return ONLY the insight text."""


class StorySynthesizer:
    """Synthesizes news stories using LLM with caching support."""
    
    def __init__(self, db=None):
        self.model = "gpt-4o"  # Default model
        self.provider = "openai"
        self.cache = GenerationCache(db)
        self.db = db
        self._api_key = None  # Will be fetched from DB
    
    async def _get_api_key(self) -> Optional[str]:
        """Get API key from LLM keys collection or environment."""
        # Try to get from LLM keys in database
        if self.db is not None:
            try:
                key_doc = await self.db.llm_keys.find_one({
                    "enabled": True,
                    "healthy": True,
                    "capabilities": "text"
                })
                if key_doc and key_doc.get("api_key"):
                    self._api_key = key_doc["api_key"]
                    logger.info(f"[StorySynthesizer] Using LLM key from DB: {key_doc.get('name')}")
                    return self._api_key
            except Exception as e:
                logger.warning(f"[StorySynthesizer] Failed to get key from DB: {e}")
        
        # Fallback to environment
        self._api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
        if self._api_key:
            logger.info("[StorySynthesizer] Using API key from environment")
        return self._api_key
    
    async def _call_llm(self, prompt: str, session_suffix: str, max_tokens: int = 2000) -> Optional[str]:
        """Make LLM call with optimized settings."""
        api_key = await self._get_api_key()
        if not api_key:
            logger.error("[StorySynthesizer] No API key configured")
            return None
        
        try:
            client = AsyncOpenAI(api_key=api_key)
            completion = await client.chat.completions.create(
                model=self.model,
                temperature=0.4,
                max_tokens=max_tokens,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional crypto news writer for FOMO platform. Write clear, factual, and engaging content. Be concise and direct."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            response = completion.choices[0].message.content or ""
            return response.strip() or None
            
        except Exception as e:
            logger.error(f"[StorySynthesizer] LLM error: {e}")
            return None
    
    async def generate_full_story_parallel(self, event: Dict, use_cache: bool = True) -> Dict[str, str]:
        """
        Generate complete story in BOTH languages in parallel for faster execution.
        Uses caching to skip already generated components.
        Returns dict with all story components.
        """
        import asyncio
        
        event_id = event.get("id", "unknown")
        title_seed = event.get("title_seed", "")
        
        result = {
            "title_en": None, "title_ru": None,
            "summary_en": None, "summary_ru": None,
            "story_en": None, "story_ru": None,
            "ai_view_en": None, "ai_view_ru": None,
            "ai_view": None,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Check cache for existing components
        if use_cache:
            cached_headline_en = await self.cache.get(event_id, "headline", "en")
            cached_headline_ru = await self.cache.get(event_id, "headline", "ru")
            cached_summary_en = await self.cache.get(event_id, "summary", "en")
            cached_summary_ru = await self.cache.get(event_id, "summary", "ru")
            cached_story_en = await self.cache.get(event_id, "story", "en")
            cached_story_ru = await self.cache.get(event_id, "story", "ru")
            cached_ai_view_en = await self.cache.get(event_id, "ai_view", "en")
            cached_ai_view_ru = await self.cache.get(event_id, "ai_view", "ru")
        else:
            cached_headline_en = cached_headline_ru = None
            cached_summary_en = cached_summary_ru = None
            cached_story_en = cached_story_ru = None
            cached_ai_view_en = cached_ai_view_ru = None
        
        # Generate headlines (use cache if available)
        if cached_headline_en:
            headline_en = cached_headline_en
            result["cache_hits"] += 1
        else:
            headline_en = await self.generate_headline(event, "English")
            headline_en = headline_en or title_seed
            await self.cache.set(event_id, "headline", "en", headline_en)
            result["cache_misses"] += 1
        
        if cached_headline_ru:
            headline_ru = cached_headline_ru
            result["cache_hits"] += 1
        else:
            headline_ru = await self.generate_headline(event, "Russian")
            headline_ru = headline_ru or headline_en
            await self.cache.set(event_id, "headline", "ru", headline_ru)
            result["cache_misses"] += 1
        
        result["title_en"] = headline_en
        result["title_ru"] = headline_ru
        
        # Generate summaries in parallel (use cache if available)
        tasks_summary = []
        if not cached_summary_en:
            tasks_summary.append(("en", self.generate_summary(event, headline_en, "English")))
        if not cached_summary_ru:
            tasks_summary.append(("ru", self.generate_summary(event, headline_ru, "Russian")))
        
        if tasks_summary:
            summary_results = await asyncio.gather(*[t[1] for t in tasks_summary])
            for i, (lang, _) in enumerate(tasks_summary):
                if lang == "en":
                    summary_en = summary_results[i] or headline_en
                    await self.cache.set(event_id, "summary", "en", summary_en)
                    result["cache_misses"] += 1
                else:
                    summary_ru = summary_results[i] or summary_en
                    await self.cache.set(event_id, "summary", "ru", summary_ru)
                    result["cache_misses"] += 1
        
        if cached_summary_en:
            summary_en = cached_summary_en
            result["cache_hits"] += 1
        if cached_summary_ru:
            summary_ru = cached_summary_ru
            result["cache_hits"] += 1
        
        # Ensure summaries are set
        summary_en = cached_summary_en or summary_en if 'summary_en' in dir() else headline_en
        summary_ru = cached_summary_ru or summary_ru if 'summary_ru' in dir() else summary_en
        
        result["summary_en"] = summary_en
        result["summary_ru"] = summary_ru
        
        # Generate stories and AI views in parallel (use cache if available)
        tasks_content = []
        if not cached_story_en:
            tasks_content.append(("story_en", self.generate_story(event, headline_en, summary_en, "", "English")))
        if not cached_story_ru:
            tasks_content.append(("story_ru", self.generate_story(event, headline_ru, summary_ru, "", "Russian")))
        if not cached_ai_view_en:
            tasks_content.append(("ai_view_en", self.generate_ai_view(event, headline_en, summary_en, "English")))
        if not cached_ai_view_ru:
            tasks_content.append(("ai_view_ru", self.generate_ai_view(event, headline_ru, summary_ru, "Russian")))
        
        if tasks_content:
            content_results = await asyncio.gather(*[t[1] for t in tasks_content])
            for i, (key, _) in enumerate(tasks_content):
                content = content_results[i] or ""
                if key == "story_en":
                    await self.cache.set(event_id, "story", "en", content)
                elif key == "story_ru":
                    await self.cache.set(event_id, "story", "ru", content)
                elif key == "ai_view_en":
                    await self.cache.set(event_id, "ai_view", "en", content)
                elif key == "ai_view_ru":
                    await self.cache.set(event_id, "ai_view", "ru", content)
                result[key] = content
                result["cache_misses"] += 1
        
        # Apply cached values
        if cached_story_en:
            result["story_en"] = cached_story_en
            result["cache_hits"] += 1
        if cached_story_ru:
            result["story_ru"] = cached_story_ru
            result["cache_hits"] += 1
        if cached_ai_view_en:
            result["ai_view_en"] = cached_ai_view_en
            result["cache_hits"] += 1
        if cached_ai_view_ru:
            result["ai_view_ru"] = cached_ai_view_ru
            result["cache_hits"] += 1
        
        result["ai_view"] = result["ai_view_en"] or ""
        
        logger.info(f"[StorySynthesizer] Generated for {event_id[:20]}: "
                   f"cache hits={result['cache_hits']}, misses={result['cache_misses']}")
        
        return result
    
    async def generate_headline(self, event: Dict, language: str = "English") -> Optional[str]:
        """Generate headline for event."""
        prompt = HEADLINE_PROMPT.format(
            event_type=event.get("event_type", "news"),
            title_seed=event.get("title_seed", ""),
            assets=", ".join(event.get("primary_assets", [])[:5]),
            organizations=", ".join(event.get("organizations", [])[:3]),
            key_facts=self._format_facts(event),
            language=language
        )
        
        return await self._call_llm(prompt, f"headline_{language}_{event.get('id', '')}")
    
    async def generate_summary(self, event: Dict, headline: str, language: str = "English") -> Optional[str]:
        """Generate summary for event."""
        prompt = SUMMARY_PROMPT.format(
            event_type=event.get("event_type", "news"),
            headline=headline,
            source_count=event.get("source_count", 1),
            key_facts=self._format_facts(event),
            language=language
        )
        
        return await self._call_llm(prompt, f"summary_{language}_{event.get('id', '')}")
    
    async def generate_story(self, event: Dict, headline: str, summary: str, 
                            source_context: str, language: str = "English") -> Optional[str]:
        """Generate full story for event."""
        prompt = STORY_PROMPT.format(
            event_type=event.get("event_type", "news"),
            headline=headline,
            summary=summary,
            assets=", ".join(event.get("primary_assets", [])[:5]),
            organizations=", ".join(event.get("organizations", [])[:5]),
            persons=", ".join(event.get("persons", [])[:3]),
            key_facts=self._format_facts(event),
            source_context=source_context[:2000],
            language=language
        )
        
        return await self._call_llm(prompt, f"story_{event.get('id', '')}")
    
    async def generate_ai_view(self, event: Dict, headline: str, 
                               summary: str, language: str = "English") -> Optional[str]:
        """Generate AI market insight."""
        prompt = AI_VIEW_PROMPT.format(
            headline=headline,
            summary=summary,
            assets=", ".join(event.get("primary_assets", [])[:3]),
            event_type=event.get("event_type", "news"),
            language=language
        )
        
        return await self._call_llm(prompt, f"aiview_{event.get('id', '')}")
    
    def _format_facts(self, event: Dict) -> str:
        """Format facts for prompt."""
        facts = event.get("extracted_facts", [])
        if not facts:
            return "- " + event.get("title_seed", "No facts available")
        
        key_facts = []
        for f in facts:
            key_facts.extend(f.get("key_facts", []))
        
        # Dedupe and limit
        key_facts = list(dict.fromkeys(key_facts))[:8]
        
        if not key_facts:
            return "- " + event.get("title_seed", "")
        
        return "\n".join(f"- {fact}" for fact in key_facts)


class EventStorySynthesizer:
    """Synthesizes stories for events."""
    
    def __init__(self, db):
        self.db = db
        self.synthesizer = StorySynthesizer()
    
    async def _get_source_context(self, event: Dict) -> str:
        """Get context from source articles."""
        context_parts = []
        
        for article_id in event.get("article_ids", [])[:3]:
            article = await self.db.normalized_articles.find_one({"id": article_id})
            if article:
                context_parts.append(f"[{article.get('source_name', 'Source')}]: {article.get('clean_text', '')[:500]}")
        
        return "\n\n".join(context_parts)
    
    async def synthesize_event(self, event_id: str) -> Dict[str, Any]:
        """Synthesize full story for an event."""
        event = await self.db.news_events.find_one({"id": event_id})
        if not event:
            return {"ok": False, "error": "Event not found"}
        
        # Check if should synthesize
        if event.get("status") not in ["developing", "confirmed", "official"]:
            return {"ok": False, "error": "Event not ready for synthesis"}
        
        if event.get("source_count", 0) < 2:
            return {"ok": False, "error": "Not enough sources"}
        
        try:
            # Generate headline
            headline_en = await self.synthesizer.generate_headline(event)
            if not headline_en:
                headline_en = event.get("title_seed", "Crypto News Update")
            
            # Generate summary
            summary_en = await self.synthesizer.generate_summary(event, headline_en)
            if not summary_en:
                summary_en = headline_en
            
            # Get source context
            source_context = await self._get_source_context(event)
            
            # Generate full story (EN)
            story_en = await self.synthesizer.generate_story(
                event, headline_en, summary_en, source_context, "English"
            )
            
            # Generate AI view
            ai_view_en = await self.synthesizer.generate_ai_view(
                event, headline_en, summary_en, "English"
            )
            
            # Generate Russian versions for RU sources
            headline_ru = None
            summary_ru = None
            story_ru = None
            ai_view_ru = None
            
            # Check if any source is Russian
            ru_sources = ["incrypted", "forklog", "bits_media"]
            has_ru_source = any(
                aid for aid in event.get("article_ids", [])
                if any(rs in aid.lower() for rs in ru_sources)
            )
            
            if has_ru_source:
                # Generate Russian story
                story_ru = await self.synthesizer.generate_story(
                    event, headline_en, summary_en, source_context, "Russian"
                )
                ai_view_ru = await self.synthesizer.generate_ai_view(
                    event, headline_en, summary_en, "Russian"
                )
            
            # Update event
            now = datetime.now(timezone.utc)
            update_data = {
                "title_en": headline_en,
                "title_ru": headline_ru,
                "summary_en": summary_en,
                "summary_ru": summary_ru,
                "story_en": story_en,
                "story_ru": story_ru,
                "ai_view_en": ai_view_en,
                "ai_view_ru": ai_view_ru,
                "published_at": now.isoformat()
            }
            
            await self.db.news_events.update_one(
                {"id": event_id},
                {"$set": update_data}
            )
            
            return {
                "ok": True,
                "event_id": event_id,
                "headline": headline_en,
                "has_story": bool(story_en)
            }
            
        except Exception as e:
            logger.error(f"[StorySynthesizer] Error: {e}")
            return {"ok": False, "error": str(e)}
    
    async def process_pending_events(self, limit: int = 5) -> Dict[str, Any]:
        """
        Process events that need story synthesis.
        Only processes events with importance > 60 (slow pipeline optimization).
        """
        results = {
            "processed": 0,
            "success": 0,
            "skipped_low_importance": 0,
            "errors": 0
        }
        
        # Find confirmed/developing events without stories
        cursor = self.db.news_events.find({
            "status": {"$in": ["confirmed", "developing"]},
            "source_count": {"$gte": 2},
            "story_en": None
        }).sort("importance_score", -1).limit(limit * 2)  # Get more, filter by importance
        
        processed = 0
        async for event in cursor:
            if processed >= limit:
                break
            
            # Importance filter - only process important events
            importance = event.get("importance_score", 0.5)
            if importance < 0.6:  # Skip low importance events
                results["skipped_low_importance"] += 1
                continue
            
            results["processed"] += 1
            processed += 1
            
            try:
                result = await self.synthesize_event(event["id"])
                
                if result.get("ok"):
                    results["success"] += 1
                else:
                    results["errors"] += 1
                    logger.warning(f"[StorySynthesizer] Failed for {event['id']}: {result.get('error')}")
                    
            except Exception as e:
                results["errors"] += 1
                logger.error(f"[StorySynthesizer] Error: {e}")
        
        return results
