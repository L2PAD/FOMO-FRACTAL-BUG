"""
Prediction Decision Engine — final action from edge + probability.

Outputs: YES / NO / WAIT / AVOID with confidence and reasoning.
"""


def make_decision(edge: dict, probability: dict) -> dict:
    """
    Compute final prediction decision.

    Thresholds:
      - |net_edge| > 0.10 + confidence > 0.5 → strong signal
      - |net_edge| > 0.05 + confidence > 0.4 → moderate signal
      - |net_edge| < 0.03 → no edge → AVOID
      - else → WAIT

    Args:
        edge: output from edge_engine.compute_edge()
        probability: output from probability_engine.compute_probability()

    Returns:
        dict with action, confidence, edge, reasoning
    """
    net_edge = edge.get("net_edge", 0)
    conf = probability.get("confidence", 0)
    reasoning = []

    abs_edge = abs(net_edge)
    is_positive = net_edge > 0

    # Strong signal
    if abs_edge > 0.10 and conf > 0.5:
        action = "YES" if is_positive else "NO"
        reasoning.append(f"Strong edge: {net_edge:+.1%}")
        reasoning.append(f"Confidence: {conf:.0%}")
        return _result(action, conf, net_edge, reasoning)

    # Moderate signal
    if abs_edge > 0.05 and conf > 0.4:
        action = "YES" if is_positive else "NO"
        reasoning.append(f"Moderate edge: {net_edge:+.1%}")
        return _result(action, conf * 0.8, net_edge, reasoning)

    # No edge
    if abs_edge < 0.03:
        reasoning.append(f"No meaningful edge: {net_edge:+.1%}")
        return _result("AVOID", conf, net_edge, reasoning)

    # Weak / uncertain
    reasoning.append(f"Weak signal: edge={net_edge:+.1%}, conf={conf:.0%}")
    return _result("WAIT", conf, net_edge, reasoning)


def _result(action: str, confidence: float, edge: float, reasoning: list) -> dict:
    return {
        "action": action,
        "confidence": round(confidence, 4),
        "edge": round(edge, 4),
        "reasoning": reasoning,
    }
