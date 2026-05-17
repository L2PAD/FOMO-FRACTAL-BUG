/**
 * taService — canonical HTTP client for the TA/Trading module (Phase A.2).
 *
 * ────────────────────────────────────────────────────────────────────────
 *   All calls go through `/api/ta/*` — the canonical namespace introduced
 *   in Phase A.1. The backend alias layer transparently proxies to the
 *   legacy handlers, so responses are byte-identical.
 *
 *   Rule of thumb:
 *     • New code MUST import from here — never touch `/api/runtime/*`,
 *       `/api/trace/*`, `/api/analytics/*`, `/api/learning/*` directly.
 *     • Existing code is MIGRATED opportunistically — not in a single
 *       rewrite pass (see plan_project.md, Phase A).
 *
 *   Contract source of truth:
 *     /app/memory/MODULE_TA_API_CONTRACT.md
 * ────────────────────────────────────────────────────────────────────────
 */

// REACT_APP_BACKEND_URL is injected at build time and already points at the
// ingress-mapped backend (e.g. https://market-analysis-dev-2.preview…).
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

/** Canonical namespace root. All TA endpoints hang off this prefix. */
export const TA_API_ROOT = '/api/ta';

// ─────────────────────────────────────────────────────────────────────────
// Tiny fetch wrapper — honours standard Response contract + surfaces errors.
// Intentionally minimal — we do NOT add retries, caching, auth, etc. here.
// Those concerns belong to a higher-level hook / store.
// ─────────────────────────────────────────────────────────────────────────
async function _request(method, path, { body, params, headers, signal } = {}) {
  let url = `${BACKEND_URL}${TA_API_ROOT}${path}`;

  if (params && Object.keys(params).length > 0) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) qs.append(k, String(v));
    }
    const qsStr = qs.toString();
    if (qsStr) url += `?${qsStr}`;
  }

  const init = {
    method,
    headers: { 'Content-Type': 'application/json', ...(headers || {}) },
    // Forward cookies for any auth/session-based handlers. The backend CORS
    // layer is configured with `allow_origins=["*"]`; browsers will only
    // attach cookies when the server opts in, so this is cheap insurance.
    credentials: 'include',
    signal,
  };
  if (body !== undefined) init.body = JSON.stringify(body);

  // Dev-only debug trace — makes module traffic easy to spot in the
  // browser console without any runtime cost in production builds.
  if (process.env.NODE_ENV === 'development') {
    // eslint-disable-next-line no-console
    console.debug('[TA API]', method, url);
  }

  const resp = await fetch(url, init);
  // Preserve original response shape — caller decides how to parse.
  // For convenience we try JSON first and fall back to text.
  const contentType = resp.headers.get('content-type') || '';
  let data = null;
  if (contentType.includes('application/json')) {
    data = await resp.json().catch(() => null);
  } else {
    data = await resp.text().catch(() => null);
  }

  if (!resp.ok) {
    const err = new Error(
      `taService ${method} ${path} failed: ${resp.status} ${resp.statusText}`
    );
    err.status = resp.status;
    err.data = data;
    err.url = url;
    throw err;
  }
  return data;
}

// Shortcuts
const _get = (path, opts) => _request('GET', path, opts);
const _post = (path, body, opts) => _request('POST', path, { ...opts, body });
const _put = (path, body, opts) => _request('PUT', path, { ...opts, body });
const _delete = (path, opts) => _request('DELETE', path, opts);

