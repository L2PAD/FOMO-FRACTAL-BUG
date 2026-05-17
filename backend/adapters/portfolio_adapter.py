"""
Portfolio Brain Adapter — bridges Python prediction pipeline to Node.js Stage 7.

Calls the Node.js Portfolio Brain service to get:
  - Factor profiles
  - Cluster overlap assessment
  - Correlation penalties
  - Risk budget evaluation
  - Final portfolio-adjusted sizing

Python is DATA PROVIDER only. Node.js is the DECISION MAKER.
"""
import httpx
import logging

logger = logging.getLogger("prediction.portfolio")

NODE_PORTFOLIO_URL = "http://localhost:8003/api/prediction-portfolio"


async def assess_candidate(case_data: dict) -> dict:
    """
    Send a single case to Portfolio Brain for assessment.
    Returns portfolio assessment dict.
    """
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{NODE_PORTFOLIO_URL}/assess",
                json=case_data,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data["assessment"]
    except Exception as e:
        logger.debug(f"Portfolio assess unavailable: {e}")

    return _empty_assessment()


async def assess_batch(cases: list[dict]) -> dict[str, dict]:
    """
    Send batch of cases to Portfolio Brain.
    Returns {market_id: assessment}.
    """
    try:
        payload = {"cases": cases}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{NODE_PORTFOLIO_URL}/batch", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("results", {})
    except Exception as e:
        logger.debug(f"Portfolio batch unavailable: {e}")

    return {}


async def get_exposure() -> dict:
    """Get current portfolio exposure summary."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{NODE_PORTFOLIO_URL}/exposure")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data["exposure"]
    except Exception as e:
        logger.debug(f"Portfolio exposure unavailable: {e}")

    return {"totalExposure": 0, "byAsset": {}, "byTheme": {}, "byEntity": {},
            "byResolution": {}, "byCatalyst": {}, "positionCount": 0}


def _empty_assessment() -> dict:
    return {
        "allowed": True,
        "capped": False,
        "blocked": False,
        "overlapScore": 0,
        "correlationPenalty": 0,
        "budgetPenalty": 0,
        "adjustedSizeFraction": 0,
        "adjustedSize": "NONE",
        "reasons": [],
    }
