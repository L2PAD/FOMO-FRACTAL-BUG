"""
Execution Layer Adapter — Python bridge to Node.js Execution Layer / Microstructure service.

Provides:
  - analyze(case_data) → full execution assessment for a single case
  - batch_analyze(cases) → batch execution analysis for all pipeline cases
"""
import os
import httpx

_NODE_URL = os.environ.get("NODE_BACKEND_URL", "http://127.0.0.1:8003")
_TIMEOUT = 15.0


async def analyze(case_data: dict) -> dict | None:
    """Full execution analysis for a single case."""
    try:
        payload = _build_payload(case_data)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/execution-layer/analyze",
                json=payload,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("execution")
    except Exception:
        pass
    return None


async def batch_analyze(cases: list[dict]) -> dict:
    """Batch execution analysis for all pipeline cases."""
    try:
        batch_payload = []
        for c in cases:
            p = _build_payload(c)
            p["marketId"] = c.get("market_id", "")
            batch_payload.append(p)

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_NODE_URL}/api/execution-layer/analyze/batch",
                json={"cases": batch_payload},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("results", {})
    except Exception:
        pass
    return {}


def _build_payload(case_data: dict) -> dict:
    """Extract execution-relevant fields from a pipeline case object."""
    analysis = case_data.get("analysis", {})
    repricing = case_data.get("repricing", {})
    social = case_data.get("socialIntel", {})
    project = case_data.get("projectIntel", {})
    market_stage = case_data.get("market_stage", "")

    return {
        "spread": case_data.get("spread", case_data.get("pricing", {}).get("spread", 0)),
        "liquidity": case_data.get("liquidity", 0),
        "volume24h": case_data.get("volume", 0),
        "edge": analysis.get("net_edge", 0),
        "fairProb": analysis.get("fair_prob", 0.5),
        "marketProb": analysis.get("market_prob", 0.5),
        "confidence": analysis.get("model_confidence", 0.5),
        "alignment": analysis.get("alignment_score", 0.5),
        "repricingState": repricing.get("repricing_state", "stalled"),
        "marketStage": market_stage if isinstance(market_stage, str) else str(market_stage),
        "socialSaturation": social.get("saturation", social.get("saturationScore", 0)),
        "socialLifecycle": social.get("lifecycle", social.get("lifecyclePhase", None)),
        "projectVerdict": project.get("verdict", None),
        "positionOversized": False,
    }
