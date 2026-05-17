"""
AI News Generation Engine
- Fetches recent news clusters from Node.js news-intelligence
- Generates AI digest article (RU + EN) using Emergent LLM key
- Generates cover image via GPT Image 1
- Stores in MongoDB
"""

from fastapi import APIRouter
from fastapi.responses import Response
import os
import json
import base64
import hashlib
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

router = APIRouter(prefix="/api/ai-news", tags=["ai-news"])

_mongo_url = os.environ.get("MONGO_URL")
_db_name = os.environ.get("DB_NAME", "intelligence_engine")
_motor = AsyncIOMotorClient(_mongo_url) if _mongo_url else None
_db = _motor[_db_name] if _motor else None


async def _fetch_news_clusters():
    """Fetch recent clusters from the Node.js news-intelligence service."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get("http://localhost:8001/api/news/feed?limit=20&hours=24")
            data = res.json()
            if data.get("ok"):
                return data.get("data", {}).get("clusters", [])
    except Exception:
        pass
    return []


def _build_article_prompt(clusters, lang="en"):
    if not clusters:
        return None

    top = sorted(clusters, key=lambda c: c.get("importance", 0), reverse=True)[:8]

    headlines = []
    for c in top:
        sentiment = c.get("sentimentHint", "neutral")
        event_type = c.get("eventType", "market")
        importance = c.get("importance", 0)
        title = c.get("title", "")
        sources = c.get("sourcesCount", 1)
        assets = ", ".join(c.get("assets", [])[:3]) or "market"
        headlines.append(f"- [{event_type.upper()}] {title} (sentiment: {sentiment}, importance: {importance}, assets: {assets}, sources: {sources})")

    headlines_text = "\n".join(headlines)

    if lang == "ru":
        return f"""Ты — профессиональный криптоаналитик. На основе следующих ключевых событий за последние 24 часа, напиши краткий аналитический дайджест на РУССКОМ языке.

Требования:
- Заголовок (1 строка, цепляющий)
- Основной текст (3-4 абзаца, ~300 слов)
- В конце: список из 3-4 ключевых сигналов
- Тон: профессиональный, но живой
- Укажи конкретные монеты/токены и цифры из новостей

События:
{headlines_text}

Ответ дай СТРОГО в формате JSON:
{{"title": "...", "body": "...", "signals": ["...", "..."], "sentiment": "bullish|bearish|mixed"}}"""
    else:
        return f"""You are a professional crypto analyst. Based on the following key events from the last 24 hours, write a concise analytical digest in ENGLISH.

Requirements:
- Title (1 line, engaging)
- Body (3-4 paragraphs, ~300 words)
- End with: list of 3-4 key signals
- Tone: professional but sharp
- Reference specific coins/tokens and numbers

Events:
{headlines_text}

Respond STRICTLY in JSON format:
{{"title": "...", "body": "...", "signals": ["...", "..."], "sentiment": "bullish|bearish|mixed"}}"""


def _parse_json_response(resp_text):
    clean = resp_text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        clean = clean.rsplit("```", 1)[0]
    return json.loads(clean)


def _build_full_article_prompt(clusters, lang="en"):
    """Build prompt for a detailed full article from clusters."""
    if not clusters:
        return None

    top = sorted(clusters, key=lambda c: c.get("importance", 0), reverse=True)[:8]
    headlines = []
    for c in top:
        sentiment = c.get("sentimentHint", "neutral")
        event_type = c.get("eventType", "market")
        importance = c.get("importance", 0)
        title = c.get("title", "")
        sources = c.get("sourcesCount", 1)
        assets = ", ".join(c.get("assets", [])[:3]) or "market"
        headlines.append(f"- [{event_type.upper()}] {title} (sentiment: {sentiment}, importance: {importance}, assets: {assets}, sources: {sources})")
    headlines_text = "\n".join(headlines)

    if lang == "ru":
        return f"""Ты — криптоаналитик. Напиши ПОДРОБНУЮ аналитическую статью на РУССКОМ на основе ключевых событий за 24 часа.

События:
{headlines_text}

Требования:
- Заголовок (1 строка, профессиональный)
- 5-7 параграфов глубокого анализа (~600 слов)
- Укажи влияние на конкретные токены/активы
- Дай прогноз: что будет дальше
- Укажи риски и возможности
- В конце: 3-5 ключевых выводов

