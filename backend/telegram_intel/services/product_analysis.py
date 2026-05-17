"""
Telegram Intel - AI Product Analysis Service
Analyzes channel posts to determine what product/service the channel offers,
how it monetizes, and trust indicators.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger(__name__)


PRODUCT_ANALYSIS_PROMPT = """You are an expert Telegram channel analyst. Analyze the following channel data and recent posts to determine what product or service this channel offers and how it monetizes.

Channel info:
- Name: {title} (@{username})
- Subscribers: {members}
- About: {about}
- Sector: {sector}

Recent posts (last {post_count}):
{posts_text}

Based on this data, provide a JSON analysis with these fields:

{{
  "product_types": ["list of product types: Advertising, Private community, Courses, Signals & research, Free content, Consulting, Token/NFT promotion, Affiliate marketing, News aggregation, Tool/Bot service"],
  "revenue_model": "How the channel likely earns money (1-2 sentences)",
  "ad_frequency": "none|rare|moderate|frequent|heavy",
  "ad_percentage": 0-100,
  "product_rating": 1.0-5.0,
  "product_description": "2-3 sentence description of what this channel offers as a product",
  "trust_indicators": ["list of 3-5 trust or risk indicators based on content quality"],
  "trust_score": 1-10,
  "monetization_signals": ["specific signals found in posts indicating monetization"],
  "user_value": "What value does a subscriber get from this channel (1-2 sentences)",
  "refund_risk": "low|medium|high",
  "content_quality": "low|medium|high|premium"
}}

Be specific and evidence-based. If the channel appears to be purely informational with no monetization, say so. Only output valid JSON, no markdown."""


async def analyze_channel_product(db, username: str) -> Dict[str, Any]:
    """Run AI analysis on channel's product/monetization"""
    try:
        # Get channel info
        channel = await db.tg_channel_states.find_one(
            {"username": username},
            {"_id": 0, "username": 1, "title": 1, "participantsCount": 1, "about": 1, "sector": 1}
        )
        if not channel:
            return {"ok": False, "error": "Channel not found"}

        # Get recent posts
        posts = await db.tg_posts.find(
            {"username": username, "text": {"$ne": None}},
            {"_id": 0, "text": 1, "views": 1, "forwards": 1, "date": 1}
        ).sort("date", -1).limit(80).to_list(80)

        if len(posts) < 3:
            return {"ok": False, "error": "Not enough posts to analyze"}

        # Build posts text for prompt (limit to avoid token overflow)
        posts_text = ""
        char_count = 0
        for i, p in enumerate(posts):
            text = (p.get("text") or "").strip()
            if not text:
                continue
            entry = f"[{i+1}] (views: {p.get('views', 0)}) {text[:300]}\n"
            if char_count + len(entry) > 8000:
                break
            posts_text += entry
            char_count += len(entry)

        prompt = PRODUCT_ANALYSIS_PROMPT.format(
            title=channel.get("title", username),
            username=username,
            members=channel.get("participantsCount", 0),
            about=channel.get("about", "N/A"),
            sector=channel.get("sector", "Unknown"),
            post_count=len(posts),
            posts_text=posts_text,
        )

        # Call OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"ok": False, "error": "OpenAI API key not configured"}

        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1200,
        )

        raw = response.choices[0].message.content.strip()
        # Clean markdown wrapper if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]

        analysis = json.loads(raw)

        # Save to DB
        now = datetime.now(timezone.utc)
        await db.tg_channel_states.update_one(
            {"username": username},
            {"$set": {
                "productAnalysis": analysis,
                "productAnalysisAt": now,
            }}
        )

        return {"ok": True, "username": username, "analysis": analysis}

    except json.JSONDecodeError as e:
        logger.error(f"AI product analysis JSON parse error for @{username}: {e}")
        return {"ok": False, "error": f"AI response parse error: {str(e)}"}
    except Exception as e:
        logger.error(f"AI product analysis error for @{username}: {e}")
        return {"ok": False, "error": str(e)}
