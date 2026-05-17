"""
Real Sentiment Model — Phase 1
================================
Replaces fake CNN/lexicon ensemble with actual LLM inference.

For each tweet/text:
  - sentiment_label: POSITIVE / NEGATIVE / NEUTRAL
  - sentiment_score: -1.0 to +1.0
  - confidence: 0.0 to 1.0
  - intent_label: BULLISH_SIGNAL / BEARISH_SIGNAL / INFORMATIONAL / WARNING / HYPE / NOISE
  - uncertainty_flag: true/false

Uses GPT-4o-mini via Emergent LLM key for fast, cheap classification.
"""

import os
import json
import re
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage

load_dotenv()

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# ─── System prompt for sentiment classification ───

SYSTEM_PROMPT = """You are a crypto market sentiment classifier. Analyze tweet text and return ONLY a valid JSON object.

RULES:
1. Classify the MARKET SENTIMENT and TRADING INTENT of the text
2. "Bullish" means the author expects price to go UP
3. "Bearish" means the author expects price to go DOWN
4. Distinguish between genuine conviction signals vs hype/noise
5. Sarcasm and irony should be flagged as uncertain
6. Pure price reporting without opinion = INFORMATIONAL
7. Engagement farming / vague "to the moon" = HYPE
8. Genuine analysis with reasoning = BULLISH_SIGNAL or BEARISH_SIGNAL
9. Risk warnings, crash predictions = WARNING

Return EXACTLY this JSON structure (no markdown, no extra text):
{
  "sentiment_label": "POSITIVE" or "NEGATIVE" or "NEUTRAL",
  "sentiment_score": float from -1.0 to 1.0,
  "confidence": float from 0.0 to 1.0,
  "intent_label": "BULLISH_SIGNAL" or "BEARISH_SIGNAL" or "INFORMATIONAL" or "WARNING" or "HYPE" or "NOISE",
  "uncertainty_flag": true or false,
  "reasoning": "one sentence why"
}"""


def _clean_text(text):
    """Clean tweet text for analysis."""
    if not text:
        return ""
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Cap length
    return text[:800]


