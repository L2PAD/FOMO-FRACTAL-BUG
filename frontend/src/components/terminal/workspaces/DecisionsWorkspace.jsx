/**
 * Decisions Workspace — Trading Terminal
 *
 * PHASE 3 visual rebuild (2026-04-30):
 *   trace → decision (engine internals → decision intelligence layer)
 *
 * Changes confined to THIS file:
 *   • DaemonStrip removed (operator-tool, not trader-tool). Replaced
 *     with a single-line system status sentence.
 *   • StatsBar 5-coloured-boxes → 4-metric compact summary (no Pass Rate).
 *   • DecisionCard surfaces Confidence and Reason WITHOUT requiring a
 *     click — the two product-critical fields are visible up front.
 *   • Step timeline removed from inline card; "View analysis" opens
 *     the existing DecisionTimeline screen (advanced mode).
 *   • Status enum mapped to human words (PENDING → Waiting, etc.).
 *   • Side BUY/SELL → Long/Short for consistency with Positions/Trade.
 *   • APPROVE → Execute. ALL-CAPS gone. Filled coloured buttons gone.
 *   • Operator note hidden behind an "Add note" toggle.
 *   • emerald-* palette throughout, no inline hex.
 *
 * NOT TOUCHED:
 *   • API endpoints / payload shape / polling cadence (5s).
 *   • DecisionTimeline.jsx (rendered as-is when openTimeline is fired).
 *   • Approve/Reject lifecycle (POST /api/runtime/decisions/:id/...).
 *   • Operator-note endpoint (POST /api/decisions/:id/note).
 */

import { useState, useEffect, useCallback } from 'react';
import DecisionTimeline from '../timeline/DecisionTimeline';
// Phase A.3 Step 3 — trace reads go through canonical /api/ta/runtime/trace/*.
// Phase A.3 Step 4.1 — daemon/status (read-only) migrated too.
// Phase A.3 Step 4.3 (approve+reject+note) — full decisions lifecycle via
// canonical /api/ta/* (note resolves via Phase A.1.1 namespace alias).
// Integration — all TA calls on this screen go through ta-integration layer
// (taAdapter read, decisionBridge write). Direct taService access forbidden here.
import { taAdapter, decisionBridge } from '../../../modules/ta-integration';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ── Status enum → human label ────────────────────────────────
function mapStatus(status) {
  switch (status) {
    case 'PENDING':     return 'Waiting';
    case 'EXECUTED':    return 'Executed';
    case 'REJECTED':    return 'Rejected';
    case 'BLOCKED':     return 'Blocked';
    case 'IN_PROGRESS': return 'Analyzing';
    default:            return status || '—';
  }
}

function statusTone(status) {
  switch (status) {
    case 'EXECUTED':    return 'text-emerald-600';
    case 'PENDING':     return 'text-yellow-600';
    case 'REJECTED':    return 'text-red-600';
    case 'BLOCKED':     return 'text-orange-600';
    case 'IN_PROGRESS': return 'text-gray-600';
    default:            return 'text-gray-600';
  }
}

// ── Pull Confidence from the SIGNAL step (display-only, no math) ──
function getSignalConfidence(trace) {
  const s = trace?.steps?.find((x) => x.step === 'SIGNAL');
  const c = s?.data?.confidence;
  if (typeof c !== 'number' || !Number.isFinite(c)) return null;
  // Same display convention as the previous StepRow used:
  // backend returns 0..1 → percent. No business math, just formatting.
  return Math.round(c * 100);
}

