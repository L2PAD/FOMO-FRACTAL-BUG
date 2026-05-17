"""`structure` slot — modules array + alignment + timeframes.

Assembles structure.modules from `sig.drivers` plus the TA/Sentiment/
Fractal module-views supplied via ctx. Mirrors server.py exactly so the
public payload remains byte-level identical.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..contracts import HomeContext


def _ta_to_module(ta_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Pure adapter — equivalent to services.technical_analysis.as_miniapp_module
    but inlined here to satisfy A10 (composer modules call no external fns)."""
    from services.technical_analysis import as_miniapp_module
    return as_miniapp_module(ta_payload)


def _sr_to_module(sr_payload: Dict[str, Any]) -> Dict[str, Any]:
    from services.sentiment_runtime import as_miniapp_module
    return as_miniapp_module(sr_payload)


def _fr_to_module(fr_payload: Dict[str, Any]) -> Dict[str, Any]:
    from services.fractal_runtime import as_miniapp_module
    return as_miniapp_module(fr_payload)


def build_structure_items(ctx: HomeContext) -> List[Dict[str, Any]]:
    """Build structure.modules array — TA / Sentiment / Fractal injection.

    Same algorithm as the original server.py:
      1. start from sig.drivers
      2. append TA module-view if no 'Technical*' already present
      3. replace any existing 'Sentiment*' driver with runtime view
         (otherwise append)
      4. replace any existing 'Fractal*' driver with runtime view
         (otherwise append)
    """
    sig = ctx.sig or {}
    drivers = sig.get("drivers", []) or []

    structure_items: List[Dict[str, Any]] = []
    for d in drivers:
        structure_items.append({
            "module": d["name"],
            "direction": d["direction"],
            "confidence": d["confidence"],
            "insight": d.get("insight", d.get("reason", "")),
        })

    # TA injection
    if ctx.ta_payload is not None:
        try:
            ta_item = _ta_to_module(ctx.ta_payload)
            if not any((it.get("module") or "").lower().startswith("technical") for it in structure_items):
                structure_items.append(ta_item)
        except Exception:
            pass

    # Sentiment injection (replace existing Sentiment driver)
    if ctx.sentiment_payload is not None:
        try:
            sr_item = _sr_to_module(ctx.sentiment_payload)
            replaced = False
            for i, it in enumerate(structure_items):
                name = (it.get("module") or "").lower()
                if name == "sentiment" or name.startswith("sentiment"):
                    structure_items[i] = sr_item
                    replaced = True
                    break
            if not replaced:
                structure_items.append(sr_item)
        except Exception:
            pass

    # Fractal injection (replace existing Fractal driver)
    if ctx.fractal_payload is not None:
        try:
            fr_item = _fr_to_module(ctx.fractal_payload)
            replaced_f = False
            for i, it in enumerate(structure_items):
                name = (it.get("module") or "").lower()
                if name == "fractal" or name.startswith("fractal"):
                    structure_items[i] = fr_item
                    replaced_f = True
                    break
            if not replaced_f:
                structure_items.append(fr_item)
        except Exception:
            pass

    return structure_items


def alignment_enum(aligned_cnt: int) -> str:
    if aligned_cnt >= 4:
        return "ALIGNED"
    if aligned_cnt >= 2:
        return "SHORT_DIVERGENCE"
    if aligned_cnt >= 1:
        return "LONG_DIVERGENCE"
    return "DIVERGENCE"


def _dir_to_bucket(d) -> str:
    r = (d or "").upper()
    if r in ("UP", "BULLISH"):
        return "bullish"
    if r in ("DOWN", "BEARISH"):
        return "bearish"
    return "neutral"


def build_timeframes(ctx: HomeContext, confidence_01: float) -> Dict[str, Dict[str, Any]]:
    """Assemble h24/d7/d30 timeframe summaries from prediction-chart timeframes."""
    timeframes = (ctx.prediction or {}).get("timeframes") or []

    def _tf_for(key):
        for t in timeframes:
            if (t.get("key") or "") == key:
                return t
        return {}

    t7 = _tf_for("7D")
    t30 = _tf_for("30D")
    h24_conv = float(t7.get("conviction", 0) or 0) * 0.9 if t7 else confidence_01
    h24_dir = _dir_to_bucket(t7.get("direction") if t7 else None)

    return {
        "h24": {"direction": h24_dir, "confidence": h24_conv},
        "d7": {
            "direction": _dir_to_bucket(t7.get("direction")),
            "confidence": float(t7.get("confidence", 0) or 0),
        },
        "d30": {
            "direction": _dir_to_bucket(t30.get("direction")),
            "confidence": float(t30.get("confidence", 0) or 0),
        },
    }


def assemble(ctx: HomeContext, confidence_01: float) -> Dict[str, Any]:
    sig = ctx.sig or {}
    df = sig.get("decisionFramework", {}) or {}
    aligned_cnt = df.get("alignedCount", 0) or 0

    items = build_structure_items(ctx)
    timeframes = build_timeframes(ctx, confidence_01)

    return {
        "modules": items,
        "alignment": alignment_enum(aligned_cnt),
        "alignmentCount": aligned_cnt,
        "insight": df.get("whatMattersNow", "") or "Waiting for alignment across modules",
        "h24": timeframes["h24"],
        "d7": timeframes["d7"],
        "d30": timeframes["d30"],
    }
