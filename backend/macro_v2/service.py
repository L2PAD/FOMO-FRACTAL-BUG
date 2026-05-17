"""Macro V2 Service — orchestration: series → z-scores → computed output."""
import statistics
from .config import Z_WINDOW, EPSILON, TEMP_SOFTMAX, HORIZON_7D, STRONG_BLOCK_RISKOFF, STRONG_BLOCK_EXTFEAR, ALT_REDUCED_THRESHOLD
from .math_utils import (
    log_return, zscore, fg_inverted, extreme_fear_prob, extreme_greed_prob,
    compute_cpi, compute_riskoff_prob, compute_macro_mult,
    compute_regime_scores, softmax, compute_transition_matrix,
)
from .providers import get_macro_series, get_macro_snapshot_raw, get_data_source
from .lmi import compute_lmi
from .risk import compute_risk_split


def _rolling_stats(values):
    if len(values) < 5:
        m = sum(values) / max(len(values), 1)
        return m, 1.0
    m = statistics.mean(values)
    s = statistics.pstdev(values) or 1.0
    return m, s


def _get_prev(points, idx, back):
    return points[max(0, idx - back)]


def compute_macro(series=None, limit=365):
    """Full macro computation from series data."""
    if series is None:
        series = get_macro_series(limit)

    if not series or len(series) < 10:
        return _empty_result()

    i = len(series) - 1
    p = series[i]
    h7 = HORIZON_7D
    p7 = _get_prev(series, i, h7)

    # Derived features
    r_btc_7 = log_return(p["btcPrice"], p7["btcPrice"])
    r_alt_7 = log_return(p["altIndex"], p7["altIndex"])
    r_altvsbtc_7 = r_alt_7 - r_btc_7

    d_btcdom_7 = p["btcDom"] - p7["btcDom"]
    d_stabledom_7 = p["stableDom"] - p7["stableDom"]

    vol_7 = p.get("marketVol") or abs(r_btc_7)

    # Rolling z-score windows
    w = min(Z_WINDOW, len(series))
    tail = series[-w:]

    def _win(fn):
        return [fn(k) for k in range(len(tail))]

    win_d_btcdom = _win(lambda k: tail[k]["btcDom"] - tail[max(0, k - h7)]["btcDom"])
    win_d_stable = _win(lambda k: tail[k]["stableDom"] - tail[max(0, k - h7)]["stableDom"])
    win_rbtc = _win(lambda k: log_return(tail[k]["btcPrice"], tail[max(0, k - h7)]["btcPrice"]))
    win_raltvsbtc = _win(lambda k: (
        log_return(tail[k]["altIndex"], tail[max(0, k - h7)]["altIndex"])
        - log_return(tail[k]["btcPrice"], tail[max(0, k - h7)]["btcPrice"])
    ))
    win_fg_inv = _win(lambda k: fg_inverted(tail[k]["fearGreed"]))
    win_vol = _win(lambda k: tail[k].get("marketVol") or abs(
        log_return(tail[k]["btcPrice"], tail[max(0, k - h7)]["btcPrice"])
    ))

    m_db, s_db = _rolling_stats(win_d_btcdom)
    m_ds, s_ds = _rolling_stats(win_d_stable)
    m_rb, s_rb = _rolling_stats(win_rbtc)
    m_avb, s_avb = _rolling_stats(win_raltvsbtc)
    m_fgi, s_fgi = _rolling_stats(win_fg_inv)
    m_v, s_v = _rolling_stats(win_vol)

    z_db7 = zscore(d_btcdom_7, m_db, s_db)
    z_ds7 = zscore(d_stabledom_7, m_ds, s_ds)
    z_rbtc7 = zscore(r_btc_7, m_rb, s_rb)
    z_altvsbtc7 = zscore(r_altvsbtc_7, m_avb, s_avb)
    z_fg_inv = zscore(fg_inverted(p["fearGreed"]), m_fgi, s_fgi)
    z_vol7 = zscore(vol_7, m_v, s_v)
    z_neg_rbtc7 = zscore(-r_btc_7, -m_rb, s_rb)

    # Core computations
    cpi, cpi_drivers = compute_cpi(z_db7, z_ds7, z_rbtc7, z_altvsbtc7)
    ex_fear = extreme_fear_prob(p["fearGreed"])
    ex_greed = extreme_greed_prob(p["fearGreed"])
    riskoff = compute_riskoff_prob(z_ds7, z_fg_inv, z_vol7, z_neg_rbtc7)
    macro_mult = compute_macro_mult(riskoff, ex_greed)

    regime_scores = compute_regime_scores(z_db7, z_ds7, z_rbtc7, z_altvsbtc7, riskoff, cpi, extreme_fear=ex_fear)
    probs = softmax(regime_scores, temp=TEMP_SOFTMAX)
    regime = max(probs, key=probs.get)

    # Transition matrix: compute CPI drift and riskOff momentum from series
    cpi_drift = 0.0
    riskoff_momentum = 0.0
    if len(series) >= 14:
        # Compute CPI for 7 days ago to get drift
        p_prev7 = _get_prev(series, i, 7)
        p_prev14 = _get_prev(series, i, 14)
        r_btc_prev = log_return(p_prev7["btcPrice"], p_prev14["btcPrice"])
        r_alt_prev = log_return(p_prev7["altIndex"], p_prev14["altIndex"])
        d_btcdom_prev = p_prev7["btcDom"] - p_prev14["btcDom"]
        d_stabledom_prev = p_prev7["stableDom"] - p_prev14["stableDom"]
        z_db7_prev = zscore(d_btcdom_prev, m_db, s_db)
        z_ds7_prev = zscore(d_stabledom_prev, m_ds, s_ds)
        z_rbtc7_prev = zscore(r_btc_prev, m_rb, s_rb)
        z_altvsbtc7_prev = zscore(r_alt_prev - r_btc_prev, m_avb, s_avb)
        cpi_prev, _ = compute_cpi(z_db7_prev, z_ds7_prev, z_rbtc7_prev, z_altvsbtc7_prev)
        cpi_drift = cpi - cpi_prev

        # RiskOff momentum
        fg_inv_prev = fg_inverted(p_prev7["fearGreed"])
        vol_prev = p_prev7.get("marketVol") or abs(r_btc_prev)
        z_fg_inv_prev = zscore(fg_inv_prev, m_fgi, s_fgi)
        z_vol7_prev = zscore(vol_prev, m_v, s_v)
        z_neg_rbtc7_prev = zscore(-r_btc_prev, -m_rb, s_rb)
        riskoff_prev = compute_riskoff_prob(z_ds7_prev, z_fg_inv_prev, z_vol7_prev, z_neg_rbtc7_prev)
        riskoff_momentum = riskoff - riskoff_prev

    transitions = compute_transition_matrix(regime, regime_scores, cpi_drift, riskoff_momentum)

    strong_blocked = (riskoff >= STRONG_BLOCK_RISKOFF) or (ex_fear >= STRONG_BLOCK_EXTFEAR)
    alt_reduced = (probs.get("FLIGHT_TO_BTC", 0) + probs.get("CAPITAL_EXIT", 0)) >= ALT_REDUCED_THRESHOLD

    notes = []
    if strong_blocked:
        notes.append("Macro blocks strong actions (risk-off / extreme fear)")
    if alt_reduced:
        notes.append("Alt exposure reduced (capital concentrates in BTC/stables)")

    # Capital flow deltas for UI
    alt_dom = round(100 - p["btcDom"] - p["stableDom"], 2)
    alt_dom_prev = round(100 - p7["btcDom"] - p7["stableDom"], 2)

    # 30d deltas (if enough data)
    p30 = _get_prev(series, i, 30)
    d_btcdom_30 = round(p["btcDom"] - p30["btcDom"], 2)
    d_stabledom_30 = round(p["stableDom"] - p30["stableDom"], 2)
    alt_dom_30 = round(100 - p30["btcDom"] - p30["stableDom"], 2)
    d_altdom_30 = round(alt_dom - alt_dom_30, 2)

    # Risk surface impact estimate (1/mult - 1)
    risk_impact_pct = round((1.0 / max(macro_mult, 0.3) - 1.0) * 100, 1) if macro_mult < 1.0 else 0.0

    # Drivers for UI decomposition
    drivers = {
        "btc_dom_delta": round(cpi_drivers["btc_dom_7d"], 3),
        "stable_dom_delta": round(cpi_drivers["stable_dom_7d"], 3),
        "btc_momentum": round(cpi_drivers["btc_ret_7d"], 3),
        "alt_relative_strength": round(cpi_drivers["alt_vs_btc_7d"], 3),
        "fear_greed_impact": round(z_fg_inv * 0.55, 3),
    }

    # Riskoff decomposition
    riskoff_drivers = {
        "stable_dom": round(z_ds7 * 0.65, 3),
        "fear_greed": round(z_fg_inv * 0.55, 3),
        "volatility": round(z_vol7 * 0.35, 3),
        "btc_drawdown": round(z_neg_rbtc7 * 0.25, 3),
    }

    result = {
        "ok": True,
        "asOf": p["t"],
        "dataSource": get_data_source(),
        "raw": {
            "fearGreed": round(p["fearGreed"], 1),
            "btcDom": round(p["btcDom"], 2),
            "stableDom": round(p["stableDom"], 2),
            "altDom": alt_dom,
            "btcPrice": round(p["btcPrice"], 2),
            "altIndex": round(p["altIndex"], 2),
            "marketVol": round(vol_7, 4),
        },
        "computed": {
            "cpi": round(cpi, 3),
            "riskOffProb": round(riskoff, 3),
            "extremeFearProb": round(ex_fear, 3),
            "extremeGreedProb": round(ex_greed, 3),
            "macroMult": round(macro_mult, 3),
            "regime": regime,
            "regimeProbs": probs,
            "strongActionsBlocked": strong_blocked,
            "altExposureReduced": alt_reduced,
            "notes": notes,
        },
        "capitalFlow": {
            "btc": {
                "dominance": round(p["btcDom"], 2),
                "delta7d": round(d_btcdom_7, 2),
                "delta30d": d_btcdom_30,
                "pressure": "IN" if d_btcdom_7 > 0.3 else ("OUT" if d_btcdom_7 < -0.3 else "FLAT"),
            },
            "alt": {
                "dominance": alt_dom,
                "delta7d": round(alt_dom - alt_dom_prev, 2),
                "delta30d": d_altdom_30,
                "pressure": "OUTPERFORMING" if r_altvsbtc_7 > 0.02 else ("UNDERPERFORMING" if r_altvsbtc_7 < -0.02 else "INLINE"),
            },
            "stable": {
                "dominance": round(p["stableDom"], 2),
                "delta7d": round(d_stabledom_7, 2),
                "delta30d": d_stabledom_30,
                "pressure": "RISK_SHELTER" if d_stabledom_7 > 0.2 else ("DEPLOYING" if d_stabledom_7 < -0.2 else "FLAT"),
            },
        },
        "drivers": drivers,
        "riskoffDrivers": riskoff_drivers,
        "transitions": {
            "from": regime,
            "probabilities": transitions,
            "cpiDrift": round(cpi_drift, 3),
            "riskoffMomentum": round(riskoff_momentum, 3),
        },
        "impact": {
            "aggressionScale": round(macro_mult, 3),
            "riskSurfaceImpact": risk_impact_pct,
            "strongActionsBlocked": strong_blocked,
            "altExposureReduced": alt_reduced,
        },
    }

    # Compute LMI from series
    result["lmi"] = compute_lmi(series)

    # Compute risk split (structural from this snapshot, tactical placeholder)
    result["riskSplit"] = compute_risk_split(result)

    return result


