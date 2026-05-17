"""
Token Intelligence Context — Single aggregated endpoint
=========================================================
Replaces 6 parallel frontend calls with 1 call.
Endpoint: /api/onchain/assets/context
"""

from .narrative import get_narrative
from .brain import get_brain_signals
from .patterns import get_patterns
from .map_service import get_map_data
from .top_actors import get_top_actors
from .signals_engine import get_signals
from .service import cache_get, cache_set


def get_token_intelligence_context(chain_id: int = 1, window: str = "24h") -> dict:
    ck = f"token_intel_ctx:{chain_id}:{window}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    narrative = get_narrative(chain_id=chain_id, window=window)
    brain = get_brain_signals(chain_id=chain_id, window=window, limit=20)
    signals = get_signals(chain_id=chain_id, window=window, limit=30)
    patterns = get_patterns(chain_id=chain_id, window=window, limit=20)
    map_data = get_map_data(chain_id=chain_id, window=window, limit=30)
    actors = get_top_actors(chain_id=chain_id, window=window, limit=20)

    result = {
        "narrative": narrative,
        "token_scores": brain,
        "signals": signals,
        "patterns": patterns,
        "routes": map_data.get("routes", []),
        "destination_heat": map_data.get("destination_heat", []),
        "actors": actors,
    }
    cache_set(ck, result)
    return result
