"""
Twitter Search Service — Unified Parser
========================================
Единый парсер с двумя режимами:
  Mode A: Account → UserTweets (GraphQL + cookies)
  Mode B: Keyword → SearchTimeline (GraphQL) → fallback Playwright
Общий pipeline: tweets → normalize → store → signal engine
"""

import json
import re
import base64
import logging
import os
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("TwitterParser")

COOKIE_ENC_KEY = None
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith("COOKIE_ENC_KEY="):
                COOKIE_ENC_KEY = line.strip().split("=", 1)[1]
                break
if not COOKIE_ENC_KEY:
    COOKIE_ENC_KEY = os.environ.get("COOKIE_ENC_KEY", "")

GQL_BASE = "https://x.com/i/api/graphql"
API_BASE = "https://api.x.com/1.1"
BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

USER_OP = "IGgvgiOx4QZndDHuD3x9TQ/UserByScreenName"
TWEETS_OP = "O0epvwaQPUx-bT9YlqlL6w/UserTweets"
SEARCH_OP = "MJpyQGqgklrVl_0X9gNy3A/SearchTimeline"

FEATURES = {
    "rweb_video_screen_enabled": True,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}

CRYPTO_ENTITIES = {
    "bitcoin": "bitcoin", "btc": "bitcoin", "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana", "cardano": "cardano", "ada": "cardano",
    "polygon": "polygon", "matic": "polygon", "chainlink": "chainlink", "link": "chainlink",
    "arbitrum": "arbitrum", "arb": "arbitrum", "optimism": "optimism", "op": "optimism",
    "sui": "sui", "pendle": "pendle", "base": "base", "near": "near",
    "avalanche": "avalanche", "avax": "avalanche", "cosmos": "cosmos", "atom": "cosmos",
}

ENTITY_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in sorted(CRYPTO_ENTITIES.keys(), key=len, reverse=True)) + r')\b',
    re.IGNORECASE
)


def extract_entities(text: str) -> list:
    if not text:
        return []
    return list(set(CRYPTO_ENTITIES[m.lower()] for m in ENTITY_PATTERN.findall(text.lower()) if m.lower() in CRYPTO_ENTITIES))


# ═══════════════════════════════════════════
# SESSION & AUTH
# ═══════════════════════════════════════════

async def get_session_cookies(db) -> Optional[tuple]:
    session = await db.twitter_sessions.find_one({"status": "OK"}, sort=[("lastSyncedAt", -1)])
    if not session or not session.get("encryptedCookies") or not COOKIE_ENC_KEY:
        return None
    try:
        parts = session["encryptedCookies"].split(':')
        if len(parts) != 3:
            return None
        iv = base64.b64decode(parts[0])
        tag = base64.b64decode(parts[1])
        ct = base64.b64decode(parts[2])
        cookies = json.loads(AESGCM(bytes.fromhex(COOKIE_ENC_KEY)).decrypt(iv, ct + tag, None).decode())
        if isinstance(cookies, dict):
            cookies = cookies.get('cookies', [cookies])
        auth_token = next((c["value"] for c in cookies if c.get("name") == "auth_token"), None)
        ct0 = next((c["value"] for c in cookies if c.get("name") == "ct0"), None)
        if not auth_token or not ct0:
            return None
        ua = session.get("userAgent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        return auth_token, ct0, ua, cookies
    except Exception as e:
        logger.error(f"Cookie decrypt error: {e}")
        return None


def _headers(cookies_list: list, ct0: str, ua: str) -> dict:
    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies_list)
    return {
        "authorization": f"Bearer {BEARER}",
        "cookie": cookie_str,
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "en",
        "user-agent": ua,
        "accept": "*/*",
        "referer": "https://x.com/",
    }


# ═══════════════════════════════════════════
# PROXY-AWARE REQUEST
# ═══════════════════════════════════════════

