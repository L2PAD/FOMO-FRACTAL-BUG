"""
Engine Narrative Service — E4
==============================
Rule-based human-readable narrative generator.
Takes the complete engine output and builds structured text sections
that explain the full market analysis in plain language.

NO LLM — pure deterministic template logic.
"""

from datetime import datetime, timezone


# ── Regime narrative templates ──

_REGIME_NARRATIVES = {
    "bull_trend": "Market is in an active bull trend",
    "bear_trend": "Market is in a bear trend",
    "accumulation": "Market is in accumulation phase",
    "distribution": "Market is in distribution phase",
    "rotation": "Capital is rotating between sectors",
    "neutral_chop": "Market shows no dominant trend — neutral chop",
}

_SETUP_NARRATIVES = {
    "liquidity_shock": "A liquidity shock has been detected — exchange order books show significant imbalance",
    "smart_money_accumulation": "Smart money is accumulating — institutional-grade capital is flowing in",
    "distribution_risk": "Distribution risk is elevated — large holders appear to be reducing exposure",
    "exchange_drain": "Exchange reserves are draining — supply squeeze conditions are forming",
    "rotation": "Capital is rotating between assets — sector rebalancing in progress",
    "actor_conflict": "Key actors are in conflict — some accumulating while others distribute",
    "otc_transfer": "OTC activity is elevated — large off-exchange transfers detected",
    "mixed": "No clear setup dominates — mixed signals across layers",
}

_FLOW_NARRATIVES = {
    "bullish_acceleration": "Capital flows are accelerating to the buy side",
    "bearish_acceleration": "Capital flows are accelerating to the sell side",
    "liquidity_expansion": "Liquidity is expanding — fresh capital entering the market",
    "flow_exhaustion": "Flow momentum is exhausting — velocity is declining despite volume",
    "neutral": "Capital flows show no significant acceleration in either direction",
}

_DECISION_VERBS = {
    "BUY": "favors a long position",
    "SELL": "signals risk reduction",
    "NEUTRAL": "recommends waiting for confirmation",
}

_CONF_ADJECTIVES = {
    "HIGH": "high",
    "MODERATE": "moderate",
    "LOW": "low",
    "INSUFFICIENT": "insufficient",
}


def _pct(v):
    """Format 0-1 float as percentage string."""
    if v is None:
        return "—"
    return f"{round(v * 100)}%"


def _build_executive_summary(data: dict) -> str:
    """One concise paragraph with confidence-adapted tone."""
    decision = data.get("decision", "NEUTRAL")
    conf = data.get("confidence", {})
    regime = data.get("regime_engine", {}).get("primary", {})
    setup = data.get("setup_engine", {}).get("primary", {})
    prob = data.get("probability_layer", {})
    composite = data.get("scores", {}).get("composite", 50)

    regime_type = regime.get("type", "neutral_chop")
    conf_level = conf.get("level", "LOW")
    conf_score = conf.get("score", 0)

    setup_type = setup.get("type", "mixed")
    setup_conf = setup.get("confidence", 0)

    cont = prob.get("continuation", 0)
    fail = prob.get("failure", 0)

    # ── Confidence-adapted tone ──
    parts = []

    if conf_level == "HIGH" and conf_score >= 70:
        # HIGH confidence tone — assertive
        regime_label = _REGIME_NARRATIVES.get(regime_type, "Market regime is unclear")
        parts.append(f"Market conditions strongly support the current thesis. {regime_label} (composite {composite}).")
        if setup_type != "mixed":
            setup_name = _SETUP_NARRATIVES.get(setup_type, setup_type.replace("_", " "))
            parts.append(f"Multiple high-confidence signals confirm the {setup_name.split('—')[0].strip().lower()} setup ({_pct(setup_conf)}).")
        verb = _DECISION_VERBS.get(decision, "recommends caution")
        parts.append(f"The engine {verb} with high confidence ({conf_score}).")
    elif conf_level in ("MODERATE",) or (conf_level == "HIGH" and conf_score < 70):
        # MODERATE confidence tone — balanced
        regime_label = _REGIME_NARRATIVES.get(regime_type, "Market regime is unclear")
        parts.append(f"{regime_label} (composite {composite}).")
        if setup_type != "mixed":
            setup_name = _SETUP_NARRATIVES.get(setup_type, setup_type.replace("_", " "))
            parts.append(f"Primary setup: {setup_name.split('—')[0].strip().lower()} ({_pct(setup_conf)} confidence).")
        else:
            parts.append("No dominant setup detected.")
        verb = _DECISION_VERBS.get(decision, "recommends caution")
        conf_adj = _CONF_ADJECTIVES.get(conf_level, "moderate")
        parts.append(f"The engine {verb} with {conf_adj} confidence ({conf_score}).")
    else:
        # LOW / INSUFFICIENT confidence tone — cautious
        regime_label = _REGIME_NARRATIVES.get(regime_type, "Market regime is unclear")
        parts.append(f"Market conditions remain uncertain. {regime_label} (composite {composite}).")
        if setup_type != "mixed":
            setup_name = _SETUP_NARRATIVES.get(setup_type, setup_type.replace("_", " "))
            parts.append(f"Current signals suggest a possible {setup_name.split('—')[0].strip().lower()}, but supporting evidence remains limited ({_pct(setup_conf)}).")
        else:
            parts.append("No clear setup dominates — signals are mixed.")
        parts.append(f"The engine recommends waiting for confirmation. Confidence is {conf_level.lower()} ({conf_score}).")

    if cont > 0 and fail > 0:
        parts.append(f"Continuation probability: {_pct(cont)}, failure risk: {_pct(fail)}.")

    return " ".join(parts)


