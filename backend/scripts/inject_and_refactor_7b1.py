"""
Hardcoded i18n Inject + Refactor — Task 7B-1 (2026-05-12)
==========================================================

Reads the translations doc emitted by `translate_hardcoded.py` and:

  1. Inserts 45 new keys into each of `en:`, `ru:`, `uk:` blocks of
     `frontend/src/core/i18n.ts`, preserving the file's quote style and
     existing order. Skips keys that already exist (idempotent).

  2. Refactors the 4 target TSX files:
       a. Re-runs the extractor to get fresh (literal → key) mapping.
       b. Replaces user-visible string literals with `{t('key')}` (JSX
          text) or `t('key')` (props / Alert.alert / string assignments).
       c. Adds `import { t } from '../../../core/i18n';` if not present.

       Brand invariants (FOMO, PRO, Telegram, BTC, ETH, SOL, USDT)
       are not extracted, so they remain literal.

  3. Verifies parity (EN/RU/UK counts equal) and prints a summary.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ─── paths ─────────────────────────────────────────────────────────────
TRANSLATIONS = Path("/app/backend/scripts/hardcoded_extract/_translations.json")
I18N_PATH = Path("/app/frontend/src/core/i18n.ts")

# (path, prefix, t_import_relative_path)
TARGETS = [
    (Path("/app/frontend/src/modules/intelligence/home/HomeScreen.tsx"),
     "homeIntel", "../../../core/i18n"),
    (Path("/app/frontend/src/modules/trading/home/HomeScreen.tsx"),
     "homeTrade", "../../../core/i18n"),
    (Path("/app/frontend/src/modules/intelligence/feed/FeedScreen.tsx"),
     "feed", "../../../core/i18n"),
    (Path("/app/frontend/src/modules/intelligence/profile/GrowthScreen.tsx"),
     "growth", "../../../core/i18n"),
]


# ─── i18n.ts inject ────────────────────────────────────────────────────
def parse_block_range(src: str, lang: str) -> tuple[int, int, dict[str, str]]:
    m = re.search(rf"^  {lang}: \{{", src, re.M)
    if not m:
        return -1, -1, {}
    start = m.end()
    depth = 1
    i = start
    while i < len(src) and depth > 0:
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    body = src[start: i - 1]
    pairs: dict[str, str] = {}
    for mm in re.finditer(r"^\s*'([^']+)':\s*'((?:[^'\\]|\\.)*)'", body, re.M):
        if mm.group(1) not in pairs:
            pairs[mm.group(1)] = mm.group(2)
    return m.start(), i, pairs


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def inject_i18n(translations: dict[str, dict[str, str]]) -> dict[str, int]:
    src = I18N_PATH.read_text()
    summary = {"en_added": 0, "ru_added": 0, "uk_added": 0,
               "en_skipped": 0, "ru_skipped": 0, "uk_skipped": 0}

    for lang in ("en", "ru", "uk"):
        start, end, existing = parse_block_range(src, lang)
        if start == -1:
            print(f"⚠️  block {lang!r} not found")
            continue

        # build addendum lines for keys not yet present
        new_lines: list[str] = []
        for k, m in translations.items():
            v = m.get(lang, "")
            if not v:
                summary[f"{lang}_skipped"] += 1
                continue
            if k in existing:
                summary[f"{lang}_skipped"] += 1
                continue
            new_lines.append(f"    '{k}': '{esc(v)}',")
            summary[f"{lang}_added"] += 1

        if not new_lines:
            continue

        # insert the new lines RIGHT BEFORE the closing brace of the lang block.
        # `end` points one past the `}` — back up to find it.
        # The closing brace is at index end-1, find the newline before it.
        close_idx = end - 1
        # find the start of the line containing `}`
        line_start = src.rfind("\n", 0, close_idx) + 1
        insertion = "\n".join(new_lines) + "\n"
        src = src[:line_start] + insertion + src[line_start:]

    I18N_PATH.write_text(src)
    return summary


# ─── JSX refactor ──────────────────────────────────────────────────────
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
# ternary / assignment string literal (heuristic — applies in JSX-leaning blocks)
RX_TERN_STR = re.compile(
    r"(\?|:|=|\(|,|\s)\s*(['\"])([A-Z][A-Za-z][A-Za-z 0-9·.,!?\-:'/&]{4,120})\2"
)


def refactor_file(path: Path, prefix: str, en_old_to_key: dict[str, str],
                  import_path: str) -> tuple[int, int]:
    src = path.read_text()
    swaps = 0

    # Replace JSX text
    def jsx_repl(m: re.Match) -> str:
        nonlocal swaps
        val = m.group(2).strip()
        key = en_old_to_key.get(val)
        if not key:
            return m.group(0)
        swaps += 1
        return f"{m.group(1)}{{t('{key}')}}{m.group(3)}"
    src_new = RX_JSX_TEXT.sub(jsx_repl, src)

    # Replace prop="..."
    def prop_repl(m: re.Match) -> str:
        nonlocal swaps
        prop, val = m.group(1), m.group(2).strip()
        key = en_old_to_key.get(val)
        if not key:
            return m.group(0)
        swaps += 1
        return f"{prop}={{t('{key}')}}"
    src_new = RX_PROP.sub(prop_repl, src_new)

    # Replace Alert.alert('Title', 'Message', ...)
    rx_alert = re.compile(
        r"Alert\.alert\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]"
    )

    def alert_repl(m: re.Match) -> str:
        nonlocal swaps
        title, msg = m.group(1).strip(), m.group(2).strip()
        tk = en_old_to_key.get(title)
        mk = en_old_to_key.get(msg)
        if not (tk or mk):
            return m.group(0)
        new_title = f"t('{tk}')" if tk else f"'{title}'"
        new_msg = f"t('{mk}')" if mk else f"'{msg}'"
        if tk: swaps += 1
        if mk: swaps += 1
        return f"Alert.alert({new_title}, {new_msg}"
    src_new = rx_alert.sub(alert_repl, src_new)

    # Replace ternary / assignment string literals (e.g. const x = 'Foo Bar')
    def tern_repl(m: re.Match) -> str:
        nonlocal swaps
        pre, _quote, val = m.group(1), m.group(2), m.group(3).strip()
        key = en_old_to_key.get(val)
        if not key:
            return m.group(0)
        swaps += 1
        return f"{pre}t('{key}')"
    src_new = RX_TERN_STR.sub(tern_repl, src_new)

    # Inject `import { t } from '<import_path>'` if missing
    if swaps > 0 and "from '../../core/i18n'" not in src_new and "from '../../../core/i18n'" not in src_new:
        # find last `import ... from '...';` and append after it
        last = None
        for m in re.finditer(r"^import [^;]+;\s*$", src_new, re.M):
            last = m
        new_import = f"\nimport {{ t }} from '{import_path}';"
        if last:
            src_new = src_new[:last.end()] + new_import + src_new[last.end():]
        else:
            src_new = new_import.lstrip() + "\n" + src_new

    if src_new != src:
        path.write_text(src_new)

    return swaps, len(en_old_to_key)


def main() -> None:
    trans = json.loads(TRANSLATIONS.read_text())
    print(f"Loaded {len(trans)} translations")

    # 1) Inject into i18n.ts
    print()
    print("=== STEP 1 — inject into i18n.ts ===")
    summary = inject_i18n(trans)
    print(json.dumps(summary, indent=2))

    # 2) Build (literal → key) per prefix
    print()
    print("=== STEP 2 — JSX refactor ===")

    # Use OLD EN literals (the in-source text) → new key.
    # We need to find OLD literal in source, not normalized EN — because
    # the source file still has the un-normalized text.
    combined_en = json.loads(
        Path("/app/backend/scripts/hardcoded_extract/_combined.en.json").read_text())
    # invert: literal -> key
    literal_to_key = {v: k for k, v in combined_en.items()}

    for path, prefix, import_path in TARGETS:
        # filter to this prefix's keys for clarity (not strictly required)
        scoped = {lit: key for lit, key in literal_to_key.items()
                  if key.startswith(prefix + ".")}
        swaps, n_keys = refactor_file(path, prefix, scoped, import_path)
        print(f"  {path.name:<40s} swaps={swaps:3d}  / keys_scoped={n_keys}")

    # 3) Verify parity
    print()
    print("=== STEP 3 — verify parity ===")
    src = I18N_PATH.read_text()
    for lang in ("en", "ru", "uk"):
        _, _, d = parse_block_range(src, lang)
        print(f"  {lang}: {len(d)} keys")


if __name__ == "__main__":
    main()
