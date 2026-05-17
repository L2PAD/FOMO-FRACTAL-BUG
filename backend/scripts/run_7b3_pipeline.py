"""
Generic Hardcoded i18n Pipeline — Task 7B-3 driver
====================================================

Reads `_7b3_targets.json` and runs the full pipeline over arbitrary
N files:

  1. extract       → _combined.en.json (per-prefix slug)
  2. translate     → _translations.json (EN normalized only when needed,
                                          RU + UK under Translation Law)
  3. fix_ru_contamination → patches RU slot when LLM contaminated it
  4. inject + refactor    → updates i18n.ts + rewrites JSX
  5. verify        → re-scans and reports remaining hardcoded

This file is self-contained — it imports the shared helpers from the
existing 7B-1 / 7B-2 scripts.
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
sys.path.insert(0, "/app/backend/scripts")

from extract_hardcoded import extract            # noqa: E402
from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
OUT_DIR = Path("/app/backend/scripts/hardcoded_extract")
TARGETS_JSON = OUT_DIR / "_7b3_targets.json"
COMBINED_EN = OUT_DIR / "_7b3_combined.en.json"
TRANS_PATH = OUT_DIR / "_7b3_translations.json"
I18N_PATH = Path("/app/frontend/src/core/i18n.ts")


# ─── Translation Law (slightly relaxed copy-rewriting per 7B-3 spec) ───
LAW = """
You localise UI strings for a cognitive trading infrastructure under
TRUTHFUL DEGRADATION.

For each EN input string, emit { en, ru, uk }.

EN policy for 7B-3 (final sweep):
  • If the source string contains ONLY casino / predictive vocabulary —
    "signal", "trade", "entry", "prediction", "profit", "win", "alpha",
    "setup" used as bait — soften it to observational language:
      observation / alignment / structure / context / deployment / restraint.
  • Otherwise keep the EN source unchanged.
  • NEVER rewrite layout, NEVER change UX intent, NEVER add or remove
    information.

RU rules: forbidden vocabulary:
  сигнал, сделка, прибыль, профит, альфа, точка входа, гарантировано,
  высокоточный, агрессивный, максимальный профит, HODL, мунить, шортить.
Preferred: структура, выравнивание, давление, контекст, наблюдение, режим,
сжатие/расширение, сдержанность, неопределённость, ясность.

UK rules: forbidden vocabulary:
  сигнал, угода, прибуток, перемога, виграш, альфа, точка входу,
  гарантовано, високоточний, агресивний, максимальний прибуток,
  HODL, мунити, шортити.
Preferred: структура, вирівнювання, тиск, контекст, спостереження, режим,
розширення/стиснення, стриманість, невизначеність, ясність.

BRAND INVARIANTS (NEVER translate):
  FOMO, Trading OS, PRO, FREE, Telegram, BTC, ETH, SOL, USDT, USD, Stripe,
  NOWPayments, Edge, Observatory.

UI: keep length close to source; preserve {placeholders}; mobile-first.
Output JSON ONLY. Schema: { key: { en, ru, uk } }.
"""


# ─── Step 1: extract over all targets ──────────────────────────────────
def step_extract() -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Returns combined EN map and the list of (path, prefix) targets."""
    targets = json.loads(TARGETS_JSON.read_text())
    combined: dict[str, str] = {}
    used_keys: set[str] = set()

    for fp, prefix in targets:
        txt = Path(fp).read_text()
        mapping, _ = extract(txt, prefix)
        for k, v in mapping.items():
            # avoid cross-file key clashes
            if k in combined and combined[k] != v:
                # generate a unique suffix
                n = 2
                while f"{k}{n}" in combined:
                    n += 1
                combined[f"{k}{n}"] = v
            else:
                combined[k] = v
            used_keys.add(k)

    COMBINED_EN.write_text(json.dumps(combined, ensure_ascii=False, indent=2))
    print(f"[step 1] extracted {len(combined)} unique keys across {len(targets)} files")
    return combined, [(fp, p) for fp, p in targets]