async def _proxy_request(db, url: str, params: dict, headers: dict, timeout: int = 20) -> dict:
    proxies = await db.proxy_pool.find({"enabled": True}, {"_id": 0}).sort([("priority", -1), ("error_count", 1)]).to_list(50)
    attempts = []

    for proxy in proxies:
        proxy_url = _build_proxy_url(proxy)
        if not proxy_url:
            continue
        pid = proxy.get("id", "unknown")
        try:
            start = time.time()
            async with httpx.AsyncClient(proxy=proxy_url, timeout=timeout, verify=False, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers, params=params)
                lat = int((time.time() - start) * 1000)

                if resp.status_code == 200:
                    await db.proxy_pool.update_one({"id": pid}, {"$set": {"healthy": True, "latency_ms": lat, "last_used": datetime.now(timezone.utc).isoformat()}, "$inc": {"success_count": 1}})
                    logger.info(f"[Proxy:{pid}] OK {url.split('/')[-1]} ({lat}ms)")
                    body = resp.json() if resp.content else {}
                    return {"ok": True, "data": body, "proxy": pid, "latency": lat}

                if resp.status_code in (401, 403):
                    return {"ok": False, "error": "AUTH_EXPIRED", "proxy": pid, "status": resp.status_code}

                if resp.status_code == 429:
                    attempts.append({"proxy": pid, "error": "RATE_LIMITED"})
                    await db.proxy_pool.update_one({"id": pid}, {"$set": {"last_error": "Rate limited"}, "$inc": {"error_count": 1}})
                    continue

                attempts.append({"proxy": pid, "status": resp.status_code})
                await db.proxy_pool.update_one({"id": pid}, {"$inc": {"error_count": 1}})
                continue

        except (httpx.TimeoutException, httpx.ConnectError, httpx.ProxyError) as e:
            attempts.append({"proxy": pid, "error": type(e).__name__})
            await db.proxy_pool.update_one({"id": pid}, {"$set": {"healthy": False}, "$inc": {"error_count": 1}})
            continue

    # Direct fallback
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                return {"ok": True, "data": resp.json() if resp.content else {}, "proxy": None}
            return {"ok": False, "error": f"HTTP_{resp.status_code}", "status": resp.status_code, "attempts": attempts}
    except Exception as e:
        return {"ok": False, "error": str(e), "attempts": attempts}


def _build_proxy_url(proxy: dict) -> str:
    server = proxy.get("server", "")
    if not server:
        return ""
    if "://" not in server:
        server = f"http://{server}"
    if proxy.get("username"):
        proto, rest = server.split("://", 1)
        return f"{proto}://{proxy['username']}:{proxy.get('password', '')}@{rest}"
    return server


# ═══════════════════════════════════════════
# MODE A: ACCOUNT → UserTweets
# ═══════════════════════════════════════════

async def twitter_typeahead(db, query: str) -> dict:
    creds = await get_session_cookies(db)
    if not creds:
        return {"ok": False, "error": "NO_SESSION", "users": []}

    _, ct0, ua, all_cookies = creds
    headers = _headers(all_cookies, ct0, ua)

    result = await _proxy_request(db, f"{API_BASE}/search/typeahead.json", {
        "q": query, "result_type": "events,users,topics", "count": "8",
    }, headers)

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", ""), "users": []}

    data = result["data"]
    users = []
    for u in data.get("users", []):
        avatar = (u.get("profile_image_url_https", "") or u.get("profile_image_url", "")).replace("_normal", "_400x400")
        users.append({
            "id": u.get("id_str", ""),
            "username": u.get("screen_name", ""),
            "name": u.get("name", ""),
            "avatar": avatar,
            "verified": u.get("verified", False) or u.get("is_blue_verified", False),
            "followers": u.get("followers_count", 0),
        })

    topics = [t.get("topic", "") for t in data.get("topics", []) if t.get("topic")]
    return {"ok": True, "users": users, "topics": topics, "proxy": result.get("proxy")}