JSON формат:
{{"title": "...", "body": "...", "conclusions": ["...", "..."], "forecast": "...", "sentiment": "bullish|bearish|mixed"}}"""
    else:
        return f"""You are a crypto analyst. Write a DETAILED analytical article in ENGLISH based on key events from the last 24 hours.

Events:
{headlines_text}

Requirements:
- Title (1 line, professional)
- 5-7 paragraphs of deep analysis (~600 words)
- Impact on specific tokens/assets
- Forecast: what happens next
- Risks and opportunities
- End with: 3-5 key conclusions

JSON format:
{{"title": "...", "body": "...", "conclusions": ["...", "..."], "forecast": "...", "sentiment": "bullish|bearish|mixed"}}"""


@router.post("/generate")
async def generate_ai_article():
    """Generate AI digest from recent news clusters."""
    llm_key = os.environ.get("EMERGENT_LLM_KEY")
    if not llm_key:
        return {"ok": False, "error": "EMERGENT_LLM_KEY not configured"}

    clusters = await _fetch_news_clusters()
    if not clusters:
        return {"ok": False, "error": "No news clusters available"}

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        articles = {}
        full_articles = {}

        for lang in ["en", "ru"]:
            # Generate mini digest
            prompt = _build_article_prompt(clusters, lang)
            if not prompt:
                continue

            chat = LlmChat(
                api_key=llm_key,
                session_id=f"news-digest-{lang}-{datetime.now(timezone.utc).strftime('%Y%m%d%H')}",
                system_message="You are a crypto market analyst. Always respond with valid JSON only, no markdown."
            )
            chat = chat.with_model("openai", "gpt-4o")

            resp_text = await chat.send_message(UserMessage(text=prompt))
            article_data = _parse_json_response(resp_text)
            articles[lang] = article_data

            # Generate full article
            full_prompt = _build_full_article_prompt(clusters, lang)
            if full_prompt:
                full_chat = LlmChat(
                    api_key=llm_key,
                    session_id=f"news-full-{lang}-{datetime.now(timezone.utc).strftime('%Y%m%d%H')}",
                    system_message="You are a crypto market analyst. Always respond with valid JSON only, no markdown."
                )
                full_chat = full_chat.with_model("openai", "gpt-4o")
                full_resp = await full_chat.send_message(UserMessage(text=full_prompt))
                full_articles[lang] = _parse_json_response(full_resp)

        # Generate cover image
        image_id = None
        en_article = articles.get("en", articles.get("ru", {}))
        try:
            from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration

            sentiment = en_article.get("sentiment", "mixed")
            mood = "optimistic green tones" if sentiment == "bullish" else "dramatic red tones" if sentiment == "bearish" else "neutral blue-gray tones"
            img_prompt = f"Abstract crypto market illustration: {mood}, clean minimal composition, dark background with glowing geometric blockchain shapes, no text, professional cover art style"

            gen = OpenAIImageGeneration(api_key=llm_key)
            images = await gen.generate_images(prompt=img_prompt, model="gpt-image-1", number_of_images=1, quality="low")

            if images and len(images) > 0:
                image_bytes = images[0]
                image_id = hashlib.md5(image_bytes[:100]).hexdigest()[:12]
                # Store in MongoDB as base64
                if _db is not None:
                    await _db["ai_news_images"].update_one(
                        {"imageId": image_id},
                        {"$set": {
                            "imageId": image_id,
                            "data": base64.b64encode(image_bytes).decode(),
                            "createdAt": datetime.now(timezone.utc).isoformat(),
                        }},
                        upsert=True
                    )
        except Exception as img_err:
            print(f"Image gen error (non-critical): {img_err}")

        # Store article in MongoDB
        doc = {
            "en": articles.get("en"),
            "ru": articles.get("ru"),
            "fullEn": full_articles.get("en"),
            "fullRu": full_articles.get("ru"),
            "imageId": image_id,
            "sourceClusterCount": len(clusters),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "type": "ai_digest",
        }

        if _db is not None:
            await _db["ai_news_digests"].insert_one(doc)
            doc.pop("_id", None)

        return {"ok": True, "article": doc}

    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Failed to parse AI response: {str(e)}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}



@router.post("/expand")
async def expand_news_cluster(body: dict):
    """Generate a full deep-dive article from a news cluster."""
    llm_key = os.environ.get("EMERGENT_LLM_KEY")
    if not llm_key:
        return {"ok": False, "error": "EMERGENT_LLM_KEY not configured"}

    title = body.get("title", "")
    summary = body.get("summary", "")
    sentiment = body.get("sentiment", "neutral")
    event_type = body.get("eventType", "market")
    assets = body.get("assets", [])
    sources_count = body.get("sourcesCount", 1)
    events = body.get("events", [])

    events_text = ""
    for ev in events[:5]:
        events_text += f"- {ev.get('publisher', '')}: {ev.get('title', '')}\n"

    lang = body.get("lang", "ru")

    if lang == "ru":
        prompt = f"""Ты — криптоаналитик. Напиши ПОДРОБНУЮ аналитическую статью на РУССКОМ на основе этой новости.