def _build_regime_section(data: dict) -> str:
    """Regime analysis paragraph."""
    regime = data.get("regime_engine", {})
    primary = regime.get("primary", {})
    secondary = regime.get("secondary", [])

    rtype = primary.get("type", "neutral_chop")
    label = _REGIME_NARRATIVES.get(rtype, "Regime unclear")
    status = primary.get("status", "weak")
    conf = primary.get("confidence", 0)
    drivers = primary.get("drivers", [])
    invalidation = primary.get("invalidation", [])

    parts = [f"{label} — status: {status}, confidence: {_pct(conf)}."]

    if drivers:
        parts.append(f"Supporting factors: {'; '.join(drivers[:3])}.")

    if invalidation:
        parts.append(f"Invalidation conditions: {'; '.join(invalidation[:2])}.")

    if secondary:
        sec_labels = [_REGIME_NARRATIVES.get(s.get("type", ""), s.get("type", "?")) + f" ({_pct(s.get('confidence', 0))})" for s in secondary[:2]]
        parts.append(f"Secondary regimes: {', '.join(sec_labels)}.")

    return " ".join(parts)


def _build_setup_section(data: dict) -> str:
    """Setup intelligence paragraph."""
    setup = data.get("setup_engine", {})
    primary = setup.get("primary", {})
    secondary = setup.get("secondary", [])

    stype = primary.get("type", "mixed")
    base = _SETUP_NARRATIVES.get(stype, stype.replace("_", " "))
    status = primary.get("status", "weak")
    conf = primary.get("confidence", 0)
    window = primary.get("window", "")
    supports = primary.get("supports", [])
    contradictions = primary.get("contradictions", [])
    invalidation = primary.get("invalidation", [])

    parts = [f"{base} — status: {status}, confidence: {_pct(conf)}."]

    if window:
        parts.append(f"Expected action window: {window}.")

    if supports:
        parts.append(f"Supported by: {'; '.join(supports[:3])}.")

    if contradictions:
        parts.append(f"Contradicted by: {'; '.join(contradictions[:2])}.")

    if invalidation:
        parts.append(f"Setup invalidates if: {'; '.join(invalidation[:2])}.")

    if secondary:
        sec_names = []
        for s in secondary[:2]:
            st = s.get("type", "?")
            sc = _pct(s.get("confidence", 0))
            sec_names.append(f"{st.replace('_', ' ')} ({sc})")
        parts.append(f"Secondary setups: {', '.join(sec_names)}.")

    return " ".join(parts)


def _build_flow_section(data: dict) -> str:
    """Flow and liquidity combined paragraph."""
    flow = data.get("flow_engine", {})
    liq = data.get("liquidity_map", {})

    flow_state = flow.get("state", "neutral")
    flow_label = _FLOW_NARRATIVES.get(flow_state, "Flow momentum neutral")
    strength = flow.get("strength", 0)
    velocity = flow.get("velocity", "low")
    flow_drivers = flow.get("drivers", [])

    parts = [f"{flow_label} — strength: {_pct(strength)}, velocity: {velocity}."]

    if flow_drivers:
        parts.append(f"Flow drivers: {'; '.join(flow_drivers[:3])}.")

    # Liquidity map
    liq_dir = liq.get("primary_direction", "neutral")
    targets = liq.get("target_zones", [])
    magnets = liq.get("magnet_zones", [])
    voids = liq.get("void_zones", [])

    if liq_dir != "neutral":
        parts.append(f"Liquidity map points {liq_dir}.")

    if targets:
        target_descs = [t.get("reason", "—") for t in targets[:2]]
        parts.append(f"Key targets: {'; '.join(target_descs)}.")

    if magnets:
        magnet_descs = [m.get("reason", "—") for m in magnets[:2]]
        parts.append(f"Magnet zones: {'; '.join(magnet_descs)}.")

    if voids:
        void_descs = [v.get("reason", "—") for v in voids[:2]]
        parts.append(f"Liquidity voids: {'; '.join(void_descs)}.")

    if liq.get("summary"):
        parts.append(liq["summary"])

    return " ".join(parts)


