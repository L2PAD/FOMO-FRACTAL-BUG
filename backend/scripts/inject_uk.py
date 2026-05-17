"""
UK Locale Inject — Task 7A (2026-05-12)
========================================
Reads `uk_translations_draft.json` and rewrites the `uk: { ... }` block
in `frontend/src/core/i18n.ts` so it matches the EN key order exactly.

* Drops orphan UK keys not present in EN.
* Preserves any UK translation that already existed (does not overwrite
  with the LLM draft).
* Keeps the rest of the file (other locales, imports, exports) untouched.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

I18N_PATH = Path("/app/frontend/src/core/i18n.ts")
DRAFT_PATH = Path("/app/backend/scripts/uk_translations_draft.json")


def parse_block(src: str, lang: str) -> tuple[int, int, dict[str, str]]:
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
    # i now points at the char AFTER the closing brace `}`
    return m.start(), i, pairs


def escape_quotes(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def build_block(lang: str, pairs_in_order: list[tuple[str, str]]) -> str:
    lines = [f"  {lang}: {{"]
    for k, v in pairs_in_order:
        lines.append(f"    '{k}': '{escape_quotes(v)}',")
    lines.append("  }")
    return "\n".join(lines)


def main() -> None:
    src = I18N_PATH.read_text()
    en_start, en_end, en = parse_block(src, "en")
    uk_start, uk_end, uk_existing = parse_block(src, "uk")

    draft: dict[str, str] = json.loads(DRAFT_PATH.read_text())

    # Final UK map: existing translations win over LLM draft (preserve any
    # hand-edited values), then fall back to draft, in EN key order.
    final: list[tuple[str, str]] = []
    missing: list[str] = []
    for k in en.keys():
        if k in uk_existing:
            final.append((k, uk_existing[k]))
        elif k in draft:
            final.append((k, draft[k]))
        else:
            missing.append(k)

    orphan_dropped = sorted(set(uk_existing) - set(en))

    new_block = build_block("uk", final)
    new_src = src[:uk_start] + new_block + src[uk_end:]

    I18N_PATH.write_text(new_src)

    print(f"EN keys total:     {len(en)}")
    print(f"UK before:         {len(uk_existing)}")
    print(f"UK after:          {len(final)}")
    print(f"Draft fed in:      {len(draft)}")
    print(f"Preserved hand UK: {len([k for k,_ in final if k in uk_existing])}")
    print(f"From draft:        {len([k for k,_ in final if k not in uk_existing])}")
    print(f"Orphans dropped:   {len(orphan_dropped)} — {orphan_dropped}")
    print(f"Still missing:     {len(missing)} {missing if missing else ''}")


if __name__ == "__main__":
    main()
