"""
MBrain adapters package.

Each adapter in this package extracts an "intelligence ring" from an external
or isolated subsystem and normalises it to the unified MBrain signal envelope:

    {
        "source":     "<short_id>",         # e.g. "ta_terminal", "onchain"
        "asset":      "BTC",
        "bias":       "bullish" | "bearish" | "neutral",
        "signal":     -1.0 .. +1.0,         # numeric form of bias
        "confidence": 0.0  .. 1.0,
        "weight":     0.0  .. 1.0,          # adapter's recommended fusion weight
        "horizon":    "24H" | "7D" | "30D" | ...,
        "raw":        { ... },              # original upstream envelope (debug)
        "ok":         True,                 # False on failure
        "error":      None | "string"
    }

Hard rules for any adapter in this folder:
  * NEVER import code from a side-car module (e.g. /app/F-TRADE-MODULE/).
  * ALWAYS go through HTTP (the side-car gateway, or a public API).
  * Network errors MUST NOT crash the caller — return ok=False instead.
  * Adapters are STATELESS — no DB writes, no caching across calls (the
    fusion layer in MBrain owns caching policy).

A new adapter is added by:
  1. Creating `<name>_adapter.py` in this directory.
  2. Exposing a single public function `get_signal(asset: str, ...) -> dict`.
  3. Adding the import + dispatch in MBrain's fusion stack (out of scope here).
"""
