"""`signal`, `marketStory`, `why`, `truth`, `entryWindow`, `conflict`,
`generated_at` slots — straight passthroughs from sig payload.
"""
from __future__ import annotations

from typing import Any, Dict

from ..contracts import HomeContext


def assemble_signal_card(ctx: HomeContext) -> Dict[str, Any]:
    sig = ctx.sig or {}
    df = sig.get("decisionFramework", {}) or {}
    return {
        "stage": df.get("stage", "EARLY"),
        "stageLabel": df.get("stageLabel", ""),
        "alignment": df.get("alignment", "0 of 6"),
        "timing": df.get("timingLabel", ""),
    }


def assemble_market_story(ctx: HomeContext) -> Dict[str, Any]:
    sig = ctx.sig or {}
    df = sig.get("decisionFramework", {}) or {}
    return {
        "text": sig.get("summary", ""),
        "regime": df.get("stage", "SCANNING"),
    }


def assemble_why(ctx: HomeContext):
    sig = ctx.sig or {}
    df = sig.get("decisionFramework", {}) or {}
    return df.get("mattersPoints", [])


def assemble_truth(ctx: HomeContext) -> Dict[str, Any]:
    sig = ctx.sig or {}
    return sig.get("truth", {}) or {}


def assemble_entry_window(ctx: HomeContext) -> Dict[str, Any]:
    sig = ctx.sig or {}
    return sig.get("entryWindow", {}) or {}


def assemble_conflict(ctx: HomeContext) -> Dict[str, Any]:
    sig = ctx.sig or {}
    return sig.get("conflict", {}) or {}


def assemble_generated_at(ctx: HomeContext) -> str:
    sig = ctx.sig or {}
    return sig.get("updatedAt", "")
