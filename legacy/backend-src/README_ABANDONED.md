# ⚠️  ABANDONED — Legacy Node.js / TypeScript Sidecar

**Status:** QUARANTINED
**Date quarantined:** 2026-05-12
**Original path:** `/app/backend/src/`
**Quarantine path:** `/app/legacy/backend-src/`
**Authoritative runtime:** **FastAPI** (`/app/backend/server.py`)

---

## DO NOT

1. **DO NOT** import any module from this directory in active Python code.
2. **DO NOT** run `npx tsx src/server.ts` or any Node-based entry point.
3. **DO NOT** add new files, fix bugs, or refactor anything inside this tree.
4. **DO NOT** revive the `:8003` Node sidecar — it is dead by policy.
5. **DO NOT** index this directory in linters, type-checkers, test discovery,
   or IDE workspaces as part of the active app.
6. **DO NOT** assume any function here mirrors current FastAPI behaviour.
   The Truthful Degradation contract and the `CognitionSnapshot` contract
   live ONLY in `/app/backend/`.

---

## What this is

This is the **abandoned Node.js / TypeScript sidecar** that used to run on
port `:8003` and answered a parallel set of HTTP routes. It belonged to an
earlier product paradigm and was the source of large-scale architectural
drift:

- duplicate cognition surfaces (two backends pretending to be one)
- accidental "double truth" — agents could not tell which side was canonical
- merge debt from multiple half-finished sprints
- false ownership of routes that FastAPI already served
- grep / index pollution: 3 835 TS files (~34 MB) showing up in every
  code-wide search

The Stabilization Plateau (Phase D, 2026-05-11) made FastAPI the **single
canonical runtime**. The Terminal Removal Sprint (2026-05-12) removed the
last fantom surface for the Trading Terminal. This quarantine completes the
cleanup by physically separating the legacy tree from the active app.

---

## Why preserved (not deleted)

This tree is kept on disk for **archaeology only**:

- historical reference for how a particular feature looked before migration
- one-off seed scripts may still parse text from select TS files
  (e.g. `news-control/crypto-rss-feeds.ts` — read as plain text, never
  executed)

If a future feature needs logic from here, the rule is: **read, understand,
re-implement natively in FastAPI**. Do not re-link the legacy tree to the
runtime in any way.

---

## Inventory

| Metric           | Value |
|------------------|-------|
| Files            | 3 862 |
| TypeScript files | 3 835 |
| JSON files       | 3     |
| Total size       | ~34 MB |
| Top-level dirs   | `api/`, `bootstrap/`, `clients/`, `middleware/`, `jobs/`, `contracts/`, `aggregation/`, `shared/`, `common/`, `plugins/`, `workers/`, `db/`, `modules/`, `scripts/`, `config/`, `ws/`, `core/`, `infra/`, `onchain/` |

---

## Related migration records

- `/app/memory/FREEZE_POINT_phase-d-stabilization-plateau.md` — the freeze
  that made FastAPI canonical.
- `/app/memory/TERMINAL_REMOVAL_SPRINT_2026-05-12.md` — Trading Terminal
  sidecar removal (prerequisite for this quarantine).
- `/app/memory/LEGACY_TS_QUARANTINE_2026-05-12.md` — this quarantine sprint.
- `/app/legacy/TERMINAL_ARCHIVED.md` — terminal anti-revive guard.

---

## Runtime verification at quarantine time

| Check                                          | Result |
|------------------------------------------------|--------|
| Python `from src` / `import src` imports       | 0      |
| Active `backend/src` references in `.py` files | 0      |
| 203 Phase D invariant tests                    | PASS   |
| `/openapi.json`                                | 200 OK |
| `/api/miniapp/home`                            | 200 OK |
| Backend supervisor                             | RUNNING |
| Expo supervisor                                | RUNNING |

The only Python references that remained were:

1. `server.py::start_node_backend()` — already commented out at callsite,
   now converted to a quarantined `raise RuntimeError(...)` stub so any
   accidental invocation surfaces loudly.
2. `scripts/seed_news_sources.py` — re-pointed to
   `/app/legacy/backend-src/modules/news-control/crypto-rss-feeds.ts` with
   a quarantine comment. This is a read-only text parse, not an import.

---

## If a future agent reads this

You are looking at history. Do not attempt to "fix" or "complete" this
directory. The cognitive trading infrastructure is **native Python FastAPI**
and lives in `/app/backend/`. Anything you need to add belongs there, behind
the runtime contract in `services/runtime_contract.py` and the home composer
in `services/home_composer/`.

If you are tempted to import something from here, stop and re-implement it
natively. Truthful Degradation is platform law: do not let a dead tree
pretend to be a live one.