// ═════════════════════════════════════════════════════════════════════════
// RUNTIME — operational control of the auto-runner (signal loop, daemon,
// symbols, mode, start/stop).
// Maps to /api/ta/runtime/* → legacy /api/runtime/*.
// ═════════════════════════════════════════════════════════════════════════
export const taRuntime = {
  /** Current runtime state: enabled, mode, status, symbols, intervals. */
  getState: (opts) => _get('/runtime/state', opts),

  /** Start the auto-runner. */
  start: (opts) => _post('/runtime/start', undefined, opts),

  /** Stop the auto-runner. */
  stop: (opts) => _post('/runtime/stop', undefined, opts),

  /**
   * Set execution mode.
   * @param {"AUTO"|"MANUAL"|"PAPER"|"DRY_RUN"} mode
   */
  setMode: (mode, opts) => _post('/runtime/mode', { mode }, opts),

  /**
   * Replace the watched-symbols list.
   * @param {string[]} symbols  e.g. ["BTCUSDT", "ETHUSDT"]
   */
  setSymbols: (symbols, opts) => _post('/runtime/symbols', { symbols }, opts),

  /**
   * Set the main signal-loop interval in seconds.
   * @param {number} interval_sec
   */
  setInterval: (interval_sec, opts) =>
    _post('/runtime/interval', { interval_sec }, opts),

  /** Execute a single run of the signal loop manually. */
  runOnce: (opts) => _post('/runtime/run-once', undefined, opts),

  // ── Decisions sub-resource ────────────────────────────────────────────
  decisions: {
    /** List decisions awaiting approval. */
    listPending: (opts) => _get('/runtime/decisions/pending', opts),

    /** Approve a decision by id. */
    approve: (decisionId, opts) =>
      _post(
        `/runtime/decisions/${encodeURIComponent(decisionId)}/approve`,
        undefined,
        opts
      ),

    /** Reject a decision by id. */
    reject: (decisionId, reason = '', opts) =>
      _post(
        `/runtime/decisions/${encodeURIComponent(decisionId)}/reject`,
        { reason },
        opts
      ),

    /**
     * Operator note for a decision (lives under /api/ta/decisions/{id}/note,
     * aliased to legacy /api/decisions/{id}/note via Phase A.1.1).
     * Pure transport — no trimming, no validation, no defaults.
     * Backend Pydantic NoteRequest expects key `note` (not text/content).
     */
    note: (decisionId, noteText, opts) =>
      _post(
        `/decisions/${encodeURIComponent(decisionId)}/note`,
        { note: noteText },
        opts
      ),
  },

  // ── Daemon sub-resource (background orchestrator) ────────────────────
  daemon: {
    start: (opts) => _post('/runtime/daemon/start', undefined, opts),
    stop: (opts) => _post('/runtime/daemon/stop', undefined, opts),
    getStatus: (opts) => _get('/runtime/daemon/status', opts),
  },

  // ── Risk status (lives under /api/runtime/risk-*) ────────────────────
  risk: {
    getStatus: (opts) => _get('/runtime/risk-status', opts),
    reset: (opts) => _post('/runtime/risk-reset', undefined, opts),
  },
};

// ═════════════════════════════════════════════════════════════════════════
// TRACE — decision-trace introspection (live + historical).
// Maps to /api/ta/runtime/trace/* → legacy /api/trace/*.
// ═════════════════════════════════════════════════════════════════════════
export const taTrace = {
  /**
   * Latest traces across all symbols.
   * @param {object} [opts]
   * @param {number} [opts.limit]  Max traces to return (server default applies if omitted).
   * @param {AbortSignal} [opts.signal]
   */
  getLatest: ({ limit, ...rest } = {}) =>
    _get(
      '/runtime/trace/latest',
      limit !== undefined ? { ...rest, params: { limit } } : rest
    ),

  /** Aggregate trace statistics (counts, breakdowns). */
  getStats: (opts) => _get('/runtime/trace/stats', opts),

  /** Fetch a single trace document by id. */
  getById: (traceId, opts) =>
    _get(`/runtime/trace/${encodeURIComponent(traceId)}`, opts),

  /** All traces for a given symbol. */
  getBySymbol: (symbol, opts) =>
    _get(`/runtime/trace/symbol/${encodeURIComponent(symbol)}`, opts),
};

// ═════════════════════════════════════════════════════════════════════════
// ANALYTICS — performance, risk and execution summaries.
// Maps to /api/ta/analytics/* → legacy /api/analytics/*.
// ═════════════════════════════════════════════════════════════════════════
export const taAnalytics = {
  /** Global decision-quality rollup (win-rate, PF, slippage, …). */
  getDecisionQuality: (opts) => _get('/analytics/decision-quality', opts),

  /** Aggregate dynamic-risk summary. */
  getDynamicRiskSummary: (opts) => _get('/analytics/dynamic-risk/summary', opts),

  /** Reasons / explanation for dynamic-risk state changes. */
  getDynamicRiskReasons: (opts) => _get('/analytics/dynamic-risk/reasons', opts),

  /** Execution-layer summary (fills, slippage, latency). */
  getExecutionSummary: (opts) => _get('/analytics/execution/summary', opts),

  /** Safety-layer summary (kill-switches, breakers). */
  getSafetySummary: (opts) => _get('/analytics/safety/summary', opts),

  /** Adaptive-risk summary. */
  getAdaptiveRiskSummary: (opts) => _get('/analytics/adaptive-risk/summary', opts),

  // ── Decisions outcome sub-resource ────────────────────────────────────
  decisions: {
    /** Aggregate outcome summary across all evaluated decisions. */
    getSummary: (opts) => _get('/analytics/decisions/summary', opts),

    /** Outcome + forensics for a single decision id. */
    getOutcome: (decisionId, opts) =>
      _get(`/analytics/decisions/outcome/${encodeURIComponent(decisionId)}`, opts),
  },
};

