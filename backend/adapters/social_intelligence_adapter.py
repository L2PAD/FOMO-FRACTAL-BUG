"""
Social Intelligence Adapter — bridges Python pipeline to Node.js Social Intelligence 2.0.

Python is DATA PROVIDER only. Node.js does the narrative analysis.
"""
import httpx
import logging

logger = logging.getLogger("prediction.social_intelligence")

NODE_SI_URL = "http://localhost:8003/api/social-intelligence"


async def analyze_social(asset: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(f"{NODE_SI_URL}/{asset}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("socialIntel", {})
    except Exception as e:
        logger.debug(f"Social intelligence unavailable: {e}")
    return {}


async def analyze_social_batch(assets: list[str]) -> dict[str, dict]:
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(f"{NODE_SI_URL}/batch", json={"assets": assets})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("results", {})
    except Exception as e:
        logger.debug(f"Social intelligence batch unavailable: {e}")
    return {}
