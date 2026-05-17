"""
Hardcoded String Extractor — Task 7B-1
=======================================

For each target React/TSX file:
  1. Find user-visible string literals (JSX text + a curated set of
     string-valued props + Alert/Linking arguments).
  2. Generate a key proposal in the form `<prefix>.<slug>` using the
     filename + a slugged 4-word excerpt.
  3. Emit:
     - <name>.draft.json :: { key: en_string } (review artefact)
     - <name>.patched.tsx :: refactored source with `t('key')` calls
       AND import statement injected if missing.

This script does NOT call the LLM. RU/UK translation happens in a
follow-up pass.

USAGE:
    python /app/backend/scripts/extract_hardcoded.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ─── target files (7B-2 primary narrative surfaces) ────
TARGETS: list[tuple[Path, str]] = [
    (Path("/app/frontend/src/modules/intelligence/home/HomeScreen.tsx"),    "homeIntel"),
    (Path("/app/frontend/src/modules/trading/home/HomeScreen.tsx"),         "homeTrade"),
    (Path("/app/frontend/src/modules/intelligence/feed/FeedScreen.tsx"),    "feed"),
    (Path("/app/frontend/src/modules/intelligence/profile/GrowthScreen.tsx"), "growth"),
]

OUT_DIR = Path("/app/backend/scripts/hardcoded_extract")
OUT_DIR.mkdir(exist_ok=True)


# ─── extraction grammar ────────────────────────────────────────────────
RX_JSX_TEXT = re.compile(
    r"(>)([A-Z][A-Za-z][A-Za-z 0-9·.,!?\-:'/&]{2,120})(<)"
)
# string-valued props that ARE user-visible
USER_PROPS = (
    "title", "placeholder", "label", "headline", "subline", "cta",
    "message", "description", "hint", "tooltip", "subtitle",
    "buttonText", "errorMessage", "emptyText"
)
RX_PROP = re.compile(
    rf'\b({"|".join(USER_PROPS)})="([A-Z][A-Za-z][A-Za-z 0-9·.,!?\-:\'/&]{{2,120}})"'
)
RX_ALERT = re.compile(
    r"Alert\.alert\(\s*['\"]([A-Z][A-Za-z][A-Za-z 0-9·.,!?\-:'/&]{2,120})['\"]"
    r"\s*,\s*['\"]([A-Z][A-Za-z][A-Za-z 0-9·.,!?\-:'/&]{2,200})['\"]"
)
# ternary / variable string assignments inside JSX-leaning code
RX_STRING_ASSIGN = re.compile(
    r"=\s*['\"]([A-Z][A-Za-z][A-Za-z 0-9·.,!?\-:'/&]{4,120})['\"]"
)


CODE_BLACKLIST = {
    "RGBA", "RGB", "URL", "JSON", "URI", "API", "DOM",
    "PROD", "BETA",
}


def is_likely_user(s: str) -> bool:
    s = s.strip()
    if len(s) < 4:
        return False
    if s.isupper() and " " not in s and "·" not in s:
        return False  # constant
    if s in {"None", "True", "False", "Loading", "Failed", "Cancel",
             "Save", "Copy", "Confirm", "Apply", "Retry", "Error",
             "OK", "Ok"}:
        return False
    if s.startswith("http") or s.startswith("/api") or s.startswith("data:"):
        return False
    if " " not in s and len(s) < 12:
        return False
    if any(s == b for b in CODE_BLACKLIST):
        return False
    # ignore raw component / icon names
    if re.fullmatch(r"[A-Z][a-zA-Z0-9]+", s):
        return False
    return True


def slugify(s: str, max_words: int = 5) -> str:
    words = re.findall(r"[A-Za-z0-9]+", s.lower())[:max_words]
    return "".join(w.title() if i > 0 else w for i, w in enumerate(words)) or "str"


# ─── extraction ────────────────────────────────────────────────────────
def extract(text: str, prefix: str) -> tuple[dict[str, str], list[tuple[str, str, str]]]:
    """
    Returns:
      mapping :: { key: en_string }
      replacements :: list[(original_literal_in_source, key, kind)]
                       — kind ∈ {'jsx', 'prop:title', 'alert-title', 'alert-msg', 'assign'}
    """
    mapping: dict[str, str] = {}
    replacements: list[tuple[str, str, str]] = []
    used_keys: set[str] = set()

    def make_key(value: str) -> str:
        base = f"{prefix}.{slugify(value)}"
        k = base
        n = 2
        while k in used_keys:
            k = f"{base}{n}"
            n += 1
        used_keys.add(k)
        return k

    # JSX text content
    for m in RX_JSX_TEXT.finditer(text):
        val = m.group(2).strip()
        if not is_likely_user(val):
            continue
        if val in (v for v in mapping.values()):
            # reuse existing key for duplicates
            key = next(k for k, v in mapping.items() if v == val)
        else:
            key = make_key(val)
            mapping[key] = val
        replacements.append((val, key, "jsx"))

    # Props
    for m in RX_PROP.finditer(text):
        prop, val = m.group(1), m.group(2).strip()
        if not is_likely_user(val):
            continue
        if val in mapping.values():
            key = next(k for k, v in mapping.items() if v == val)
        else:
            key = make_key(val)
            mapping[key] = val
        replacements.append((val, key, f"prop:{prop}"))

    # Alerts
    for m in RX_ALERT.finditer(text):
        title, msg = m.group(1).strip(), m.group(2).strip()
        if is_likely_user(title):
            if title in mapping.values():
                t_key = next(k for k, v in mapping.items() if v == title)
            else:
                t_key = make_key(title)
                mapping[t_key] = title
            replacements.append((title, t_key, "alert-title"))
        if is_likely_user(msg):
            if msg in mapping.values():
                m_key = next(k for k, v in mapping.items() if v == msg)
            else:
                m_key = make_key(msg)
                mapping[m_key] = msg
            replacements.append((msg, m_key, "alert-msg"))

    return mapping, replacements


# ─── main ──────────────────────────────────────────────────────────────
def main() -> None:
    combined: dict[str, str] = {}
    summary: list[dict] = []

    for path, prefix in TARGETS:
        src = path.read_text()
        mapping, replacements = extract(src, prefix)
        summary.append({
            "file": str(path),
            "prefix": prefix,
            "keys_extracted": len(mapping),
            "replacements_in_source": len(replacements),
            "first_5_keys": list(mapping.items())[:5],
        })
        for k, v in mapping.items():
            if k not in combined:
                combined[k] = v

        # write per-file draft
        draft_path = OUT_DIR / f"{prefix}.draft.json"
        draft_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2))

    # combined draft for LLM RU+UK pass
    combined_path = OUT_DIR / "_combined.en.json"
    combined_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2))

    # human-readable summary
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print()
    print(f"Total unique keys: {len(combined)}")
    print(f"Combined EN map:  {combined_path}")


if __name__ == "__main__":
    main()
