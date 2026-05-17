"""
Sentiment Service — REAL Data Pipeline
=======================================

Sources:
1. Alternative.me Fear & Greed Index (FREE API, no key needed)
2. CoinGecko community/developer data (FREE API)
3. LLM sentiment analysis of recent crypto news headlines

Stores sentiment_events in MongoDB for the adapter to read.
"""
import os
import json
import logging
import httpx
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "test_database")
EMERGENT_KEY = os.getenv("EMERGENT_LLM_KEY", "")

_client = MongoClient(MONGO_URL)
_db = _client[DB_NAME]


# ==================== 1. FEAR & GREED INDEX ====================

async def fetch_fear_greed() -> dict | None:
    """Fetch real Fear & Greed Index from Alternative.me (free, no key)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=7&format=json")
            if resp.status_code == 200:
                data = resp.json()
                entries = data.get("data", [])
                if entries:
                    latest = entries[0]
                    return {
                        "value": int(latest.get("value", 50)),
                        "classification": latest.get("value_classification", "Neutral"),
                        "timestamp": datetime.fromtimestamp(int(latest.get("timestamp", 0)), tz=timezone.utc),
                        "history": [
                            {"value": int(e.get("value", 50)), "classification": e.get("value_classification", ""),
                             "date": datetime.fromtimestamp(int(e.get("timestamp", 0)), tz=timezone.utc).strftime("%Y-%m-%d")}
                            for e in entries[:7]
                        ],
                    }
    except Exception as e:
        logger.error(f"[Sentiment] Fear & Greed fetch error: {e}")
    return None


# ==================== 2. COINGECKO COMMUNITY DATA ====================

async def fetch_coingecko_sentiment(asset: str = "bitcoin") -> dict | None:
    """Fetch community sentiment data from CoinGecko (free tier)."""
    coin_ids = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
    coin_id = coin_ids.get(asset.upper(), asset.lower())
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                params={"localization": "false", "tickers": "false", "market_data": "true",
                         "community_data": "true", "developer_data": "false"}
            )
            if resp.status_code == 200:
                data = resp.json()
                community = data.get("community_data", {})
                market = data.get("market_data", {})
                sentiment = data.get("sentiment_votes_up_percentage", 0)
                
                return {
                    "asset": asset.upper(),
                    "sentiment_up_pct": sentiment or 0,
                    "sentiment_down_pct": data.get("sentiment_votes_down_percentage", 0),
                    "reddit_subscribers": community.get("reddit_subscribers", 0),
                    "reddit_active_48h": community.get("reddit_accounts_active_48h", 0),
                    "twitter_followers": community.get("twitter_followers", 0),
                    "price_change_24h": market.get("price_change_percentage_24h", 0),
                    "price_change_7d": market.get("price_change_percentage_7d", 0),
                    "market_cap_rank": data.get("market_cap_rank", 0),
                }
    except Exception as e:
        logger.error(f"[Sentiment] CoinGecko fetch error for {asset}: {e}")
    return None


# ==================== 3. LLM NEWS ANALYSIS ====================

async def analyze_headlines_with_llm(headlines: list[str], asset: str = "BTC") -> list[dict]:
    """Analyze news headlines.

    Hierarchy:
      1. VADER NLP (rule-based, local, no key) — ALWAYS run, primary substrate
      2. Emergent LLM (if EMERGENT_KEY present) — augments VADER with intent
    VADER alone is enough to lift sentiment events out of the
    `defaulted-score-0.5` failure mode that triggers P0 degradation.
    """
    if not headlines:
        return []

    # ── Primary: VADER (deterministic, in-process, no credentials) ──
    results: list[dict] = []
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        vader = SentimentIntensityAnalyzer()
        # Crypto-domain term boosting — VADER's stock lexicon doesn't
        # know "halving" or "bullrun" etc.  Lightweight overlay.
        vader.lexicon.update({
            "bullish": 2.5, "bearish": -2.5, "moon": 2.0, "moonshot": 2.5,
            "rally": 2.0, "pump": 1.5, "dump": -2.5, "crash": -3.0,
            "ath": 2.0, "atl": -2.0, "halving": 1.5, "etf": 1.0,
            "approval": 1.5, "rejected": -1.5, "hack": -3.0, "exploit": -2.5,
            "scam": -3.0, "rugpull": -3.5, "liquidation": -1.5,
            "breakout": 1.8, "breakdown": -1.8, "support": 0.8, "resistance": -0.4,
            "fud": -1.5, "fomo": 1.0, "accumulation": 1.2, "distribution": -1.0,
        })
        for h in headlines[:20]:
            scores = vader.polarity_scores(h or "")
            comp = float(scores.get("compound", 0.0))
            if comp >= 0.20:
                intent = "BULLISH"
            elif comp <= -0.20:
                intent = "BEARISH"
            else:
                intent = "NEUTRAL"
            # Confidence: scaled by absolute compound magnitude
            conf = min(0.95, 0.4 + abs(comp) * 0.6)
            results.append({
                "sentiment_score": round(comp, 4),
                "confidence":      round(conf, 4),
                "intent":          intent,
                "reasoning":       f"VADER compound={comp:.2f} (pos={scores.get('pos',0):.2f}, neg={scores.get('neg',0):.2f}, neu={scores.get('neu',0):.2f})",
                "engine":          "vader_v1",
            })
    except Exception as e:
        logger.warning(f"[Sentiment] VADER unavailable: {e}")

    # ── Optional augmentation: Emergent LLM (only if key present) ──
    if EMERGENT_KEY and results:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            import uuid

            system = (
                "You are a crypto market sentiment analyst. For each headline, return a JSON array "
                "with objects containing: sentiment_score (-1.0 to 1.0), confidence (0-1), "
                "intent (BULLISH/BEARISH/NEUTRAL), reasoning (one sentence). "
                "Return ONLY valid JSON array, no markdown."
            )

            headlines_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines[:10]))
            prompt = f"Analyze these {asset} crypto headlines for market sentiment:\n\n{headlines_text}"

            chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=f"sentiment-{uuid.uuid4().hex[:8]}",
                system_message=system,
            )

            text = await chat.send_message(UserMessage(text=prompt))
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            llm_results = json.loads(text)
            if isinstance(llm_results, list):
                # Merge — LLM overrides VADER for entries it returned
                for i, llm_r in enumerate(llm_results):
                    if i < len(results) and isinstance(llm_r, dict):
                        llm_r["engine"] = "vader_v1+llm"
                        results[i] = llm_r
        except Exception as e:
            logger.warning(f"[Sentiment] LLM augment failed (VADER still primary): {e}")

    return results


async def fetch_crypto_news(asset: str = "BTC") -> list[str]:
    """Fetch recent crypto news headlines from free sources."""
    headlines = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Source 1: CoinGecko trending search (free, no key)
            resp = await client.get("https://api.coingecko.com/api/v3/search/trending")
            if resp.status_code == 200:
                data = resp.json()
                coins = data.get("coins", [])
                for c in coins[:5]:
                    item = c.get("item", {})
                    name = item.get("name", "")
                    symbol = item.get("symbol", "")
                    score = item.get("score", 0)
                    if name:
                        headlines.append(f"Trending: {name} ({symbol}) — rank #{score + 1} on CoinGecko")

            # Source 2: CoinGecko global data for macro context
            resp2 = await client.get("https://api.coingecko.com/api/v3/global")
            if resp2.status_code == 200:
                gdata = resp2.json().get("data", {})
                mc_change = gdata.get("market_cap_change_percentage_24h_usd", 0)
                active = gdata.get("active_cryptocurrencies", 0)
                btc_dom = gdata.get("market_cap_percentage", {}).get("btc", 0)
                headlines.append(f"Global crypto market cap change 24h: {mc_change:.1f}%")
                headlines.append(f"BTC dominance: {btc_dom:.1f}% across {active} active cryptocurrencies")
                if mc_change > 3:
                    headlines.append(f"Strong crypto market rally: total cap up {mc_change:.1f}% in 24h")
                elif mc_change < -3:
                    headlines.append(f"Crypto market selloff: total cap down {mc_change:.1f}% in 24h")
    except Exception as e:
        logger.error(f"[Sentiment] News fetch error: {e}")
    return headlines


# ==================== PIPELINE: INGEST & STORE ====================

async def run_sentiment_ingestion(assets: list[str] = None):
    """
    Full sentiment ingestion pipeline:
    1. Fetch Fear & Greed Index
    2. Fetch CoinGecko community data per asset
    3. Fetch news and analyze with LLM
    4. Store everything as sentiment_events in MongoDB
    """
    if assets is None:
        assets = ["BTC", "ETH", "SOL"]
    
    now = datetime.now(timezone.utc)
    events = []
    
    # 1. Fear & Greed Index (global crypto sentiment)
    fg = await fetch_fear_greed()
    if fg:
        events.append({
            "source": "fear_greed_index",
            "sourceType": "index",
            "symbol": "MARKET",
            "weightedScore": fg["value"] / 100.0,
            "weightedConfidence": 0.85,
            "eventType": "market_sentiment",
            "sourceWeight": 0.9,
            "createdAt": now,
            "raw": fg,
            "authorHandle": "alternative.me",
        })
        logger.info(f"[Sentiment] Fear & Greed: {fg['value']} ({fg['classification']})")
    
    for asset in assets:
        # 2. CoinGecko community sentiment
        cg = await fetch_coingecko_sentiment(asset)
        if cg:
            up_pct = cg.get("sentiment_up_pct", 50)
            score = up_pct / 100.0 if up_pct > 0 else 0.5
            
            events.append({
                "source": "coingecko",
                "sourceType": "community",
                "symbol": asset,
                "weightedScore": score,
                "weightedConfidence": 0.7,
                "eventType": "bullish_signal" if score > 0.6 else "bearish_signal" if score < 0.4 else "neutral_info",
                "sourceWeight": 0.7,
                "createdAt": now,
                "raw": cg,
                "authorHandle": "coingecko_community",
            })
            logger.info(f"[Sentiment] CoinGecko {asset}: {up_pct:.0f}% up")
        
        # 3. News + LLM analysis
        headlines = await fetch_crypto_news(asset)
        if headlines:
            llm_results = await analyze_headlines_with_llm(headlines, asset)
            
            for i, h in enumerate(headlines):
                llm_data = llm_results[i] if i < len(llm_results) else {}
                score_val = llm_data.get("sentiment_score", 0)
                conf = llm_data.get("confidence", 0.5)
                intent = llm_data.get("intent", "NEUTRAL")
                
                # Normalize score from [-1,1] to [0,1]
                normalized_score = (score_val + 1) / 2
                
                events.append({
                    "source": "cryptocompare_news",
                    "sourceType": "news",
                    "symbol": asset,
                    "weightedScore": normalized_score,
                    "weightedConfidence": conf,
                    "eventType": "bullish_signal" if intent == "BULLISH" else "bearish_signal" if intent == "BEARISH" else "neutral_info",
                    "sourceWeight": 0.6,
                    "createdAt": now,
                    "raw": {"headline": h, "llm_analysis": llm_data},
                    "authorHandle": "cryptocompare",
                })
            
            logger.info(f"[Sentiment] {asset}: {len(headlines)} news analyzed by LLM")
    
    # Store all events
    if events:
        _db.sentiment_events.insert_many(events)
        logger.info(f"[Sentiment] Stored {len(events)} sentiment events")
    
    return {"ok": True, "events_count": len(events), "assets": assets}


# ==================== API: GET SENTIMENT ====================

def get_sentiment_for_asset(asset: str = "BTC") -> dict:
    """
    Get aggregated sentiment data for an asset.
    Reads from sentiment_events in MongoDB (populated by ingestion pipeline).
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    
    # Get recent events for this asset
    events = list(_db.sentiment_events.find(
        {"symbol": {"$in": [asset.upper(), "MARKET"]}, "createdAt": {"$gte": cutoff_24h}},
    ).sort("createdAt", DESCENDING).limit(50))
    
    if not events:
        # Try last 7 days
        cutoff_7d = now - timedelta(days=7)
        events = list(_db.sentiment_events.find(
            {"symbol": {"$in": [asset.upper(), "MARKET"]}, "createdAt": {"$gte": cutoff_7d}},
        ).sort("createdAt", DESCENDING).limit(50))
    
    if not events:
        return {
            "asset": asset,
            "status": "no_data",
            "message": "No sentiment data available. Run ingestion first.",
        }
    
    # Aggregate
    total_weight = 0.0
    weighted_sum = 0.0
    conf_sum = 0.0
    bullish = 0
    bearish = 0
    neutral = 0
    
    for e in events:
        score = e.get("weightedScore", 0.5)
        conf = e.get("weightedConfidence", 0.3)
        sw = e.get("sourceWeight", 0.5)
        weighted_sum += score * sw
        conf_sum += conf * sw
        total_weight += sw
        
        if score > 0.6:
            bullish += 1
        elif score < 0.4:
            bearish += 1
        else:
            neutral += 1
    
    avg_score = weighted_sum / total_weight if total_weight > 0 else 0.5
    avg_conf = conf_sum / total_weight if total_weight > 0 else 0.3
    
    # Fear & Greed
    fg_event = next((e for e in events if e.get("source") == "fear_greed_index"), None)
    fg_data = fg_event.get("raw", {}) if fg_event else {}
    fg_value = fg_data.get("value", int(avg_score * 100))
    fg_class = fg_data.get("classification", "Neutral")
    
    # Determine state
    if avg_score > 0.75:
        state = "EUPHORIA"
    elif avg_score > 0.6:
        state = "OPTIMISM"
    elif avg_score > 0.45:
        state = "NEUTRAL"
    elif avg_score > 0.3:
        state = "FEAR"
    else:
        state = "CAPITULATION"
    
    # Direction
    direction = "BULLISH" if avg_score > 0.55 else "BEARISH" if avg_score < 0.45 else "NEUTRAL"
    strength = min(1.0, abs(avg_score - 0.5) * 2.5)
    
    # Community data
    cg_event = next((e for e in events if e.get("source") == "coingecko" and e.get("symbol") == asset), None)
    cg_data = cg_event.get("raw", {}) if cg_event else {}
    
    # News headlines (from LLM analysis)
    news_events = [e for e in events if e.get("sourceType") == "news" and e.get("symbol") == asset]
    headlines = [
        {
            "text": e.get("raw", {}).get("headline", ""),
            "sentiment": "bullish" if e.get("weightedScore", 0.5) > 0.6 else "bearish" if e.get("weightedScore", 0.5) < 0.4 else "neutral",
            "score": round(e.get("weightedScore", 0.5), 2),
        }
        for e in news_events[:5]
    ]
    
    return {
        "asset": asset,
        "status": "active",
        "state": state,
        "direction": direction,
        "strength": round(strength, 2),
        "confidence": round(avg_conf, 2),
        "score": round(avg_score * 100),
        "fearGreed": {
            "value": fg_value,
            "classification": fg_class,
            "history": fg_data.get("history", []),
        },
        "community": {
            "sentimentUp": cg_data.get("sentiment_up_pct", 0),
            "sentimentDown": cg_data.get("sentiment_down_pct", 0),
            "redditSubscribers": cg_data.get("reddit_subscribers", 0),
            "redditActive48h": cg_data.get("reddit_active_48h", 0),
            "twitterFollowers": cg_data.get("twitter_followers", 0),
        },
        "priceContext": {
            "change24h": cg_data.get("price_change_24h", 0),
            "change7d": cg_data.get("price_change_7d", 0),
        },
        "distribution": {
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "total": len(events),
        },
        "topHeadlines": headlines,
        "signal": {
            "direction": direction,
            "strength": "STRONG" if strength > 0.5 else "MODERATE" if strength > 0.25 else "WEAK",
            "confidence": round(avg_conf, 2),
        },
        "sources": list(set(e.get("source", "unknown") for e in events)),
        "lastUpdated": events[0].get("createdAt").isoformat() if events else None,
    }
