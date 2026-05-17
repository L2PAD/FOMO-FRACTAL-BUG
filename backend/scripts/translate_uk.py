"""
UK Locale Parity — Task 7A Translation Script (2026-05-12)
==========================================================

Generates Ukrainian translations for the 245 missing keys in
`frontend/src/core/i18n.ts`, using Claude Sonnet 4.5 via Emergent
Universal Key, under a strict epistemic restraint contract.

OUTPUT: writes JSON map { key: uk_translation } to
        /app/backend/scripts/uk_translations_draft.json

The actual i18n.ts injection is done in a separate step after human
semantic review.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

I18N_PATH = Path("/app/frontend/src/core/i18n.ts")
OUT_PATH = Path("/app/backend/scripts/uk_translations_draft.json")
EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

# ─── EPISTEMIC TRANSLATION LAW ───────────────────────────────────────
TRANSLATION_LAW = """
You translate English UI strings to UKRAINIAN for a cognitive trading
infrastructure. The platform's defining philosophy is TRUTHFUL DEGRADATION:
it speaks observationally, not predictively; it never promises profit; it
never sounds like a casino, a hype crypto-Twitter feed, or a Binance clone.

ABSOLUTELY FORBIDDEN in your Ukrainian output (these words destroy the
platform's tone — even if the EN source is permissive):

  ❌ сигнал           (use: структурний сигнал, спостереження, or rephrase)
  ❌ угода             (use: позиція, рішення)
  ❌ прибуток          (use: результат, віддача, віддача структури)
  ❌ перемога / виграш
  ❌ альфа
  ❌ точка входу       (use: рівень розгортання, момент узгодженості)
  ❌ гарантовано
  ❌ високоточний / точний прогноз
  ❌ агресивний
  ❌ максимальний прибуток
  ❌ обережно — крипто-сленг: HODL, мунити, шортити

PREFERRED Ukrainian vocabulary families:

  ✓ структура / структурний
  ✓ вирівнювання / узгодженість
  ✓ тиск
  ✓ контекст
  ✓ спостереження
  ✓ режим
  ✓ розширення / стиснення
  ✓ стриманість / витримка
  ✓ невизначеність / непідтверджений
  ✓ ясність / прозорість

BRAND INVARIANTS — never translate these:
  • FOMO
  • Trading OS
  • PRO
  • Telegram
  • BTC / ETH / SOL / USDT / USD
  • Stripe / NOWPayments — keep as-is

UI CONVENTIONS:
  • Keep length close to the English source. UI is mobile-first; long
    Ukrainian phrases break layouts.
  • Buttons/CTAs: short, imperative-soft. e.g. "Unlock" → "Відкрити".
  • Section headers: nominal-noun phrasing, no period. e.g. "Action Plan"
    → "План дій".
  • Error/status: literal but plain. e.g. "Failed to load" →
    "Не вдалось завантажити".
  • Marketing copy: soft, observational. NEVER hype. e.g. "Be first to
    know" → "Бачити раніше за інших" — NOT "Дізнавайся миттєво!".

If an EN string contains a placeholder like `{count}` or `{name}` or
`{plan}`, preserve it VERBATIM in your translation.

Output JSON ONLY — no commentary, no explanation. Schema:
  { "<key>": "<ukrainian translation>", ... }
"""


# ─── i18n parser ──────────────────────────────────────────────────────
def parse_locale_block(text: str, lang: str) -> dict[str, str]:
    m = re.search(rf"^  {lang}: \{{", text, re.M)
    if not m:
        return {}
    start = m.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    body = text[start: i - 1]
    pairs: dict[str, str] = {}
    for mm in re.finditer(r"^\s*'([^']+)':\s*'((?:[^'\\]|\\.)*)'", body, re.M):
        if mm.group(1) not in pairs:
            pairs[mm.group(1)] = mm.group(2)
    return pairs


# ─── Category routing (priority order per sprint contract) ───────────
PRIORITY_ORDER = [
    ("paywall", lambda k: k.startswith("paywall.")),
    ("pro+sub", lambda k: k.startswith("pro.") or k.startswith("sub.")),
    ("home+edge+feed", lambda k: k.startswith(("home.", "edge.", "feed."))),
    ("security+2fa+account", lambda k: k.startswith(("security.", "2fa.", "account."))),
    ("prefs+notif", lambda k: k.startswith(("prefs.", "notif."))),
    ("welcome+about+telegram+connected+general+profile", lambda k:
        k.startswith(("welcome.", "about.", "telegram.", "connected.",
                      "general.", "profile."))),
    ("referrals+trade", lambda k: k.startswith(("referrals.", "trade."))),
    ("residual_no_prefix", lambda k: "." not in k),
]


def categorize(missing_en: dict[str, str]) -> dict[str, dict[str, str]]:
    buckets: dict[str, dict[str, str]] = {name: {} for name, _ in PRIORITY_ORDER}
    buckets["other"] = {}
    for k, v in missing_en.items():
        placed = False
        for name, predicate in PRIORITY_ORDER:
            if predicate(k):
                buckets[name][k] = v
                placed = True
                break
        if not placed:
            buckets["other"][k] = v
    return buckets


# ─── LLM call ─────────────────────────────────────────────────────────
async def translate_batch(category: str, batch: dict[str, str]) -> dict[str, str]:
    """Send one categorized batch to Claude Sonnet 4.5 for translation."""
    if not batch:
        return {}
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"uk-parity-{category}",
        system_message=TRANSLATION_LAW,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    payload = json.dumps(batch, ensure_ascii=False, indent=2)
    prompt = (
        f"CATEGORY: {category}\n\n"
        f"Translate these EN UI strings to Ukrainian under the law above.\n"
        f"Return JSON ONLY, same keys, Ukrainian values.\n\n"
        f"{payload}"
    )
    msg = UserMessage(text=prompt)
    resp = await chat.send_message(msg)

    # Robust JSON extract (model may wrap in ```json fences)
    text = resp.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except Exception as e:
        print(f"  ⚠️  [{category}] JSON parse failed: {e}")
        print(f"     raw response (first 500): {text[:500]}")
        return {}
    return parsed


async def main():
    src = I18N_PATH.read_text()
    en = parse_locale_block(src, "en")
    uk = parse_locale_block(src, "uk")
    missing = {k: v for k, v in en.items() if k not in uk}

    print(f"EN keys:        {len(en)}")
    print(f"UK keys:        {len(uk)}")
    print(f"Missing in UK:  {len(missing)}")
    print()

    if not missing:
        print("Nothing to translate. Done.")
        return

    buckets = categorize(missing)
    results: dict[str, str] = {}

    for category, _ in PRIORITY_ORDER:
        batch = buckets.get(category, {})
        if not batch:
            continue
        print(f"→ [{category}] {len(batch)} keys ...")
        translated = await translate_batch(category, batch)
        for k, v in translated.items():
            if k in missing and isinstance(v, str) and v.strip():
                results[k] = v
        print(f"  ✓ got {len(translated)} translations")

    # any residual category
    residual = buckets.get("other", {})
    if residual:
        print(f"→ [other] {len(residual)} keys ...")
        translated = await translate_batch("other", residual)
        for k, v in translated.items():
            if k in missing and isinstance(v, str) and v.strip():
                results[k] = v
        print(f"  ✓ got {len(translated)} translations")

    # Sort by EN key order for clean diffs
    en_order = [k for k in en.keys() if k in results]
    ordered = {k: results[k] for k in en_order}

    OUT_PATH.write_text(json.dumps(ordered, ensure_ascii=False, indent=2))
    print()
    print(f"Wrote {len(ordered)} translations → {OUT_PATH}")
    if len(ordered) < len(missing):
        miss = sorted(set(missing) - set(ordered))
        print(f"⚠️  Missing translations for {len(miss)} keys: {miss[:10]}{' ...' if len(miss) > 10 else ''}")


if __name__ == "__main__":
    asyncio.run(main())