// ── Decision Card ────────────────────────────────────────────
function DecisionCard({ trace, onApprove, onReject, onOpenTimeline }) {
  const [loading, setLoading] = useState(false);
  const [showNote, setShowNote] = useState(false);
  const [note, setNote] = useState('');
  const [noteSaved, setNoteSaved] = useState(false);

  const isPending = trace.final_status === 'PENDING';
  const isLong = trace.side === 'BUY';
  const confidence = getSignalConfidence(trace);
  const reason = trace.final_reason || 'No clear signal';

  // Decision id, used by Approve / Reject / Note actions.
  const decStep = trace.steps?.find(
    (s) => s.step === 'PENDING_CREATED' || s.step === 'OPERATOR_CREATED'
  );
  const decisionId = decStep?.data?.decision_id;

  const persistNote = async () => {
    if (!note.trim() || !decisionId) return;
    // trim() stays here on the caller (integration layer is pure transport).
    await decisionBridge.note(decisionId, note.trim());
  };

  const doExecute = async () => {
    if (!decisionId) return;
    setLoading(true);
    if (note.trim()) await persistNote();
    try { await onApprove(decisionId); } finally { setLoading(false); }
  };

  const doReject = async () => {
    if (!decisionId) return;
    setLoading(true);
    if (note.trim()) await persistNote();
    try { await onReject(decisionId); } finally { setLoading(false); }
  };

  const saveNote = async () => {
    await persistNote();
    setNoteSaved(true);
    setTimeout(() => setNoteSaved(false), 2000);
  };

  return (
    <div
      className="bg-white border border-gray-200 rounded-lg p-4"
      data-testid={`decision-card-${trace.trace_id}`}
    >
      {/* Header — symbol + side pill + human status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="font-medium text-gray-900">{trace.symbol}</div>
          <span
            className={`text-xs px-2 py-0.5 rounded-full ${
              isLong
                ? 'bg-emerald-50 text-emerald-600'
                : 'bg-red-50 text-red-600'
            }`}
          >
            {isLong ? 'Long' : 'Short'}
          </span>
        </div>
        <div className={`text-sm ${statusTone(trace.final_status)}`}>
          {mapStatus(trace.final_status)}
        </div>
      </div>

      {/* Body — Confidence + Reason are visible WITHOUT a click. */}
      <div className="mt-3 text-sm">
        <div className="text-gray-500">Confidence</div>
        <div className="text-gray-900">
          {confidence != null ? `${confidence}%` : '—'}
        </div>

        <div className="mt-2 text-gray-500">Reason</div>
        <div className="text-gray-700 leading-relaxed">{reason}</div>
      </div>

      {/* Operator note — hidden by default */}
      {!showNote && decisionId && (
        <button
          type="button"
          onClick={() => setShowNote(true)}
          className="text-xs text-gray-400 hover:text-gray-600 mt-3"
          data-testid="add-note-toggle"
        >
          Add note
        </button>
      )}
      {showNote && decisionId && (
        <div
          className="mt-3 flex gap-2"
          data-testid="operator-note"
        >
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Why approve or reject?"
            className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md text-gray-700 placeholder-gray-400 focus:outline-none focus:border-gray-400"
            data-testid="operator-note-input"
          />
          <button
            type="button"
            onClick={saveNote}
            className="px-3 py-1.5 text-sm rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50"
            data-testid="save-note-btn"
          >
            {noteSaved ? 'Saved' : 'Save'}
          </button>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4">
        {isPending && decisionId && (
          <>
            <button
              type="button"
              onClick={doExecute}
              disabled={loading}
              className="px-3 py-1.5 text-sm rounded-md bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 transition-colors"
              data-testid="execute-decision-btn"
            >
              {loading ? 'Working…' : 'Execute'}
            </button>
            <button
              type="button"
              onClick={doReject}
              disabled={loading}
              className="px-3 py-1.5 text-sm rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
              data-testid="reject-decision-btn"
            >
              Reject
            </button>
          </>
        )}
        <button
          type="button"
          onClick={onOpenTimeline}
          className="text-xs text-gray-500 hover:text-gray-700 ml-auto"
          data-testid="open-timeline-btn"
        >
          View analysis
        </button>
      </div>
    </div>
  );
}

// ── Main Workspace ───────────────────────────────────────────
export default function DecisionsWorkspace() {
  const [traces, setTraces] = useState([]);
  const [stats, setStats] = useState(null);
  const [daemon, setDaemon] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedTrace, setSelectedTrace] = useState(null);

  // Polling unchanged: every 5s, three GETs in parallel.
  const fetchData = useCallback(async () => {
    try {
      const [tRes, sRes, dRes] = await Promise.all([
        // All TA calls go through ta-integration layer — no direct taService.
        taAdapter.getLatestTrace(),
        taAdapter.getDecisionStats(),
        taAdapter.getDaemonStatus(),
      ]);
      setTraces(tRes.traces || []);
      setStats(sRes);
      setDaemon(dRes);
    } catch (err) {
      console.error('[Decisions] fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 5000);
    return () => clearInterval(iv);
  }, [fetchData]);

  // Lifecycle — all writes go through decisionBridge (ta-integration).
  const handleApprove = async (id) => {
    await decisionBridge.approve(id);
    fetchData();
  };

  const handleReject = async (id) => {
    await decisionBridge.reject(id, 'OPERATOR_REJECTED');
    fetchData();
  };

  // Advanced mode: full DecisionTimeline screen, untouched component.
  if (selectedTrace) {
    return (
      <DecisionTimeline
        trace={selectedTrace}
        onBack={() => setSelectedTrace(null)}
      />
    );
  }

  const isRunning = !!daemon?.is_running;

  return (
    <div
      className="h-full bg-white overflow-y-auto"
      data-testid="decisions-workspace"
    >
      <div className="p-6">
        {/* System status — one product-tone line (no operator controls) */}
        <div className="mb-4 text-sm text-gray-500">
          System is{' '}
          <span className="text-gray-700 font-medium">
            {isRunning ? 'actively scanning the market' : 'paused'}
          </span>
        </div>

        {/* Compact summary — 4 metrics, no Pass Rate, no boxes */}
        {stats && (
          <div
            className="flex items-center gap-6 mb-6 text-sm"
            data-testid="decisions-stats"
          >
            <div>
              <div className="text-gray-500">Decisions</div>
              <div className="font-semibold text-gray-900 tabular-nums">
                {stats.total_traces ?? 0}
              </div>
            </div>
            <div>
              <div className="text-gray-500">Executed</div>
              <div className="font-semibold text-emerald-600 tabular-nums">
                {stats.executed ?? 0}
              </div>
            </div>
            <div>
              <div className="text-gray-500">Pending</div>
              <div className="font-semibold text-yellow-600 tabular-nums">
                {stats.pending ?? 0}
              </div>
            </div>
            <div>
              <div className="text-gray-500">Rejected</div>
              <div className="font-semibold text-red-600 tabular-nums">
                {stats.rejected ?? 0}
              </div>
            </div>
          </div>
        )}

        {/* List */}
        {loading ? (
          <div className="text-center py-12 text-sm text-gray-400">
            Loading decisions…
          </div>
        ) : traces.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <div className="text-gray-700 font-medium">No decisions yet</div>
            <div className="text-sm mt-1">
              The system has not detected any valid setups.
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {traces.map((t) => (
              <DecisionCard
                key={t.trace_id}
                trace={t}
                onApprove={handleApprove}
                onReject={handleReject}
                onOpenTimeline={() => setSelectedTrace(t)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
