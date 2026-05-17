"""
Cover Image Generation Module
=============================

Generates cover images for confirmed news events using Gemini Nano Banana.
Images are stored as base64 or URLs and cached to avoid regeneration.
"""

import asyncio
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class CoverImageGenerator:
    """Generates cover images for news events using OpenAI."""
    
    def __init__(self, db=None):
        self.db = db
        self._api_key = None  # Will be fetched from DB
        self.model = "gpt-image-1"  # OpenAI image generation model
        
    async def _get_api_key(self) -> Optional[str]:
        """Get API key from LLM keys collection or environment."""
        # Try to get from LLM keys in database (with image capability)
        if self.db is not None:
            try:
                key_doc = await self.db.llm_keys.find_one({
                    "enabled": True,
                    "healthy": True,
                    "capabilities": "image"
                })
                if key_doc and key_doc.get("api_key"):
                    self._api_key = key_doc["api_key"]
                    logger.info(f"[ImageGen] Using LLM key from DB: {key_doc.get('name')}")
                    return self._api_key
            except Exception as e:
                logger.warning(f"[ImageGen] Failed to get key from DB: {e}")
        
        # Fallback to environment
        self._api_key = os.getenv("EMERGENT_LLM_KEY") or os.getenv("OPENAI_API_KEY")
        if self._api_key:
            logger.info("[ImageGen] Using API key from environment")
        return self._api_key
        
    def _generate_prompt(self, event: Dict[str, Any]) -> str:
        """Generate image prompt from event data."""
        title = event.get("title_en") or event.get("title_seed", "Crypto News")
        event_type = event.get("event_type", "news")
        entities = event.get("primary_entities", [])
        assets = event.get("primary_assets", [])
        
        # Build context
        context_parts = []
        if entities:
            context_parts.append(f"Entities: {', '.join(entities[:3])}")
        if assets:
            context_parts.append(f"Assets: {', '.join(assets[:3])}")
        
        context = ". ".join(context_parts) if context_parts else ""
        
        # Event type specific styling
        type_styles = {
            "regulation": "government/regulatory theme, scales of justice motif",
            "funding": "investment/growth theme, upward arrows, wealth symbols",
            "listing": "trading/exchange theme, chart patterns, exchange icons",
            "partnership": "collaboration theme, connecting nodes, handshake motif",
            "hack": "security theme, warning signals, digital breach visualization",
            "governance": "voting/dao theme, ballot symbols, community governance",
            "launch": "product launch theme, rocket or launch imagery",
            "airdrop": "distribution theme, tokens falling, celebration",
            "acquisition": "merger theme, combining elements, business deal",
            "legal": "legal/court theme, gavel, legal documents"
        }
        
        style_addition = type_styles.get(event_type, "general crypto news theme")
        
        prompt = f"""Create a professional crypto news editorial illustration.

Topic: {title[:100]}
{context}

Style requirements:
- Modern fintech editorial illustration
- Dark neutral background (#0D1117 or similar dark theme)
- Abstract blockchain/crypto visual elements
- Clean, minimalistic design
- {style_addition}
- Premium quality, suitable for news article header
- No text, logos, or specific brand symbols
- Aspect ratio: landscape (1200x630 pixels)
- Professional editorial quality like Bloomberg or Messari

Do not include any text or words in the image."""

        return prompt
    
    async def generate_for_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate cover image for a news event using OpenAI."""
        event_id = event.get("id")
        
        if not event_id:
            logger.warning("No event ID provided")
            return None
        
        # Check if already has image
        if event.get("cover_image_url") or event.get("cover_image_base64"):
            logger.info(f"[ImageGen] Event {event_id} already has cover image")
            return {"status": "exists", "event_id": event_id}
        
        # Only generate for confirmed/developing events
        status = event.get("status", "candidate")
        if status not in ["confirmed", "developing"]:
            logger.info(f"[ImageGen] Skipping {event_id} - status is {status}")
            return {"status": "skipped", "reason": f"status={status}"}
        
        api_key = await self._get_api_key()
        if not api_key:
            logger.warning("[ImageGen] No API key configured")
            return {"status": "error", "reason": "no_api_key"}
        
        try:
            from openai import AsyncOpenAI
            
            # Generate prompt
            prompt = self._generate_prompt(event)
            
            client = AsyncOpenAI(api_key=api_key)
            image_response = await client.images.generate(
                model=self.model,
                prompt=prompt,
                n=1,
                size="1536x1024",
                quality="high",
                response_format="b64_json"
            )
            
            if not image_response.data:
                logger.warning(f"[ImageGen] No images generated for {event_id}")
                return {"status": "error", "reason": "no_image_generated"}
            
            image_base64 = image_response.data[0].b64_json
            if not image_base64:
                logger.warning(f"[ImageGen] Image generated without b64 payload for {event_id}")
                return {"status": "error", "reason": "empty_image_payload"}
            
            data_url = f"data:image/png;base64,{image_base64}"
            
            # Update event in database
            if self.db is not None:
                await self.db.news_events.update_one(
                    {"id": event_id},
                    {
                        "$set": {
                            "cover_image_base64": data_url,
                            "cover_image_generated_at": datetime.now(timezone.utc).isoformat(),
                            "cover_image_prompt": prompt[:500]
                        }
                    }
                )
            
            logger.info(f"[ImageGen] Generated cover image for {event_id}")
            
            return {
                "status": "success",
                "event_id": event_id,
                "image_size": len(image_base64)
            }
            
        except Exception as e:
            logger.error(f"[ImageGen] Error generating image for {event_id}: {e}")
            return {"status": "error", "reason": str(e)}
    
    async def generate_batch(self, limit: int = 5) -> Dict[str, Any]:
        """Generate images for confirmed events without images."""
        if self.db is None:
            return {"error": "No database connection"}
        
        # Find confirmed events without images
        events = await self.db.news_events.find({
            "status": {"$in": ["confirmed", "developing"]},
            "cover_image_base64": {"$exists": False},
            "cover_image_url": {"$exists": False}
        }).sort("feed_score", -1).limit(limit).to_list(limit)
        
        results = {
            "total": len(events),
            "generated": 0,
            "skipped": 0,
            "errors": 0,
            "details": []
        }
        
        for event in events:
            result = await self.generate_for_event(event)
            results["details"].append(result)
            
            if result and result.get("status") == "success":
                results["generated"] += 1
            elif result and result.get("status") == "skipped":
                results["skipped"] += 1
            else:
                results["errors"] += 1
            
            # Small delay between generations
            await asyncio.sleep(1)
        
        return results


# Global instance
_image_generator: Optional[CoverImageGenerator] = None


def get_image_generator() -> CoverImageGenerator:
    """Get global image generator instance."""
    global _image_generator
    if _image_generator is None:
        _image_generator = CoverImageGenerator()
    return _image_generator


def set_image_generator_db(db):
    """Set database for image generator."""
    global _image_generator
    if _image_generator is None:
        _image_generator = CoverImageGenerator(db)
    else:
        _image_generator.db = db