def _text_hash(text):
    """SHA256 hash for caching."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _parse_response(raw_text):
    """Parse LLM response into structured sentiment data."""
    # Try to extract JSON from response
    text = raw_text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return _fallback_result("parse_error")
        else:
            return _fallback_result("no_json")

    # Validate and normalize
    valid_sentiments = {"POSITIVE", "NEGATIVE", "NEUTRAL"}
    valid_intents = {"BULLISH_SIGNAL", "BEARISH_SIGNAL", "INFORMATIONAL", "WARNING", "HYPE", "NOISE"}

    sentiment_label = data.get("sentiment_label", "NEUTRAL")
    if sentiment_label not in valid_sentiments:
        sentiment_label = "NEUTRAL"

    intent_label = data.get("intent_label", "NOISE")
    if intent_label not in valid_intents:
        intent_label = "NOISE"

    score = data.get("sentiment_score", 0.0)
    try:
        score = max(-1.0, min(1.0, float(score)))
    except (ValueError, TypeError):
        score = 0.0

    confidence = data.get("confidence", 0.5)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (ValueError, TypeError):
        confidence = 0.5

    return {
        "sentiment_label": sentiment_label,
        "sentiment_score": round(score, 4),
        "confidence": round(confidence, 4),
        "intent_label": intent_label,
        "uncertainty_flag": bool(data.get("uncertainty_flag", False)),
        "reasoning": str(data.get("reasoning", ""))[:200],
    }


def _fallback_result(reason="unknown"):
    """Fallback when LLM fails."""
    return {
        "sentiment_label": "NEUTRAL",
        "sentiment_score": 0.0,
        "confidence": 0.0,
        "intent_label": "NOISE",
        "uncertainty_flag": True,
        "reasoning": f"fallback: {reason}",
    }


async def analyze_sentiment(text, author_handle="", token=""):
    """Analyze a single text for sentiment. Returns structured result."""
    clean = _clean_text(text)
    if not clean or len(clean) < 5:
        return _fallback_result("text_too_short")

    if not EMERGENT_KEY:
        return _fallback_result("no_api_key")

    try:
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"sentiment_{_text_hash(clean)}",
            system_message=SYSTEM_PROMPT,
        )
        chat.with_model("openai", "gpt-4o-mini")

        context = f"Tweet by @{author_handle}" if author_handle else "Tweet"
        if token:
            context += f" about ${token}"

        msg = UserMessage(text=f"{context}:\n\n{clean}")
        response = await chat.send_message(msg)
        return _parse_response(response)

    except Exception as e:
        return _fallback_result(f"llm_error: {str(e)[:100]}")


async def analyze_batch(items):
    """
    Analyze a batch of items. Each item: {"text": ..., "author_handle": ..., "token": ...}
    Returns list of results in same order.
    """
    results = []
    for item in items:
        result = await analyze_sentiment(
            text=item.get("text", ""),
            author_handle=item.get("author_handle", ""),
            token=item.get("token", ""),
        )
        results.append(result)
    return results


async def backfill_events(db, limit=100, skip_analyzed=True):
    """
    Run sentiment inference on existing actor_signal_events.
    Stores results in sentiment_inference_events collection.
    """
    query = {"source": "twitter_kol"}
    if skip_analyzed:
        # Skip events that already have sentiment
        analyzed_ids = await db.sentiment_inference_events.distinct("source_id")
        if analyzed_ids:
            query["tweet_id"] = {"$nin": analyzed_ids}

    events = await db.actor_signal_events.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    if not events:
        return {"ok": True, "processed": 0, "message": "no events to process"}

    processed = 0
    errors = 0

    for event in events:
        text = event.get("text", "")
        if not text or len(text) < 10:
            continue

        result = await analyze_sentiment(
            text=text,
            author_handle=event.get("actor_handle", ""),
            token=event.get("token", ""),
        )

        doc = {
            "source_id": event.get("tweet_id", ""),
            "source_type": "actor_signal_event",
            "text": text[:500],
            "clean_text": _clean_text(text),
            "tokens": [event.get("token", "")] if event.get("token") else [],
            "author_id": event.get("actor_id", ""),
            "author_handle": event.get("actor_handle", ""),
            **result,
            "model_version": "gpt-4o-mini-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            await db.sentiment_inference_events.update_one(
                {"source_id": doc["source_id"]},
                {"$set": doc},
                upsert=True,
            )
            processed += 1
        except Exception:
            errors += 1

    return {
        "ok": True,
        "processed": processed,
        "errors": errors,
        "total_events": len(events),
    }


async def get_inference_stats(db):
    """Get stats on sentiment inference events."""
    total = await db.sentiment_inference_events.count_documents({})
    by_sentiment = {}
    async for doc in db.sentiment_inference_events.aggregate([
        {"$group": {"_id": "$sentiment_label", "count": {"$sum": 1}}}
    ]):
        by_sentiment[doc["_id"]] = doc["count"]

    by_intent = {}
    async for doc in db.sentiment_inference_events.aggregate([
        {"$group": {"_id": "$intent_label", "count": {"$sum": 1}}}
    ]):
        by_intent[doc["_id"]] = doc["count"]

    avg_confidence = 0
    async for doc in db.sentiment_inference_events.aggregate([
        {"$group": {"_id": None, "avg": {"$avg": "$confidence"}}}
    ]):
        avg_confidence = round(doc["avg"], 4)

    uncertain_count = await db.sentiment_inference_events.count_documents({"uncertainty_flag": True})

    return {
        "total": total,
        "by_sentiment": by_sentiment,
        "by_intent": by_intent,
        "avg_confidence": avg_confidence,
        "uncertain_pct": round(uncertain_count / total * 100, 1) if total > 0 else 0,
    }
