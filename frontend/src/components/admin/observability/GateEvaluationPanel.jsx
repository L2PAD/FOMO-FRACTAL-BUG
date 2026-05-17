/**
 * Gate Evaluation panel — PHASE 2 / I1 / R9
 * Source: /api/ta-prediction-intelligence/shadow-gate-eval/summary
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '../../ui/card';
import { fetchShadowGateEvalSummary } from '../../../services/taPredictionApi';
import {
  ReadOnlyHeader,
  PanelStateBlock,
  EpistemicBanner,
  fmtPct,
  humanize,
} from './primitives';

const VERDICT_META = {
  GATE_QUALITY_GOOD:     { state: 'healthy',      severity: 'info',     label: 'GOOD',                banner: 'Gate quality is good — blocked predictions reliably underperform allowed ones.' },
  GATE_QUALITY_MODERATE: { state: 'degraded',     severity: 'warning',  label: 'MODERATE',            banner: 'Gate quality is moderate. Some discrimination is present but not strong.' },
  GATE_QUALITY_POOR:     { state: 'degraded',     severity: 'critical', label: 'POOR',                banner: 'Gate quality is poor — blocked predictions perform comparably to allowed ones. Gate may not be discriminating.' },
  INSUFFICIENT_SAMPLE:   { state: 'empty_sample', severity: 'warning',  label: 'INSUFFICIENT SAMPLE', banner: 'Not enough evaluated outcomes to compute gate quality. The gate runs but its quality verdict is unknown.' },
  UNKNOWN:               { state: 'unavailable',  severity: 'warning',  label: 'UNKNOWN',             banner: 'Backend returned no verdict.' },
};

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-2xl font-semibold text-gray-900">{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1 tabular-nums">{sub}</div>}
    </div>
  );
}

export default function GateEvaluationPanel() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetchShadowGateEvalSummary();
      setSummary(r.summary);
    } catch (e) {
      setError(e);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    let mounted = true;
    refetch();
    return () => { mounted = false; };
  }, [refetch]);

  let state;
  if (loading && !summary) state = 'loading';
  else if (error) state = 'error';
  else if (!summary) state = 'unavailable';
  else state = (VERDICT_META[summary.verdict]?.state) || 'unavailable';

  const meta = summary ? VERDICT_META[summary.verdict] : null;

  return (
    <div className="p-6 space-y-4" data-testid="observability-gate-evaluation">
      <ReadOnlyHeader
        title="Gate Evaluation"
        subtitle="Gate quality verdict · outcome coverage · allowed/blocked correctness"
        endpoint="GET /api/ta-prediction-intelligence/shadow-gate-eval/summary"
        state={state}
        onRefresh={() => refetch()}
        loading={loading}
      />
      <Card>
        <CardContent className="p-4 space-y-4">
          {state === 'loading' || state === 'error' || state === 'unavailable' ? (
            <PanelStateBlock
              state={state}
              message={state === 'error' ? (error instanceof Error ? error.message : 'Network or backend error.') : undefined}
            />
          ) : (
            <>
              {meta && (
                <EpistemicBanner severity={meta.severity} title={`Gate quality — ${meta.label}`}>
                  {meta.banner}
                </EpistemicBanner>
              )}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Stat label="Total" value={String(summary.total)} />
                <Stat label="With outcome" value={String(summary.total_with_outcome)} sub={`coverage: ${fmtPct(summary.outcome_coverage)}`} />
                <Stat label="Allowed" value={String(summary.allowed_total)} sub={`correct: ${fmtPct(summary.allowed_correct_rate)}`} />
                <Stat label="Blocked" value={String(summary.blocked_total)} sub={`bad rate: ${fmtPct(summary.blocked_bad_rate)}`} />
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-2">Block reasons by frequency</div>
                {Object.keys(summary.reason_histogram || {}).length === 0 ? (
                  <div className="text-xs text-gray-500">No block reasons recorded in evaluated set.</div>
                ) : (
                  <div className="space-y-1.5">
                    {Object.entries(summary.reason_histogram).sort((a, b) => b[1] - a[1]).map(([reason, count]) => {
                      const pct = summary.total > 0 ? count / summary.total : 0;
                      return (
                        <div key={reason} className="flex items-center gap-3 text-sm">
                          <span className="text-gray-700 w-56 truncate text-xs" title={reason}>{humanize(reason)}</span>
                          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div className="h-full bg-amber-500 transition-all" style={{ width: `${Math.min(100, pct * 100)}%` }} />
                          </div>
                          <span className="w-20 text-right text-xs text-gray-700 tabular-nums">{count} · {fmtPct(pct)}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="text-[11px] text-gray-500 pt-2 border-t flex flex-wrap gap-x-6 gap-y-1">
                <span>Version: <span className="text-gray-700 font-medium">{summary.shadow_gate_eval_version}</span></span>
                <span>Verdict: <span className="text-gray-700 font-medium">{humanize(summary.verdict)}</span></span>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