// ═════════════════════════════════════════════════════════════════════════
// LEARNING — pattern-extraction insights + (AF6) real-learning engine.
// Maps to /api/ta/learning/* → legacy /api/learning/*.
// Note: backend currently has TWO routers sharing this prefix
//       (modules.learning + alpha_factory.real_learning). Both are reachable
//       via the alias; taService exposes the union.
// ═════════════════════════════════════════════════════════════════════════
export const taLearning = {
  /** Liveness / identity probe. */
  getHealth: (opts) => _get('/learning/health', opts),

  /** Pattern-extraction insights (modules.learning). */
  getInsights: (opts) => _get('/learning/insights', opts),

  // ── AF6 real-learning engine ──────────────────────────────────────────
  /** Submit an outcome sample into the real-learning engine. */
  submitOutcome: (payload, opts) => _post('/learning/outcome', payload, opts),

  /** Current AF6 learning metrics. */
  getMetrics: (opts) => _get('/learning/metrics', opts),

  /** Historical outcomes stream. */
  getOutcomes: (params, opts) => _get('/learning/outcomes', { ...(opts || {}), params }),

  /** Summary rollup of the real-learning engine. */
  getSummary: (opts) => _get('/learning/summary', opts),

  // ── Shadow ML sub-resource (ETAP 4) ──────────────────────────────────
  // Read-side endpoints fuel the user-facing Shadow ML dashboard. The
  // write-side (train / infer) was moved to /admin/tech-analysis per
  // MOVE_V2_EXTRACTED.md — still exposed here for admin surfaces.
  shadow: {
    /** Service status + model readiness. */
    getStatus: (opts) => _get('/learning/shadow/status', opts),

    /** Prediction statistics for a horizon (defaults to "7d"). */
    getStats: (horizon = '7d', opts) =>
      _get('/learning/shadow/stats', { ...(opts || {}), params: { horizon } }),

    /** Recent shadow predictions (default limit 10). */
    getPredictions: (limit = 10, opts) =>
      _get('/learning/shadow/predictions', { ...(opts || {}), params: { limit } }),

    /** Evaluation report for a horizon. */
    getEvaluation: (horizon = '7d', opts) =>
      _get(`/learning/shadow/eval/${encodeURIComponent(horizon)}`, opts),

    /** Calibration data (snapshotId + horizon). */
    getCalibration: (snapshotId, horizon, opts) =>
      _get(
        `/learning/shadow/calibration/${encodeURIComponent(snapshotId)}/${encodeURIComponent(horizon)}`,
        opts
      ),

    // Admin-only (MOVE V-2): exposed under taLearning.shadow.* to keep
    // the namespace complete; UI callers should live under /admin/*.
    train: (payload, opts) => _post('/learning/shadow/train', payload, opts),
    infer: (payload, opts) => _post('/learning/shadow/infer', payload, opts),
  },
};

// ═════════════════════════════════════════════════════════════════════════
// Low-level escape hatch — use sparingly, only when adding a new endpoint
// before it's promoted into the typed namespaces above.
// ═════════════════════════════════════════════════════════════════════════
export const taRaw = {
  get: _get,
  post: _post,
  put: _put,
  delete: _delete,
};

// ─────────────────────────────────────────────────────────────────────────
// Default export — the whole canonical surface in a single object.
// Import whichever flavour you prefer:
//
//     import { taRuntime, taTrace } from 'modules/ta/services/taService';
//     import taService              from 'modules/ta/services/taService';
// ─────────────────────────────────────────────────────────────────────────
const taService = {
  runtime: taRuntime,
  trace: taTrace,
  analytics: taAnalytics,
  learning: taLearning,
  raw: taRaw,
  // Meta
  API_ROOT: TA_API_ROOT,
  BACKEND_URL,
};

export default taService;
