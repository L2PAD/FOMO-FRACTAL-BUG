"""Macro V2 pure math — no I/O, no state."""
import math
from .config import (
    CPI_WEIGHTS, RISKOFF_WEIGHTS, REGIME_WEIGHTS,
    MACRO_MULT_RISKOFF_COEFF, MACRO_MULT_GREED_COEFF,
    MACRO_MULT_FLOOR, MACRO_MULT_CEILING, EPSILON,
)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def softmax(scores, temp=1.0):
    m = max(scores.values())
    exps = {k: math.exp((v - m) / max(temp, EPSILON)) for k, v in scores.items()}
    s = sum(exps.values()) + EPSILON
    return {k: round(v / s, 4) for k, v in exps.items()}


def log_return(p_now, p_prev):
    return math.log(p_now / max(p_prev, EPSILON))


def zscore(x, mean, std):
    return (x - mean) / (std + EPSILON)


def fg_inverted(fg):
    """Fear&Greed → inverted scale: FG=0 → +2, FG=100 → -2."""
    return (50.0 - fg) / 25.0


def extreme_fear_prob(fg):
    return sigmoid((20.0 - fg) / 4.0)


def extreme_greed_prob(fg):
    return sigmoid((fg - 80.0) / 4.0)


def compute_cpi(z_db7, z_ds7, z_rbtc7, z_altvsbtc7):
    """Capital Pressure Index + per-driver contributions."""
    drivers = {
        "btc_dom_7d": CPI_WEIGHTS["btc_dom_7d"] * z_db7,
        "stable_dom_7d": CPI_WEIGHTS["stable_dom_7d"] * z_ds7,
        "btc_ret_7d": CPI_WEIGHTS["btc_ret_7d"] * z_rbtc7,
        "alt_vs_btc_7d": CPI_WEIGHTS["alt_vs_btc_7d"] * z_altvsbtc7,
    }
    return sum(drivers.values()), drivers


def compute_riskoff_prob(z_ds7, z_fg_inv, z_vol7, z_neg_rbtc7):
    w = RISKOFF_WEIGHTS
    x = w["stable_dom"] * z_ds7 + w["fg_inv"] * z_fg_inv + w["vol"] * z_vol7 + w["neg_btc_ret"] * z_neg_rbtc7
    return sigmoid(x)


def compute_macro_mult(riskoff, ex_greed):
    return clamp(
        1.0 - MACRO_MULT_RISKOFF_COEFF * riskoff - MACRO_MULT_GREED_COEFF * ex_greed,
        MACRO_MULT_FLOOR,
        MACRO_MULT_CEILING,
    )


def compute_regime_scores(z_db7, z_ds7, z_rbtc7, z_altvsbtc7, riskoff, cpi, extreme_fear=0.0):
    """Raw regime scores before softmax.
    
    Applies behavioral penalty: Extreme Fear suppresses Alt Rotation
    and boosts Capital Exit (market psychology override).
    """
    w = REGIME_WEIGHTS
    scores = {
        "FLIGHT_TO_BTC": (
            w["FLIGHT_TO_BTC"]["z_db7"] * z_db7
            + w["FLIGHT_TO_BTC"]["z_rbtc7"] * z_rbtc7
            + w["FLIGHT_TO_BTC"]["riskoff"] * riskoff
            + w["FLIGHT_TO_BTC"]["z_altvsbtc7"] * z_altvsbtc7
        ),
        "ALT_ROTATION": (
            w["ALT_ROTATION"]["z_db7"] * z_db7
            + w["ALT_ROTATION"]["riskoff"] * riskoff
            + w["ALT_ROTATION"]["z_altvsbtc7"] * z_altvsbtc7
            + w["ALT_ROTATION"]["z_ds7"] * z_ds7
        ),
        "CAPITAL_EXIT": (
            w["CAPITAL_EXIT"]["z_ds7"] * z_ds7
            + w["CAPITAL_EXIT"]["riskoff"] * riskoff
            + w["CAPITAL_EXIT"]["z_rbtc7"] * z_rbtc7
        ),
        "NEUTRAL": w["NEUTRAL"]["abs_cpi"] * abs(cpi),
    }

    # Behavioral penalty: Extreme Fear suppresses risk-on regimes
    if extreme_fear > 0.1:
        scores["ALT_ROTATION"] -= 1.0 * extreme_fear
        scores["CAPITAL_EXIT"] += 0.8 * extreme_fear
        scores["NEUTRAL"] += 0.3 * extreme_fear

    return scores


# Transition inertia and drift coefficients
TRANSITION_INERTIA = 0.4       # bonus for staying in current regime
TRANSITION_DRIFT_COEFF = 0.3   # how much CPI drift influences transitions
TRANSITION_MAX_SELF = 0.85     # max self-transition probability
TRANSITION_MIN_OTHER = 0.02    # min transition to any neighbor


def compute_transition_matrix(current_regime, regime_scores, cpi_drift, riskoff_momentum=0.0):
    """Compute transition probabilities from current regime.
    
    logit(to) = score(to) + drift_component(to) + inertia(to==current)
    Then softmax → probabilities, clamped.
    
    Args:
        current_regime: current dominant regime key
        regime_scores: raw scores dict (before softmax)
        cpi_drift: rate of change of CPI (positive = toward BTC/stables)
        riskoff_momentum: rate of change of riskOffProb
    
    Returns:
        dict of {regime: probability} summing to ~1.0
    """
    regimes = list(regime_scores.keys())

    # Drift components: how CPI/riskoff momentum pushes toward each regime
    drift_map = {
        "FLIGHT_TO_BTC": TRANSITION_DRIFT_COEFF * cpi_drift + 0.15 * riskoff_momentum,
        "ALT_ROTATION": -TRANSITION_DRIFT_COEFF * cpi_drift - 0.15 * riskoff_momentum,
        "CAPITAL_EXIT": 0.2 * riskoff_momentum + 0.1 * cpi_drift,
        "NEUTRAL": -0.1 * abs(cpi_drift) - 0.1 * abs(riskoff_momentum),
    }

    logits = {}
    for r in regimes:
        base = regime_scores.get(r, 0)
        drift = drift_map.get(r, 0)
        inertia = TRANSITION_INERTIA if r == current_regime else 0
        logits[r] = base + drift + inertia

    probs = softmax(logits, temp=1.0)

    # Clamp: max self-transition, min others
    self_prob = min(probs.get(current_regime, 0), TRANSITION_MAX_SELF)
    for r in regimes:
        if r == current_regime:
            probs[r] = self_prob
        else:
            probs[r] = max(probs[r], TRANSITION_MIN_OTHER)

    # Renormalize
    total = sum(probs.values())
    return {r: round(v / total, 4) for r, v in probs.items()}