def compute_macro_history(limit=90):
    """Compute macro for last N days (sliding window)."""
    series = get_macro_series(max(limit + 60, 200))
    results = []
    start = max(30, len(series) - limit)
    for k in range(start, len(series)):
        tail = series[:k + 1]
        try:
            r = compute_macro(series=tail)
            results.append({
                "t": r["asOf"],
                "cpi": r["computed"]["cpi"],
                "riskOffProb": r["computed"]["riskOffProb"],
                "macroMult": r["computed"]["macroMult"],
                "regime": r["computed"]["regime"],
                "regimeProbs": r["computed"]["regimeProbs"],
                "fearGreed": r["raw"]["fearGreed"],
            })
        except Exception:
            continue
    return {"ok": True, "points": results}


def _empty_result():
    return {
        "ok": False,
        "error": "Insufficient macro data",
        "raw": {},
        "computed": {
            "cpi": 0, "riskOffProb": 0.5, "extremeFearProb": 0.5,
            "extremeGreedProb": 0.01, "macroMult": 0.7,
            "regime": "NEUTRAL", "regimeProbs": {
                "FLIGHT_TO_BTC": 0.25, "ALT_ROTATION": 0.25,
                "CAPITAL_EXIT": 0.25, "NEUTRAL": 0.25,
            },
            "strongActionsBlocked": False, "altExposureReduced": False, "notes": [],
        },
        "capitalFlow": {},
        "drivers": {},
        "riskoffDrivers": {},
        "impact": {},
    }
