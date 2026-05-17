"""
Execution Engine — translates sizing decisions into execution hints.

Converts position size and market conditions into:
  - executable: bool
  - entry type (market/limit/wait)
  - side (YES/NO/NONE)
  - size_fraction
  - execution note
"""


def build_plan(recommendation: dict, sizing: dict) -> dict:
    """
    Build execution plan from recommendation and sizing.

    Returns:
        dict with executable, entry, note
    """
    if not sizing.get("allowed"):
        return {
            "executable": False,
            "entry": None,
            "note": "Do not enter this market now",
        }

    action = recommendation.get("action", "AVOID")
    exec_mode = sizing.get("execution_mode", "WAIT")

    entry_type = "place_limit_order" if exec_mode == "LIMIT" else "enter_market"
    side = _side_from_action(action)

    if exec_mode == "WAIT":
        return {
            "executable": False,
            "entry": None,
            "note": "Monitor for better entry conditions",
        }

    return {
        "executable": True,
        "entry": {
            "type": entry_type,
            "side": side,
            "size_fraction": sizing.get("size_fraction", 0),
            "max_slippage_bps": sizing.get("max_slippage_bps", 100),
        },
        "note": _build_note(sizing, recommendation),
    }


def _side_from_action(action: str) -> str:
    if action.startswith("YES"):
        return "YES"
    if action.startswith("NO"):
        return "NO"
    return "NONE"


def _build_note(sizing: dict, recommendation: dict) -> str:
    mode = sizing.get("execution_mode", "WAIT")
    if mode == "LIMIT":
        return "Use passive entry due to spread/pricing conditions"

    risk_flags = sizing.get("risk_flags", [])
    if "wide_spread" in risk_flags:
        return "Watch spread before executing"
    if "pricing_not_ideal" in risk_flags:
        return "Entry acceptable but price may already reflect some thesis"

    return "Entry is acceptable at current market conditions"
