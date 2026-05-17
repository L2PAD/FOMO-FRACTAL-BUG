/**
 * Gate Analytics panel — PHASE 2 / I1 / R10
 * Source: /api/ta-prediction-intelligence/shadow-gate-analytics/report
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '../../ui/card';
import { fetchShadowGateAnalyticsReport } from '../../../services/taPredictionApi';
import {
  ReadOnlyHeader,
  PanelStateBlock,
  EpistemicBanner,
  StateBadge,
  fmtPct,
  fmtTime,
  humanize,
} from './primitives';

const VERDICT_STATE = {
  GATE_QUALITY_GOOD: 'healthy',
  GATE_QUALITY_MODERATE: 'degraded',
  GATE_QUALITY_POOR: 'degraded',
  INSUFFICIENT_SAMPLE: 'empty_sample',
  UNKNOWN: 'unavailable',
};
const VERDICT_LABEL = {
  GATE_QUALITY_GOOD: 'good',
  GATE_QUALITY_MODERATE: 'moderate',
  GATE_QUALITY_POOR: 'poor',
  INSUFFICIENT_SAMPLE: 'insufficient sample',
  UNKNOWN: 'unknown',
};

function Pair({ k, v }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-gray-500">{k}</span>
      <span className="text-gray-900 text-right tabular-nums">{v}</span>
    </div>
  );
}

function WindowCard({ w }) {
  const verdictState = VERDICT_STATE[w.verdict] || 'unavailable';
  const dominantReason =
    w.reason_histogram && Object.keys(w.reason_histogram).length > 0
      ? Object.entries(w.reason_histogram).sort((a, b) => b[1] - a[1])[0]
      : null;
  return (
    <div className="rounded-md border border-gray-200 bg-white p-3 space-y-2" data-testid={`gate-analytics-window-${w.window}`}>
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-gray-900">{w.window}</div>
        <StateBadge state={verdictState} override={VERDICT_LABEL[w.verdict] || w.verdict} />
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <Pair k="total" v={String(w.total)} />
        <Pair k="with outcome" v={String(w.total_with_outcome)} />
        <Pair k="allowed" v={String(w.allowed_total)} />
        <Pair k="blocked" v={String(w.blocked_total)} />
        <Pair k="coverage" v={fmtPct(w.outcome_coverage)} />
        <Pair k="allowed correct" v={fmtPct(w.allowed_correct_rate)} />
        <Pair k="blocked correct" v={fmtPct(w.blocked_correct_rate)} />
        <Pair k="blocked bad" v={fmtPct(w.blocked_bad_rate)} />
      </div>
      <div className="pt-1 border-t border-gray-100 text-[11px] text-gray-600">
        Dominant reason: <span className="text-gray-800 font-medium" title={dominantReason ? dominantReason[0] : undefined}>
          {dominantReason ? `${humanize(dominantReason[0])} (${dominantReason[1]})` : '—'}
        </span>
      </div>
    </div>
  );
}

export default function GateAnalyticsPanel() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetchShadowGateAnalyticsReport();
      setReport(r);
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
  if (loading && !report) state = 'loading';
  else if (error) state = 'error';
  else if (!report) state = 'unavailable';
  else if (report.enriched_rows === 0) state = 'empty_sample';
  else state = 'healthy';

  return (
    <div className="p-6 space-y-4" data-testid="observability-gate-analytics">
      <ReadOnlyHeader
        title="Gate Analytics"
        subtitle="Longitudinal trends · 24h / 7d / 30d windows"
        endpoint="GET /api/ta-prediction-intelligence/shadow-gate-analytics/report"
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
              {state === 'empty_sample' && (
                <EpistemicBanner severity="info" title="No enriched outcomes yet">
                  Analytics report runs but no rows have been enriched with outcomes for any time window. Trends will populate once trades complete and outcomes are computed.
                </EpistemicBanner>
              )}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {report.windows.map(w => <WindowCard key={w.window} w={w} />)}
              </div>
              <div className="text-[11px] text-gray-500 pt-2 border-t flex flex-wrap gap-x-6 gap-y-1">
                <span>Version: <span className="text-gray-700 font-medium">{report.analytics_version}</span></span>
                <span>Freeze: <span className="text-gray-700 font-medium">{report.freeze_label}</span></span>
                <span>Adapter: <span className="text-gray-700 font-medium">{humanize(report.adapter_mode)}</span></span>
                <span>Enriched rows: <span className="text-gray-700 font-medium tabular-nums">{report.enriched_rows}</span></span>
                <span>Computed: <span className="text-gray-700 font-medium tabular-nums">{fmtTime(report.computed_at)}</span></span>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
