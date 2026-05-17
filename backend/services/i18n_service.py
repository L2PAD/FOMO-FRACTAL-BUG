"""
i18n_service.py — server-side translation lookup for TG Mini-App.

Phase E1 / A2 — TG Mini-App server-side localization.

Single source of truth: `frontend/src/core/i18n.ts`, exported via
`frontend/scripts/generate-i18n-json.cjs` into `i18n_dictionary.json`
(co-located with this module).

Architecture principle: one language brain → two render surfaces.
The Expo client reads `i18n.ts` directly at runtime; the FastAPI backend
reads the JSON snapshot. Whenever `i18n.ts` is updated, the generator
script must be re-run before the backend is restarted, or the JSON file
will be stale.

Public API:
    resolve_locale(lang: str | None, accept_language: str | None = None) -> str
        Whitelist resolver. Returns one of {"en", "ru", "uk"}. Falls back
        to "en" for anything outside the whitelist or unknown.
    t(key: str, lang: str = "en", **placeholders) -> str
        Look up `key` in the locale; substitute `{name}` placeholders if
        provided. Falls back to EN if the key is missing in the requested
        locale, then to the raw key string if also missing in EN.
    locale_dict(lang: str) -> dict[str, str]
        Return the full {key: value} mapping for a locale.

The dictionary is loaded once at module import time. Hot-reload happens
by restarting the backend (acceptable given language strings rarely
change in production).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_DICT_PATH = os.path.join(_HERE, "i18n_dictionary.json")

WHITELIST = ("en", "ru", "uk")
DEFAULT_LOCALE = "en"


def _load() -> Dict[str, Dict[str, str]]:
    try:
        with open(_DICT_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        d = payload.get("dictionary", {})
        # Ensure every whitelisted locale exists, even if empty, so callers
        # can rely on `dict[locale]` access without KeyError noise.
        for loc in WHITELIST:
            d.setdefault(loc, {})
        log.info("i18n_service loaded: %s", {k: len(v) for k, v in d.items()})
        return d
    except FileNotFoundError:
        log.warning("i18n_service: dictionary missing at %s — TG locale will fall back to raw keys", _DICT_PATH)
        return {loc: {} for loc in WHITELIST}
    except Exception as exc:  # pragma: no cover
        log.exception("i18n_service: failed to load dictionary: %s", exc)
        return {loc: {} for loc in WHITELIST}


_DICT: Dict[str, Dict[str, str]] = _load()


def resolve_locale(lang: Optional[str], accept_language: Optional[str] = None) -> str:
    """Pick a whitelisted locale.

    Priority:
      1. explicit `lang` query parameter (after lowercasing + trimming "-region")
      2. first whitelisted match from Accept-Language header
      3. DEFAULT_LOCALE ("en")
    """
    if lang:
        candidate = lang.strip().lower().split("-")[0]
        if candidate in WHITELIST:
            return candidate
    if accept_language:
        for token in accept_language.split(","):
            tag = token.strip().split(";")[0].lower().split("-")[0]
            if tag in WHITELIST:
                return tag
    return DEFAULT_LOCALE


def locale_dict(lang: str) -> Dict[str, str]:
    return _DICT.get(lang) or _DICT.get(DEFAULT_LOCALE, {})


def t(key: str, lang: str = DEFAULT_LOCALE, **placeholders: Any) -> str:
    """Translate a key, substituting `{name}` placeholders.

    Fallback chain: requested locale → EN → raw key.
    """
    bucket = locale_dict(lang)
    value = bucket.get(key)
    if value is None:
        value = _DICT.get(DEFAULT_LOCALE, {}).get(key, key)
    if placeholders:
        try:
            return value.format(**placeholders)
        except (KeyError, IndexError, ValueError):
            return value
    return value
