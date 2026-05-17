# TERMINAL — ARCHIVED, DO NOT REVIVE

**Date archived:** 2026-05-12
**Sprint:** Terminal Removal Sprint
**Decision owner:** product
**Record:** /app/memory/TERMINAL_REMOVAL_SPRINT_2026-05-12.md

---

## What this file marks

The Trading Terminal subsystem (originally hosted under
`/app/F-TRADE-MODULE/` and routed via the `trading_terminal_gateway` to
side-car `:8002`) was deliberately retired from the production codebase.

It belonged to a different product paradigm — execution / brokerage UI / a
parallel React build — that diverged from the current line:
**Cognitive Trading Infrastructure / Operator Environment**.

The cognition core (TA, Sentiment, Fractal, Shadow, Outcome, Paper,
Observatory, MetaBrain) is **native FastAPI** and does NOT depend on the
side-car. Removing the terminal did NOT remove cognition.

---

## What was deleted

| Component                                                  | Type           | Status     |
|------------------------------------------------------------|----------------|------------|
| `/app/F-TRADE-MODULE/`                                     | Empty dir      | DELETED    |
| `backend/gateways/trading_terminal_gateway.py`             | Reverse proxy  | MOVED to `.<name>.REMOVED-2026-05-12` |
| `backend/admin_build/terminal-admin-inject.js`             | DOM injector   | MOVED to `.<name>.REMOVED` |
| `backend/admin_build/terminal-user-inject.js`              | DOM injector   | MOVED to `.<name>.REMOVED` |
| `backend/admin_build/terminal-inject.js.legacy`            | DOM injector   | MOVED to `.<name>.REMOVED` |
| `frontend/app/terminal.tsx`                                | Expo shim      | MOVED to `.terminal.tsx.REMOVED-2026-05-12` |
| `server.py` gateway include + SPA mount + degraded handlers| Code           | REMOVED    |
| `server.py` `_TERMINAL_USER_INJECT_JS` / `_TERMINAL_ADMIN_INJECT_JS` constants | Code | REMOVED |
| `_rewrite_admin_html` terminal sidebar injection block      | Code           | REMOVED    |
| `serve_admin` terminal-admin-inject append                  | Code           | REMOVED    |
| `TRADING_TERMINAL_UPSTREAM` env variable                    | Configuration  | REMOVED from `backend/.env` |

---

## What was kept (and why)

* `backend/modules/mbrain_adapters/trading_terminal_adapter.py` — **converted
  to honest stub**. Two consumers (`ta_shadow_fusion.py`, `routes/mbrain_shadow.py`)
  still import `get_signal` and `health`. Rather than break their import
  paths, the adapter now returns `{ok: False, error: "terminal_removed"}`
  envelopes without any HTTP call. The shadow-fusion pipeline reads the
  honest envelope and routes around the dead source — no inflated confidence,
  no fake bias.

---

## Rules for future agents

1. **DO NOT** recreate `/app/F-TRADE-MODULE/`.
2. **DO NOT** reinstate the `trading_terminal_gateway`.
3. **DO NOT** add `/api/terminal/*`, `/api/terminal-app/*`, `/terminal*` routes
   that proxy to or pretend to be a side-car.
4. **DO NOT** mock the terminal in tests as if it were running — the honest
   stub already provides the expected `ok=False` shape for fusion logic.
5. If a product decision genuinely revives terminal-class execution, do it
   under a new, native FastAPI module (no side-car, no parallel React build).

---

## Honest-404 contract

Any path under `/api/terminal*`, `/api/terminal-app*`, or `/terminal*` now
falls through to the global catch-all (Stabilization Sprint C4) and returns:

```json
{
  "ok": false,
  "error": "not_found",
  "path": "/api/terminal/...",
  "method": "GET",
  "detail": "This route is not registered in FastAPI. ..."
}
```

That is the canonical behaviour. Do not replace it with a 503
"terminal_unavailable" contract — that contract was itself archived as a
phantom degraded surface.