# ─── Step 2: translate in chunks ───────────────────────────────────────
async def translate_chunk(idx: int, chunk: dict[str, str]) -> dict[str, dict[str, str]]:
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"hardcoded-7b3-{idx}",
        system_message=LAW,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    prompt = ("Translate / restraint-normalize. Output JSON ONLY "
              "{ key: {en, ru, uk} }.\n\n"
              + json.dumps(chunk, ensure_ascii=False, indent=2))
    resp = await chat.send_message(UserMessage(text=prompt))
    txt = resp.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*", "", txt)
        txt = re.sub(r"\s*```$", "", txt)
    try:
        return json.loads(txt)
    except Exception as e:
        print(f"  ⚠️  chunk {idx}: JSON parse error: {e}; raw[:300]={txt[:300]!r}")
        return {}


async def step_translate(combined: dict[str, str]) -> dict[str, dict[str, str]]:
    items = list(combined.items())
    chunks = [dict(items[i:i + 18]) for i in range(0, len(items), 18)]
    out: dict[str, dict[str, str]] = {}
    for i, ck in enumerate(chunks):
        print(f"[step 2] chunk {i + 1}/{len(chunks)} ({len(ck)} keys)")
        res = await translate_chunk(i, ck)
        for k in ck:
            e = res.get(k)
            if isinstance(e, dict) and all(
                isinstance(e.get(x), str) and e[x].strip()
                for x in ("en", "ru", "uk")
            ):
                out[k] = e
        print(f"   ✓ {len(out)} accepted total")
    TRANS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out


# ─── Step 3: RU contamination repair ───────────────────────────────────
RU_LAW = """
Translate UI strings to RUSSIAN ONLY. Output JSON {key: ru}.
Forbidden RU: сигнал, сделка, прибыль, профит, альфа, точка входа,
гарантировано, высокоточный, агрессивный, максимальный профит.
Preferred: структура, выравнивание, давление, контекст, наблюдение, режим,
сжатие/расширение, сдержанность, неопределённость, ясность.
Brand invariants: FOMO, Trading OS, PRO, FREE, Telegram, BTC, ETH, SOL,
USDT, USD, Stripe, NOWPayments. No commentary.
"""


async def step_fix_ru(translations: dict[str, dict[str, str]]) -> int:
    contaminated = {k: m["en"] for k, m in translations.items() if m["ru"] == m["uk"]}
    if not contaminated:
        print("[step 3] no RU contamination")
        return 0
    print(f"[step 3] {len(contaminated)} contaminated RU entries — repairing")
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id="ru-fix-7b3",
                   system_message=RU_LAW).with_model(
        "anthropic", "claude-sonnet-4-5-20250929")
    prompt = "Translate to Russian only. JSON {key:ru}.\n\n" + \
        json.dumps(contaminated, ensure_ascii=False, indent=2)
    resp = await chat.send_message(UserMessage(text=prompt))
    txt = resp.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*", "", txt)
        txt = re.sub(r"\s*```$", "", txt)
    fixes = json.loads(txt)
    n = 0
    for k, ru in fixes.items():
        if k in translations and isinstance(ru, str) and ru.strip():
            translations[k]["ru"] = ru
            n += 1
    TRANS_PATH.write_text(json.dumps(translations, ensure_ascii=False, indent=2))
    print(f"  fixed {n} RU entries")
    return n


# ─── Step 4: inject + refactor ─────────────────────────────────────────
def parse_block(src: str, lang: str):
    m = re.search(rf"^  {lang}: \{{", src, re.M)
    if not m:
        return -1, -1, {}
    start = m.end(); depth = 1; i = start
    while i < len(src) and depth > 0:
        c = src[i]
        if c == "{": depth += 1
        elif c == "}": depth -= 1
        i += 1
    body = src[start: i - 1]
    pairs = {}
    for mm in re.finditer(r"^\s*'([^']+)':\s*'((?:[^'\\]|\\.)*)'", body, re.M):
        if mm.group(1) not in pairs:
            pairs[mm.group(1)] = mm.group(2)
    return m.start(), i, pairs


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def step_inject(translations: dict[str, dict[str, str]]) -> dict:
    src = I18N_PATH.read_text()
    summary = {}
    for lang in ("en", "ru", "uk"):
        start, end, existing = parse_block(src, lang)
        if start == -1:
            continue
        new_lines = []
        for k, m in translations.items():
            v = m.get(lang, "")
            if not v or k in existing:
                continue
            new_lines.append(f"    '{k}': '{esc(v)}',")
        if not new_lines:
            continue
        close_idx = end - 1
        line_start = src.rfind("\n", 0, close_idx) + 1
        insertion = "\n".join(new_lines) + "\n"
        src = src[:line_start] + insertion + src[line_start:]
        summary[lang] = len(new_lines)
    I18N_PATH.write_text(src)
    print(f"[step 4] inject: {summary}")
    return summary


