"""
Hardcoded i18n Pipeline — Task 7B-1 (Translation + Normalization)
==================================================================

For the 45 keys extracted from EdgeScreen / PaywallScreen /
SignalDetailScreen / OperatorObservatoryScreen, this script:

  1. Sends the raw EN strings to Claude Sonnet 4.5 under the platform's
     Truthful-Degradation restraint contract for THREE outputs per key:

         en_normalized — same English, but with casino/predictive tone
                         softened ("Unlock exact entry" → "Unlock the
                         alignment context"). Brand invariants kept.
         ru             — Russian under the same Translation Law.
         uk             — Ukrainian under the same Translation Law.

  2. Writes /app/backend/scripts/hardcoded_extract/_translations.json
     with shape:  { key: { en: str, ru: str, uk: str } }

The actual i18n.ts injection + JSX refactor happen in subsequent steps.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
IN_PATH = Path("/app/backend/scripts/hardcoded_extract/_combined.en.json")
OUT_PATH = Path("/app/backend/scripts/hardcoded_extract/_translations.json")


# ─── Translation Law (multi-target, restraint-bound) ────────────────────
LAW = """
You localise UI strings for a cognitive trading infrastructure whose
defining law is TRUTHFUL DEGRADATION: it speaks observationally, never
predictively; it never promises profit, alpha, or precise entries; it
never sounds like a casino, a hype crypto-Twitter feed, or a Binance clone.

For EACH input English string, emit THREE outputs:

  • "en": restraint-normalized English. If the source already complies,
    keep it. If it contains casino/predictive/hype tone, soften it without
    changing the structural intent. Examples:
       "Unlock exact entry"           → "Unlock alignment detail"
       "PRE-CONFIRMATION ENTRY"       → "PRE-CONFIRMATION CONTEXT"
       "Signals before they become obvious"
                                      → "Structure shifts before they
                                         become obvious"
       "You are already positioned"   → keep (observational, neutral)

  • "ru": Russian under the same law. Forbidden vocabulary:
       сигнал (use "наблюдение / структурный сдвиг"),
       сделка, профит, прибыль, альфа, точка входа, гарантированно,
       высокоточный, агрессивный, максимальный профит,
       HODL, мунить, шортить, IDO sniper.
    Preferred: структура, выравнивание, давление, контекст, наблюдение,
       режим, сжатие/расширение, сдержанность, неопределённость, ясность.

  • "uk": Ukrainian under the same law. Forbidden vocabulary:
       сигнал (use "спостереження / структурне зрушення"),
       угода, прибуток, перемога, виграш, альфа, точка входу,
       гарантовано, високоточний, агресивний, максимальний прибуток,
       HODL, мунити, шортити.
    Preferred: структура, вирівнювання, тиск, контекст, спостереження,
       режим, розширення/стиснення, стриманість, невизначеність, ясність.

BRAND INVARIANTS — never translate, never rename:
  FOMO, Trading OS, PRO, FREE, Telegram, BTC, ETH, SOL, USDT, USD,
  Stripe, NOWPayments, Edge, Observatory.

UI CONVENTIONS:
  • Length close to source — mobile-first layouts break with long strings.
  • Section headers (ALL CAPS) — keep ALL CAPS for ru/uk too only if the
    source is ALL CAPS.
  • Preserve `{placeholder}` variables verbatim.

OUTPUT: JSON only. Schema:
   { "<original_key>": { "en": "...", "ru": "...", "uk": "..." }, ... }

No explanation. No code fences. No commentary.
"""


def chunk(d: dict[str, str], size: int = 15) -> list[dict[str, str]]:
    items = list(d.items())
    return [dict(items[i:i + size]) for i in range(0, len(items), size)]


async def translate_chunk(idx: int, chunk_map: dict[str, str]) -> dict[str, dict[str, str]]:
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"hardcoded-7b1-{idx}",
        system_message=LAW,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    prompt = (
        "Translate / restraint-normalize the following UI strings. "
        "Output JSON ONLY with { key: {en, ru, uk} }.\n\n"
        + json.dumps(chunk_map, ensure_ascii=False, indent=2)
    )
    resp = await chat.send_message(UserMessage(text=prompt))

    text = resp.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def main() -> None:
    src = json.loads(IN_PATH.read_text())
    print(f"Loaded {len(src)} EN keys from {IN_PATH}")

    chunks = chunk(src, 15)
    out: dict[str, dict[str, str]] = {}
    for i, ck in enumerate(chunks):
        print(f"→ chunk {i + 1}/{len(chunks)} ({len(ck)} keys)")
        result = await translate_chunk(i, ck)
        # validation
        for k in ck:
            entry = result.get(k)
            if isinstance(entry, dict) and all(
                isinstance(entry.get(x), str) and entry[x].strip()
                for x in ("en", "ru", "uk")
            ):
                out[k] = entry
            else:
                print(f"  ⚠️  invalid entry for {k!r}: {entry!r}")
        print(f"   ✓ {len(out)} accepted so far")

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print()
    print(f"Wrote {len(out)} translations → {OUT_PATH}")
    if len(out) < len(src):
        miss = sorted(set(src) - set(out))
        print(f"⚠️  Missing for {len(miss)} keys: {miss}")


if __name__ == "__main__":
    asyncio.run(main())