Новость: {title}
Краткое содержание: {summary}
Тип события: {event_type}
Настроение рынка: {sentiment}
Затронутые активы: {', '.join(assets) if assets else 'рынок в целом'}
Количество источников: {sources_count}
Детали от источников:
{events_text}

Требования:
- Заголовок (1 строка, профессиональный)
- 5-7 параграфов глубокого анализа (~600 слов)
- Укажи влияние на конкретные токены/активы
- Дай прогноз: что будет дальше
- Укажи риски и возможности
- В конце: 3-5 ключевых выводов

JSON формат:
{{"title": "...", "body": "...", "conclusions": ["...", "..."], "forecast": "...", "sentiment": "bullish|bearish|mixed"}}"""
    else:
        prompt = f"""You are a crypto analyst. Write a DETAILED analytical article in ENGLISH based on this news.

News: {title}
Summary: {summary}
Event type: {event_type}
Market sentiment: {sentiment}
Affected assets: {', '.join(assets) if assets else 'market overall'}
Sources count: {sources_count}
Source details:
{events_text}

Requirements:
- Title (1 line, professional)
- 5-7 paragraphs of deep analysis (~600 words)
- Impact on specific tokens/assets
- Forecast: what happens next
- Risks and opportunities
- End with: 3-5 key conclusions

JSON format:
{{"title": "...", "body": "...", "conclusions": ["...", "..."], "forecast": "...", "sentiment": "bullish|bearish|mixed"}}"""

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"news-expand-{hashlib.md5(title.encode()).hexdigest()[:8]}",
            system_message="You are a crypto market analyst. Always respond with valid JSON only."
        )
        chat = chat.with_model("openai", "gpt-4o")
        resp_text = await chat.send_message(UserMessage(text=prompt))
        article = _parse_json_response(resp_text)

        # Generate cover image
        image_id = None
        try:
            from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
            s_mood = "optimistic green" if article.get("sentiment") == "bullish" else "dramatic red" if article.get("sentiment") == "bearish" else "cool blue-gray"
            img_prompt = f"Abstract crypto market illustration for article about {event_type}: {s_mood} tones, dark background, glowing blockchain shapes, no text, cover art"
            gen = OpenAIImageGeneration(api_key=llm_key)
            images = await gen.generate_images(prompt=img_prompt, model="gpt-image-1", number_of_images=1, quality="low")
            if images:
                image_id = hashlib.md5(images[0][:100]).hexdigest()[:12]
                if _db is not None:
                    await _db["ai_news_images"].update_one(
                        {"imageId": image_id},
                        {"$set": {"imageId": image_id, "data": base64.b64encode(images[0]).decode(), "createdAt": datetime.now(timezone.utc).isoformat()}},
                        upsert=True
                    )
        except Exception:
            pass

        return {"ok": True, "article": article, "imageId": image_id}

    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/articles")
async def get_ai_articles(limit: int = 10):
    """Get stored AI-generated articles."""
    if _db is None:
        return {"ok": True, "articles": []}

    articles = await _db["ai_news_digests"] \
        .find({}, {"_id": 0}) \
        .sort("generatedAt", -1) \
        .limit(limit) \
        .to_list(limit)

    return {"ok": True, "articles": articles}


@router.get("/latest")
async def get_latest_ai_article():
    """Get the most recent AI-generated article."""
    if _db is None:
        return {"ok": True, "article": None}

    article = await _db["ai_news_digests"] \
        .find_one({}, {"_id": 0}, sort=[("generatedAt", -1)])

    return {"ok": True, "article": article}


@router.get("/image/{image_id}")
async def get_ai_image(image_id: str):
    """Serve a stored AI-generated image."""
    if _db is None:
        return Response(status_code=404)

    doc = await _db["ai_news_images"].find_one({"imageId": image_id}, {"_id": 0})
    if not doc or not doc.get("data"):
        return Response(status_code=404)

    image_bytes = base64.b64decode(doc["data"])
    return Response(content=image_bytes, media_type="image/png")