RX_JSX_TEXT = re.compile(
    r"(>)([A-Z][A-Za-z][A-Za-z 0-9·.,!?\-:'/&]{2,120})(<)"
)
USER_PROPS = (
    "title", "placeholder", "label", "headline", "subline", "cta",
    "message", "description", "hint", "tooltip", "subtitle",
    "buttonText", "errorMessage", "emptyText"
)
RX_PROP = re.compile(
    rf'\b({"|".join(USER_PROPS)})="([A-Z][A-Za-z][A-Za-z 0-9·.,!?\-:\'/&]{{2,120}})"'
)


def compute_import_path(file_path: str) -> str:
    """Compute relative path from file to /app/frontend/src/core/i18n."""
    fp = Path(file_path)
    target = Path("/app/frontend/src/core/i18n")
    # depth from file dir
    rel = os.path.relpath(target, fp.parent)
    return rel.replace("\\", "/")


def step_refactor(targets: list[tuple[str, str]],
                  combined_en: dict[str, str]) -> int:
    """Replace literals in TSX with `t('key')` for each target."""
    literal_to_key = {v: k for k, v in combined_en.items()}
    total = 0
    for fp, prefix in targets:
        src = Path(fp).read_text()
        scoped = {lit: key for lit, key in literal_to_key.items()
                  if key.startswith(prefix + ".")}
        swaps = 0

        def jsx(m):
            nonlocal swaps
            v = m.group(2).strip()
            k = scoped.get(v)
            if not k:
                return m.group(0)
            swaps += 1
            return f"{m.group(1)}{{t('{k}')}}{m.group(3)}"

        def prop(m):
            nonlocal swaps
            p, v = m.group(1), m.group(2).strip()
            k = scoped.get(v)
            if not k:
                return m.group(0)
            swaps += 1
            return f"{p}={{t('{k}')}}"

        rx_alert = re.compile(
            r"Alert\.alert\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]"
        )

        def alert(m):
            nonlocal swaps
            t1, t2 = m.group(1).strip(), m.group(2).strip()
            k1, k2 = scoped.get(t1), scoped.get(t2)
            if not (k1 or k2):
                return m.group(0)
            n1 = f"t('{k1}')" if k1 else f"'{t1}'"
            n2 = f"t('{k2}')" if k2 else f"'{t2}'"
            if k1: swaps += 1
            if k2: swaps += 1
            return f"Alert.alert({n1}, {n2}"

        new = RX_JSX_TEXT.sub(jsx, src)
        new = RX_PROP.sub(prop, new)
        new = rx_alert.sub(alert, new)

        if swaps > 0 and "from '../" in new and " t " not in new[:1500]:
            # check if t import already imported
            if "from '../../core/i18n'" not in new and \
               "from '../../../core/i18n'" not in new and \
               "from '../../../../core/i18n'" not in new:
                rel = compute_import_path(fp)
                imp = f"\nimport {{ t }} from '{rel}';"
                # find last import
                last = None
                for m in re.finditer(r"^import [^;]+;\s*$", new, re.M):
                    last = m
                if last:
                    new = new[:last.end()] + imp + new[last.end():]

        if new != src:
            Path(fp).write_text(new)
        total += swaps
    print(f"[step 4-refactor] {total} literal→t() swaps across {len(targets)} files")
    return total


def step_verify(targets: list[tuple[str, str]]) -> int:
    """Re-extract and report remaining hardcoded."""
    leftover = 0
    issues = []
    for fp, prefix in targets:
        m, _ = extract(Path(fp).read_text(), prefix)
        if m:
            leftover += len(m)
            issues.append((fp, len(m)))
    if leftover == 0:
        print("[step 5] ✅ ZERO hardcoded remaining across all 7B-3 targets")
    else:
        print(f"[step 5] ⚠️  {leftover} hardcoded remaining:")
        for f, n in issues:
            print(f"   {f}: {n}")
    return leftover


async def main() -> None:
    combined, targets = step_extract()
    translations = await step_translate(combined)
    await step_fix_ru(translations)
    step_inject(translations)
    step_refactor(targets, combined)
    step_verify(targets)


if __name__ == "__main__":
    asyncio.run(main())
