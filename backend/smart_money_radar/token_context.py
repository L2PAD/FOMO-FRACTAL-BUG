"""
Token Context Service
======================
Aggregates all smart money data for a single token into one response.
Endpoint: /api/onchain/smart-money/token/{symbol}/context
"""

from .brain import get_brain_signals
from .patterns import get_patterns
from .narrative import get_narrative
from .map_service import get_map_data
from .top_actors import get_top_actors
from .signals_engine import get_signals
from .service import cache_get, cache_set


def get_token_context(symbol: str, chain_id: int = 1, window: str = "24h") -> dict:
    sym_upper = symbol.upper()
    ck = f"token_ctx:{sym_upper}:{chain_id}:{window}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    brain = get_brain_signals(chain_id=chain_id, window=window, limit=20)
    patterns = get_patterns(chain_id=chain_id, window=window, limit=20)
    narrative = get_narrative(chain_id=chain_id, window=window)
    map_data = get_map_data(chain_id=chain_id, window=window, limit=30)
    actors = get_top_actors(chain_id=chain_id, window=window, limit=20)
    signals = get_signals(chain_id=chain_id, window=window, limit=30)

    # Token score from brain
    token_score = None
    for b in brain:
        if b["token"].upper() == sym_upper:
            token_score = b
            break

    # All brain scores for relative ranking
    all_scores = sorted(brain, key=lambda x: x["alpha_score"], reverse=True)
    rank = next((i + 1 for i, b in enumerate(all_scores) if b["token"].upper() == sym_upper), None)

    # Patterns involving this token
    token_patterns = [p for p in patterns if
                      p.get("token", "").upper() == sym_upper or
                      p.get("from_token", "").upper() == sym_upper or
                      p.get("to_token", "").upper() == sym_upper]

    # Signals for this token
    token_signals = [s for s in signals if s.get("token", "").upper() == sym_upper]

    # Routes involving this token
    all_routes = map_data.get("routes", [])
    token_routes = [r for r in all_routes if
                    r.get("token", "").upper() == sym_upper or
                    r.get("from_token", "").upper() == sym_upper or
                    r.get("to_token", "").upper() == sym_upper]

    # Flow from destination heat
    dest_heat = map_data.get("destination_heat", [])
    token_flow = next((h for h in dest_heat if h["token"].upper() == sym_upper), None)
    total_abs_flow = sum(abs(h["net_flow_usd"]) for h in dest_heat)
    flow_share = (abs(token_flow["net_flow_usd"]) / total_abs_flow * 100) if token_flow and total_abs_flow > 0 else 0

    # Actors exposed to this token
    token_actors = [a for a in actors if sym_upper in [t.upper() for t in a.get("tokens", [])]]

    # Related tokens: tokens that co-appear in rotation patterns with this token
    related = set()
    for p in patterns:
        if p.get("from_token", "").upper() == sym_upper and p.get("to_token"):
            related.add(p["to_token"])
        elif p.get("to_token", "").upper() == sym_upper and p.get("from_token"):
            related.add(p["from_token"])
    # Also add tokens traded by the same actors
    for a in token_actors:
        for t in a.get("tokens", []):
            if t.upper() != sym_upper:
                related.add(t)
    related_tokens = list(related)[:8]

    # Related token scores
    related_scores = [b for b in brain if b["token"] in related_tokens]

    result = {
        "symbol": sym_upper,
        "score": token_score,
        "rank": rank,
        "total_tokens": len(all_scores),
        "patterns": token_patterns,
        "signals": token_signals,
        "routes": token_routes[:10],
        "flow": {
            "net_flow_usd": token_flow["net_flow_usd"] if token_flow else 0,
            "share_pct": round(flow_share, 1),
        },
        "actors": token_actors[:8],
        "related_tokens": related_scores[:6],
        "narrative": narrative,
    }
    cache_set(ck, result)
    return result
