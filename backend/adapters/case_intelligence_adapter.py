"""
Case Intelligence Adapter — bridges Python prediction pipeline to Node.js Case Intelligence Engine.

Calls the Node.js reasoning core to get Decision Memos for markets.
Python is DATA PROVIDER only. Node.js does the reasoning.
"""
import httpx
import logging

logger = logging.getLogger("prediction.case_intelligence")

NODE_CI_URL = "http://localhost:8003/api/case-intelligence"


async def analyze_case(case_data: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(f"{NODE_CI_URL}/analyze", json=case_data)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return {
                        "memo": data.get("memo"),
                        "event": data.get("event"),
                        "evidenceStats": data.get("evidenceStats"),
                        "thesis": data.get("thesis"),
                        "gap": data.get("gap"),
                        "risks": data.get("risks"),
                    }
    except Exception as e:
        logger.debug(f"Case intelligence unavailable: {e}")
    return {}


async def analyze_batch(cases: list[dict]) -> dict[str, dict]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{NODE_CI_URL}/batch", json={"cases": cases})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("results", {})
    except Exception as e:
        logger.debug(f"Case intelligence batch unavailable: {e}")
    return {}
