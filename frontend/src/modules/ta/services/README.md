# modules/ta/services — canonical TA/Trading HTTP client

**Phase:** A.2 · service layer scaffolding · no call-site migration yet.

## Why this exists

In Phase A.1 we introduced `/api/ta/*` as the **canonical namespace** of the
TA / Trading vertical (see `/app/memory/MODULE_TA_API_CONTRACT.md`). A thin
ASGI middleware on the backend transparently proxies every canonical request
to its legacy handler, so we get a real module boundary without breaking
anything.

This folder is the **client-side half** of that boundary. It gives the rest
of the frontend exactly one place to reach TA runtime / trace / analytics /
learning APIs. Nothing else in the codebase should open a `fetch()` to
`/api/runtime/*`, `/api/trace/*`, `/api/analytics/*` or `/api/learning/*`
directly.

## What lives here

```
modules/ta/services/
├── taService.js    ← single source of truth (typed wrappers)
├── index.js        ← public re-exports
└── README.md       ← this file
```

## Usage

```js
import { taRuntime, taTrace, taAnalytics, taLearning } from 'modules/ta/services';

// Runtime ───────────────────────────────────────
const state = await taRuntime.getState();
await taRuntime.start();
await taRuntime.setMode('AUTO');
await taRuntime.setSymbols(['BTCUSDT', 'ETHUSDT']);
const pending = await taRuntime.decisions.listPending();
await taRuntime.decisions.approve('auto-49125c117320');

// Trace ─────────────────────────────────────────
const latest = await taTrace.getLatest();
const byId = await taTrace.getById('trace-123');

// Analytics ─────────────────────────────────────
const quality = await taAnalytics.getDecisionQuality();
const exec = await taAnalytics.getExecutionSummary();

// Learning ──────────────────────────────────────
const health = await taLearning.getHealth();
const metrics = await taLearning.getMetrics();
```

## Rules

* ✅ **New code** — must import from `modules/ta/services`.
* ✅ **Bug-fix touching a call site** — opportunistically migrate it.
* ❌ **Do NOT** kick off a global rewrite of every existing `fetch('/api/…')`.
  That is Phase A.3+ and will be done by systematic sweep, not manually.
* ❌ **Do NOT** add business logic here. Shape/merge/transform belongs to the
  hooks / store (Phase A.3+), not the transport layer.

## Error handling

On non-2xx responses `_request` throws an `Error` with extras:

```js
try {
  await taRuntime.getState();
} catch (err) {
  err.status  // HTTP status code
  err.data    // parsed body (JSON when possible, else text)
  err.url     // the exact URL we tried
}
```

## Canonical → legacy mapping (for reference)

| taService call                          | Canonical                                  | Legacy                                |
| --------------------------------------- | ------------------------------------------ | ------------------------------------- |
| `taRuntime.getState()`                  | `/api/ta/runtime/state`                    | `/api/runtime/state`                  |
| `taRuntime.decisions.listPending()`     | `/api/ta/runtime/decisions/pending`        | `/api/runtime/decisions/pending`      |
| `taTrace.getLatest()`                   | `/api/ta/runtime/trace/latest`             | `/api/trace/latest`                   |
| `taAnalytics.getDecisionQuality()`      | `/api/ta/analytics/decision-quality`       | `/api/analytics/decision-quality`     |
| `taAnalytics.decisions.getSummary()`    | `/api/ta/analytics/decisions/summary`      | `/api/analytics/decisions/summary`    |
| `taLearning.getHealth()`                | `/api/ta/learning/health`                  | `/api/learning/health`                |

Both URLs return byte-identical JSON.

## Roadmap

* **A.2 (this folder)** — wrapper is live, zero call sites migrated yet.
* **A.3** — systematic migration sweep: find all
  `fetch('/api/{runtime,trace,analytics,learning}/…')` in `src/` and replace
  them with `taService.*` calls.
* **A.4** — add React-Query / SWR adapter for cached subscriptions.
* **B** — extend taService with `signal`, `decision`, `execution intent`
  higher-level contract methods (see Phase B in plan_project.md).