def _build_probability_section(data: dict) -> str:
    """Probability assessment paragraph."""
    prob = data.get("probability_layer", {})
    cont = prob.get("continuation", 0)
    fail = prob.get("failure", 0)
    upgrade = prob.get("upgrade", 0)
    summary = prob.get("summary", "")

    parts = []
    parts.append(f"Continuation probability: {_pct(cont)}. Failure risk: {_pct(fail)}. Upgrade potential: {_pct(upgrade)}.")

    if cont > fail:
        margin = round((cont - fail) * 100)
        parts.append(f"Continuation leads by {margin} percentage points — setup has statistical edge.")
    elif fail > cont:
        margin = round((fail - cont) * 100)
        parts.append(f"Failure risk exceeds continuation by {margin} percentage points — caution warranted.")
    else:
        parts.append("Continuation and failure risk are evenly balanced — no clear statistical edge.")

    if upgrade > 0.15:
        parts.append(f"Meaningful upgrade potential ({_pct(upgrade)}) — conditions could improve.")

    if summary:
        parts.append(summary)

    return " ".join(parts)


def _build_risk_section(data: dict) -> str:
    """Risk factors paragraph."""
    gates = data.get("gates", {})
    explanation = data.get("decision_explanation", {})
    otc_mm = data.get("otc_mm_influence", {})

    risk_gate = gates.get("risk", {})
    risk_factors = risk_gate.get("factors", [])
    evidence_status = gates.get("evidence", {}).get("status", "PASS")
    coverage_status = gates.get("coverage", {}).get("status", "FULL")

    contradictions = explanation.get("bearish_or_contradictions", [])

    parts = []

    if risk_factors:
        parts.append(f"Active risk factors ({len(risk_factors)}): {'; '.join(risk_factors[:3])}.")
    else:
        parts.append("No significant risk factors detected.")

    if evidence_status in ("WEAK", "FAIL"):
        parts.append(f"Evidence gate is {evidence_status} — module agreement is insufficient.")

    if coverage_status in ("LOW", "PARTIAL"):
        parts.append(f"Data coverage is {coverage_status.lower()} — some intelligence sources are missing.")

    if contradictions:
        parts.append(f"Key contradictions: {'; '.join(contradictions[:2])}.")

    if otc_mm.get("mm_presence"):
        parts.append("Market maker activity detected — expect increased volatility and potential false signals.")

    otc_bias = otc_mm.get("otc_bias", "neutral")
    if otc_bias != "neutral":
        parts.append(f"OTC flow bias is {otc_bias}.")

    return " ".join(parts)


def _build_action_section(data: dict) -> str:
    """Action plan paragraph — what needs to happen."""
    decision = data.get("decision", "NEUTRAL")
    explanation = data.get("decision_explanation", {})
    blockers = explanation.get("decision_blockers", [])
    triggers = explanation.get("upgrade_triggers", [])
    conf = data.get("confidence", {})

    parts = []

    if decision == "BUY":
        parts.append("Position: The engine recommends a long bias.")
        if triggers:
            parts.append(f"To maintain: {triggers[0]}.")
    elif decision == "SELL":
        parts.append("Position: The engine signals risk reduction.")
        if triggers:
            parts.append(f"To maintain: {triggers[0]}.")
    else:
        parts.append("Position: No action — waiting for confirmation.")
        if blockers:
            parts.append(f"Primary blocker: {blockers[0]}.")
        if triggers:
            parts.append(f"Upgrade requires: {'; '.join(triggers[:3])}.")

    conf_score = conf.get("score", 0)
    if conf_score < 45:
        parts.append("Low confidence suggests reducing position size if acting.")
    elif conf_score >= 70:
        parts.append("High confidence supports full position sizing.")

    return " ".join(parts)


def build_narrative(engine_data: dict) -> dict:
    """
    Main entry point — builds complete narrative from engine output.
    Returns structured narrative with sections and full_text.
    """
    sections = [
        {
            "id": "summary",
            "title": "Executive Summary",
            "content": _build_executive_summary(engine_data),
        },
        {
            "id": "regime",
            "title": "Regime Analysis",
            "content": _build_regime_section(engine_data),
        },
        {
            "id": "setup",
            "title": "Setup Intelligence",
            "content": _build_setup_section(engine_data),
        },
        {
            "id": "flow",
            "title": "Flow & Liquidity",
            "content": _build_flow_section(engine_data),
        },
        {
            "id": "probability",
            "title": "Probability Assessment",
            "content": _build_probability_section(engine_data),
        },
        {
            "id": "risk",
            "title": "Risk Factors",
            "content": _build_risk_section(engine_data),
        },
        {
            "id": "action",
            "title": "Action Plan",
            "content": _build_action_section(engine_data),
        },
    ]

    full_text = "\n\n".join(f"{s['title']}:\n{s['content']}" for s in sections)

    return {
        "sections": sections,
        "full_text": full_text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "4.5",
    }