async def twitter_user_tweets(db, username: str, count: int = 20) -> dict:
    creds = await get_session_cookies(db)
    if not creds:
        return {"ok": False, "error": "NO_SESSION", "tweets": []}

    _, ct0, ua, all_cookies = creds
    headers = _headers(all_cookies, ct0, ua)

    user_vars = json.dumps({"screen_name": username.lstrip("@"), "withSafetyModeUserFields": True})
    user_feats = json.dumps({"responsive_web_graphql_timeline_navigation_enabled": True, "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False, "verified_phone_label_enabled": False, "rweb_tipjar_consumption_enabled": True})
    user_result = await _proxy_request(db, f"{GQL_BASE}/{USER_OP}", {"variables": user_vars, "features": user_feats}, headers)

    if not user_result.get("ok"):
        return {"ok": False, "error": user_result.get("error", "USER_LOOKUP_FAILED"), "tweets": []}

    user_r = user_result["data"].get("data", {}).get("user", {}).get("result", {})
    user_id = user_r.get("rest_id")
    if not user_id:
        return {"ok": False, "error": "USER_NOT_FOUND", "tweets": []}

    ul = user_r.get("legacy", {})
    profile = {
        "id": user_id,
        "username": ul.get("screen_name", username),
        "name": ul.get("name", ""),
        "avatar": (ul.get("profile_image_url_https", "") or "").replace("_normal", "_400x400"),
        "verified": user_r.get("is_blue_verified", False),
        "followers": ul.get("followers_count", 0),
        "description": ul.get("description", ""),
    }

    tweet_vars = json.dumps({"userId": user_id, "count": count, "includePromotedContent": False, "withQuickPromoteEligibilityTweetFields": True, "withVoice": True, "withV2Timeline": True})
    tweets_result = await _proxy_request(db, f"{GQL_BASE}/{TWEETS_OP}", {"variables": tweet_vars, "features": json.dumps(FEATURES)}, headers)

    if not tweets_result.get("ok"):
        return {"ok": False, "error": tweets_result.get("error"), "tweets": [], "profile": profile}

    tweets = _parse_timeline_tweets(tweets_result["data"], source_type="user_timeline")
    stored = await _store_tweets(db, tweets, f"@{username.lstrip('@')}")
    logger.info(f"@{username}: {len(tweets)} tweets, {stored} new")
    return {"ok": True, "tweets": tweets, "stored": stored, "profile": profile, "source": "api", "proxy": tweets_result.get("proxy")}


# ═══════════════════════════════════════════
# MODE B: KEYWORD → SearchTimeline (API) → fallback Playwright
# ═══════════════════════════════════════════

async def search_tweets(db, query: str, count: int = 20) -> dict:
    """
    Единая точка входа для keyword search.
    1. Пробует SearchTimeline через GraphQL API (cookies + proxy)
    2. При 404/ошибке → fallback на Playwright browser
    3. Нормализация → store → return
    """
    # Attempt 1: SearchTimeline API
    api_result = await _search_timeline_api(db, query, count)
    if api_result.get("ok") and api_result.get("tweets"):
        stored = await _store_tweets(db, api_result["tweets"], query)
        logger.info(f"SearchTimeline API: '{query}' → {len(api_result['tweets'])} tweets, {stored} new")
        return {
            "ok": True,
            "tweets": api_result["tweets"],
            "stored": stored,
            "source": "search_api",
            "proxy": api_result.get("proxy"),
        }

    api_error = api_result.get("error", "UNKNOWN")
    logger.warning(f"SearchTimeline API failed for '{query}': {api_error} → falling back to Playwright")

    # Attempt 2: Playwright browser fallback
    pw_result = await _search_via_browser(db, query, count)
    if pw_result.get("ok") and pw_result.get("tweets"):
        stored = await _store_tweets(db, pw_result["tweets"], query)
        logger.info(f"Playwright search: '{query}' → {len(pw_result['tweets'])} tweets, {stored} new")
        return {
            "ok": True,
            "tweets": pw_result["tweets"],
            "stored": stored,
            "source": "playwright",
        }

    pw_error = pw_result.get("error", "UNKNOWN")
    logger.error(f"Both search methods failed for '{query}': API={api_error}, Playwright={pw_error}")

    # Last resort: DB cached results
    db_tweets = await _search_db_cached(db, query, count)
    return {
        "ok": len(db_tweets) > 0,
        "tweets": db_tweets,
        "source": "database_cache",
        "api_error": api_error,
        "pw_error": pw_error,
    }


async def _search_timeline_api(db, query: str, count: int = 20) -> dict:
    """SearchTimeline через GraphQL — cookies + proxy"""
    creds = await get_session_cookies(db)
    if not creds:
        return {"ok": False, "error": "NO_SESSION"}

    _, ct0, ua, all_cookies = creds
    headers = _headers(all_cookies, ct0, ua)

    variables = json.dumps({
        "rawQuery": query,
        "count": count,
        "querySource": "typed_query",
        "product": "Latest",
    })

    result = await _proxy_request(db, f"{GQL_BASE}/{SEARCH_OP}", {
        "variables": variables,
        "features": json.dumps(FEATURES),
    }, headers)

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "API_FAILED"), "status": result.get("status")}

    tweets = _parse_search_results(result["data"])
    return {"ok": True, "tweets": tweets, "proxy": result.get("proxy")}


