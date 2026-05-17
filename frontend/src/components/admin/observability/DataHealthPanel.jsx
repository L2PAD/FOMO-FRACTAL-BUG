/**
 * Data Health panel — PHASE 2 / I1 (replaces previous ReservedTab)
 * Source: /api/ta-prediction-intelligence/data-health
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '../../ui/card';
import { fetchDataHealth } from '../../../services/taPredictionApi';
import {
  ReadOnlyHeader,
  PanelStateBlock,
  EpistemicBanner,
  StateBadge,
  fmtPct,
  fmtTime,
  humanize,
} from './primitives';

export default function DataHealthPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetchDataHealth();
      setData(r);
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
  if (loading && !data) state = 'loading';
  else if (error) state = 'error';
  else if (!data) state = 'unavailable';
  else if (data.status === 'healthy') state = 'healthy';
  else state = 'degraded';

  return (
    <div className="p-6 space-y-4" data-testid="observability-data-health">
      <ReadOnlyHeader
        title="Data Health"
        subtitle="Pipeline / features / outcomes / debug / drift block scores"
        endpoint="GET /api/ta-prediction-intelligence/data-health"
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
              {data.status !== 'healthy' && (
                <EpistemicBanner
                  severity={data.status === 'broken' ? 'critical' : 'warning'}
                  title={`Data health — ${humanize(data.status)}`}
                >
                  Trust score: <span className="font-medium tabular-nums">{fmtPct(data.trust_score)}</span>. Recommendation: <span className="font-medium">{humanize(data.recommendation)}</span>.
                </EpistemicBanner>
              )}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {Object.entries(data.block_scores || {}).map(([blk, score]) => {
                  const sState = score >= 0.85 ? 'healthy' : score >= 0.5 ? 'degraded' : 'error';
                  return (
                    <div key={blk} className="rounded-md border border-gray-200 bg-gray-50 p-3 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs uppercase tracking-wide text-gray-600">{humanize(blk)}</span>
                        <StateBadge state={sState} override={fmtPct(score)} />
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all ${score >= 0.85 ? 'bg-emerald-500' : score >= 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                          style={{ width: `${Math.min(100, score * 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
              {data.issues && data.issues.length > 0 && (
                <div>
                  <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-2">Issues ({data.issues.length})</div>
                  <ul className="space-y-1.5">
                    {data.issues.map((iss, i) => (
                      <li key={i} className="text-sm rounded border border-gray-200 bg-white p-2">
                        <div className="flex items-start gap-2">
                          <StateBadge
                            state={iss.severity === 'critical' ? 'error' : iss.severity === 'warning' ? 'degraded' : 'unavailable'}
                            override={humanize(iss.severity)}
                          />
                          <div className="min-w-0">
                            <div className="text-xs text-gray-500" title={iss.code}>{humanize(iss.code)}</div>
                            <div className="text-sm text-gray-900 mt-0.5">{iss.message}</div>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="text-[11px] text-gray-500 pt-2 border-t flex flex-wrap gap-x-6 gap-y-1">
                <span>Version: <span className="text-gray-700 font-medium">{data.data_health_version}</span></span>
                <span>Builder: <span className="text-gray-700 font-medium">{data.builder_version}</span></span>
                <span>Computed: <span className="text-gray-700 font-medium tabular-nums">{fmtTime(data.computed_at)}</span></span>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