async def _search_via_browser(db, query: str, count: int = 20) -> dict:
    """Playwright fallback: headless Chrome → twitter.com/search → scroll → extract"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"ok": False, "error": "PLAYWRIGHT_NOT_INSTALLED"}

    # Get cookies for auth
    creds = await get_session_cookies(db)
    browser_cookies = []
    if creds:
        _, ct0, ua, all_cookies = creds
        for c in all_cookies:
            browser_cookies.append({
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ".x.com"),
                "path": c.get("path", "/"),
            })

    tweets = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(
                user_agent=creds[2] if creds else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
            )

            if browser_cookies:
                await context.add_cookies(browser_cookies)

            page = await context.new_page()

            # Intercept XHR responses to capture tweet data from API calls
            captured_tweets = []

            async def handle_response(response):
                try:
                    url = response.url
                    if "SearchTimeline" in url or "adaptive.json" in url:
                        if response.status == 200:
                            data = await response.json()
                            parsed = _parse_search_results(data)
                            captured_tweets.extend(parsed)
                except Exception:
                    pass

            page.on("response", handle_response)

            search_url = f"https://x.com/search?q={query}&src=typed_query&f=live"
            logger.info(f"Playwright: navigating to {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)

            # Scroll to load more tweets
            scroll_count = min(3, max(1, count // 10))
            for i in range(scroll_count):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                await page.wait_for_timeout(2000)

            # If XHR capture got tweets, use those (structured data)
            if captured_tweets:
                tweets = captured_tweets[:count]
                logger.info(f"Playwright XHR capture: {len(tweets)} tweets")
            else:
                # DOM fallback: extract tweets from rendered page
                tweets = await _extract_tweets_from_dom(page, count)
                logger.info(f"Playwright DOM extraction: {len(tweets)} tweets")

            await browser.close()

    except Exception as e:
        logger.error(f"Playwright search error: {e}")
        return {"ok": False, "error": str(e)}

    return {"ok": len(tweets) > 0, "tweets": tweets}


async def _extract_tweets_from_dom(page, count: int) -> list:
    """Extract tweets from rendered Twitter DOM"""
    tweets = []
    try:
        articles = await page.query_selector_all('article[data-testid="tweet"]')
        for article in articles[:count]:
            try:
                # Username
                user_link = await article.query_selector('div[data-testid="User-Name"] a[role="link"]')
                username = ""
                display_name = ""
                if user_link:
                    href = await user_link.get_attribute("href") or ""
                    username = href.strip("/").split("/")[-1] if href else ""
                name_el = await article.query_selector('div[data-testid="User-Name"] a span')
                if name_el:
                    display_name = (await name_el.inner_text()).strip()

                # Tweet text
                text_el = await article.query_selector('div[data-testid="tweetText"]')
                text = (await text_el.inner_text()).strip() if text_el else ""

                if not text and not username:
                    continue

                # Engagement metrics
                likes = await _get_metric(article, 'button[data-testid="like"]')
                reposts = await _get_metric(article, 'button[data-testid="retweet"]')
                replies = await _get_metric(article, 'button[data-testid="reply"]')

                # Avatar
                avatar_el = await article.query_selector('div[data-testid="Tweet-User-Avatar"] img')
                avatar = (await avatar_el.get_attribute("src") or "").replace("_normal", "_400x400") if avatar_el else ""

                # Time
                time_el = await article.query_selector('time')
                tweeted_at = await time_el.get_attribute("datetime") if time_el else ""

                tweet_id = f"pw_{username}_{int(time.time())}_{len(tweets)}"

                tweets.append({
                    "tweetId": tweet_id,
                    "text": text,
                    "username": username,
                    "displayName": display_name,
                    "likes": likes,
                    "reposts": reposts,
                    "replies": replies,
                    "views": 0,
                    "tweetedAt": tweeted_at,
                    "author": {
                        "username": username,
                        "name": display_name,
                        "avatar": avatar,
                        "verified": False,
                        "followers": 0,
                    },
                })
            except Exception:
                continue
    except Exception as e:
        logger.error(f"DOM extraction error: {e}")
    return tweets


async def _get_metric(article, selector: str) -> int:
    try:
        el = await article.query_selector(selector)
        if el:
            txt = (await el.inner_text()).strip()
            if not txt:
                return 0
            txt = txt.replace(",", "").strip()
            if txt.endswith("K"):
                return int(float(txt[:-1]) * 1000)
            if txt.endswith("M"):
                return int(float(txt[:-1]) * 1000000)
            return int(txt) if txt.isdigit() else 0
    except Exception:
        pass
    return 0


async def _search_db_cached(db, query: str, count: int) -> list:
    """Fallback: поиск в кешированных твитах"""
    filter_q = {"$or": [
        {"text": {"$regex": re.escape(query), "$options": "i"}},
        {"keyword": {"$regex": re.escape(query), "$options": "i"}},
        {"entities_mentioned": query.lower()},
    ]}
    cursor = db.twitter_results.find(filter_q, {"_id": 0}).sort("parsedAt", -1).limit(count)
    tweets = []
    async for t in cursor:
        author = t.get("author", {})
        tweets.append({
            "tweetId": t.get("tweetId", ""),
            "text": t.get("text", ""),
            "username": t.get("username", ""),
            "displayName": t.get("displayName", "") or author.get("name", ""),
            "likes": t.get("likes", 0),
            "reposts": t.get("reposts", 0),
            "replies": t.get("replies", 0),
            "views": t.get("views", 0),
            "tweetedAt": str(t.get("tweetedAt", "")),
            "avatar": author.get("avatar", ""),
            "verified": author.get("verified", False),
            "followers": author.get("followers", 0),
        })
    return tweets


# ═══════════════════════════════════════════
# UNIFIED ENTRY POINT — routes @account to Mode A, keywords to Mode B
# ═══════════════════════════════════════════

async def twitter_search(db, query: str, count: int = 20) -> dict:
    """
    Единая точка входа:
      @username → Mode A (UserTweets)
      keyword  → Mode B (SearchTimeline → Playwright fallback)
    """
    if query.startswith("@"):
        return await twitter_user_tweets(db, query.lstrip("@"), count)
    return await search_tweets(db, query, count)


# ═══════════════════════════════════════════
# TWEET PARSING — unified for all sources
# ═══════════════════════════════════════════

def _extract_tweet(ic: dict) -> Optional[dict]:
    try:
        tr = ic.get("tweet_results", {}).get("result", {})
        if not tr:
            return None
        if tr.get("__typename") == "TweetWithVisibilityResults":
            tr = tr.get("tweet", {})
        legacy = tr.get("legacy", {})
        core = tr.get("core", {}).get("user_results", {}).get("result", {})
        ul = core.get("legacy", {})
        tid = legacy.get("id_str") or tr.get("rest_id", "")
        text = legacy.get("full_text", "")
        if not tid or not text:
            return None
        username = ul.get("screen_name", "")
        display_name = ul.get("name", "")
        avatar = (ul.get("profile_image_url_https", "") or "").replace("_normal", "_400x400")
        verified = core.get("is_blue_verified", False)
        followers = ul.get("followers_count", 0)
        user_id = core.get("rest_id", "")
        views = 0
        vd = tr.get("views", {})
        if vd and vd.get("count"):
            try:
                views = int(vd["count"])
            except (ValueError, TypeError):
                pass
        return {
            "tweetId": tid, "text": text,
            "username": username, "displayName": display_name,
            "likes": legacy.get("favorite_count", 0), "reposts": legacy.get("retweet_count", 0),
            "replies": legacy.get("reply_count", 0), "views": views,
            "tweetedAt": legacy.get("created_at", ""),
            "author": {"id": user_id, "username": username,
                "name": display_name, "avatar": avatar,
                "verified": verified, "followers": followers},
        }
    except Exception:
        return None


def _parse_timeline_tweets(data: dict, source_type: str = "user_timeline") -> list:
    """Парсинг твитов из UserTweets / timeline response"""
    tweets = []
    try:
        result = data.get("data", {}).get("user", {}).get("result", {})
        timeline_obj = result.get("timeline_v2", result.get("timeline", {}))
        instructions = timeline_obj.get("timeline", {}).get("instructions", [])
        for instr in instructions:
            for entry in instr.get("entries", []):
                content = entry.get("content", {})
                ic = content.get("itemContent", {})
                if ic:
                    t = _extract_tweet(ic)
                    if t:
                        tweets.append(t)
                for item in content.get("items", []):
                    ic2 = item.get("item", {}).get("itemContent", {})
                    t = _extract_tweet(ic2)
                    if t:
                        tweets.append(t)
    except Exception as e:
        logger.error(f"Timeline parse error: {e}")
    return tweets


def _parse_search_results(data: dict) -> list:
    """Парсинг твитов из SearchTimeline response"""
    tweets = []
    try:
        instructions = (
            data.get("data", {}).get("search_by_raw_query", {}).get("search_timeline", {}).get("timeline", {}).get("instructions", [])
            or data.get("globalObjects", {}) and [data]  # adaptive.json format
            or []
        )

        # GraphQL format
        for instr in instructions:
            if isinstance(instr, dict):
                for entry in instr.get("entries", []):
                    content = entry.get("content", {})
                    ic = content.get("itemContent", {})
                    if ic:
                        t = _extract_tweet(ic)
                        if t:
                            tweets.append(t)
                    for item in content.get("items", []):
                        ic2 = item.get("item", {}).get("itemContent", {})
                        t = _extract_tweet(ic2)
                        if t:
                            tweets.append(t)

        # adaptive.json format (legacy)
        if not tweets and "globalObjects" in data:
            go = data["globalObjects"]
            users_map = go.get("users", {})
            for tid, tw in go.get("tweets", {}).items():
                uid = tw.get("user_id_str", "")
                user = users_map.get(uid, {})
                tweets.append({
                    "tweetId": tid,
                    "text": tw.get("full_text", ""),
                    "username": user.get("screen_name", ""),
                    "displayName": user.get("name", ""),
                    "likes": tw.get("favorite_count", 0),
                    "reposts": tw.get("retweet_count", 0),
                    "replies": tw.get("reply_count", 0),
                    "views": 0,
                    "tweetedAt": tw.get("created_at", ""),
                    "author": {
                        "id": uid,
                        "username": user.get("screen_name", ""),
                        "name": user.get("name", ""),
                        "avatar": (user.get("profile_image_url_https", "") or "").replace("_normal", "_400x400"),
                        "verified": user.get("verified", False),
                        "followers": user.get("followers_count", 0),
                    },
                })
    except Exception as e:
        logger.error(f"Search results parse error: {e}")
    return tweets


# ═══════════════════════════════════════════
# STORAGE — unified for all pipelines
# ═══════════════════════════════════════════

async def _store_tweets(db, tweets: list, query: str) -> int:
    stored = 0
    for tweet in tweets:
        entities = extract_entities(tweet["text"])
        doc = {
            "ownerType": "SYSTEM", "source": "LIVE", "query": query,
            "tweetId": tweet["tweetId"], "text": tweet["text"],
            "username": tweet["username"], "displayName": tweet.get("displayName", ""),
            "likes": tweet.get("likes", 0), "reposts": tweet.get("reposts", 0),
            "replies": tweet.get("replies", 0), "views": tweet.get("views", 0),
            "author": tweet.get("author", {}), "keyword": query,
            "tweetedAt": tweet.get("tweetedAt"),
            "createdAt": datetime.now(timezone.utc), "parsedAt": datetime.now(timezone.utc),
            "entities_mentioned": entities, "entity_count": len(entities),
        }
        res = await db.twitter_results.update_one({"tweetId": tweet["tweetId"]}, {"$set": doc}, upsert=True)
        if res.upserted_id:
            stored += 1
    return stored
