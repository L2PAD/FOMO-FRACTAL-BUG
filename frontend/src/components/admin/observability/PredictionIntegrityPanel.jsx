/**
 * Prediction Integrity panel — PHASE 2 / I1 / R7
 * Source: GET /api/ta-prediction-intelligence/live (prediction_context_integrity block).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '../../ui/card';
import { fetchLive } from '../../../services/taPredictionApi';
import {
  ReadOnlyHeader,
  PanelStateBlock,
  EpistemicBanner,
  StateBadge,
  fmtPct,
  humanize,
  shortId,
} from './primitives';

function ComponentCard({ title, rows, state }) {
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 p-3 space-y-2" data-testid={`integrity-component-${title.toLowerCase().replace(/\s+/g,'-')}`}>
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-gray-900">{title}</div>
        <StateBadge state={state} />
      </div>
      <div className="text-xs space-y-0.5">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-2">
            <span className="text-gray-500">{k}</span>
            <span className="text-gray-900 break-words text-right">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PredictionIntegrityPanel({ symbol = 'BTCUSDT', tf = '1d' }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const payload = await fetchLive(symbol, tf);
      setData(payload);
    } catch (e) {
      setError(e);
    } finally { setLoading(false); }
  }, [symbol, tf]);

  useEffect(() => {
    let mounted = true;
    refetch();
    return () => { mounted = false; };
  }, [refetch]);

  const integrity = data?.prediction_context_integrity || null;

  let state;
  if (loading && !data) state = 'loading';
  else if (error) state = 'error';
  else if (!integrity) state = 'unavailable';
  else if (integrity.status === 'HEALTHY') state = 'healthy';
  else state = 'degraded';

  const isUnreliable = integrity?.status === 'UNRELIABLE';

  return (
    <div className="p-6 space-y-4" data-testid="observability-integrity">
      <ReadOnlyHeader
        title="Prediction Integrity"
        subtitle="HEALTHY / DEGRADED / UNRELIABLE — epistemic verdict on the live prediction"
        endpoint={`GET /api/ta-prediction-intelligence/live?symbol=${symbol}&tf=${tf}`}
        state={state}
        onRefresh={() => refetch()}
        loading={loading}
      />
      <Card>
        <CardContent className="p-4 space-y-4">
          {state === 'loading' || state === 'error' || state === 'unavailable' ? (
            <PanelStateBlock
              state={state}
              message={
                state === 'unavailable' ? 'Integrity verdict not available for this scope.'
                  : state === 'error' ? (error instanceof Error ? error.message : 'Network or backend error.')
                  : undefined
              }
            />
          ) : (
            <>
              {integrity.status === 'HEALTHY' && (
                <EpistemicBanner severity="info" title="Integrity — HEALTHY">
                  All upstream components (CORE7, calibration, data health) report acceptable state.
                </EpistemicBanner>
              )}
              {integrity.status === 'DEGRADED' && (
                <EpistemicBanner severity="warning" title="Integrity — DEGRADED">
                  One or more upstream components are degraded. Trade outcomes may still be tracked, but confidence and calibration are reduced.
                </EpistemicBanner>
              )}
              {isUnreliable && (
                <EpistemicBanner severity="critical" title="Integrity — UNRELIABLE">
                  Multiple upstream components fail. Predictions from this scope must NOT be used for execution. Shadow gate will block them by default.
                </EpistemicBanner>
              )}

              {integrity.reasons?.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[11px] uppercase tracking-wide text-gray-500">Причины</div>
                  <ul className="list-disc pl-5 space-y-0.5 text-sm text-gray-800">
                    {integrity.reasons.map((r, i) => (
                      <li key={i} title={r}>{humanize(r)}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-2">Component contributions</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <ComponentCard
                    title="CORE7"
                    rows={[
                      ['available', integrity.components.core7.available ? 'yes' : 'no'],
                      ['acceptance state', humanize(integrity.components.core7.acceptance_state)],
                    ]}
                    state={integrity.components.core7.available ? 'healthy' : 'unavailable'}
                  />
                  <ComponentCard
                    title="Calibration"
                    rows={[
                      ['available', integrity.components.calibration.available ? 'yes' : 'no'],
                      ['quality', humanize(integrity.components.calibration.quality)],
                      ['stability', humanize(integrity.components.calibration.stability)],
                      ['sample size', String(integrity.components.calibration.sample_size)],
                    ]}
                    state={
                      !integrity.components.calibration.available ? 'unavailable'
                        : integrity.components.calibration.sample_size < 30 ? 'empty_sample'
                        : integrity.components.calibration.quality === 'good' ? 'healthy'
                        : 'degraded'
                    }
                  />
                  <ComponentCard
                    title="Data Health"
                    rows={[
                      ['available', integrity.components.data_health.available ? 'yes' : 'no'],
                      ['status', humanize(integrity.components.data_health.status)],
                      ['trust score', fmtPct(integrity.components.data_health.trust_score)],
                    ]}
                    state={
                      !integrity.components.data_health.available ? 'unavailable'
                        : integrity.components.data_health.status === 'healthy' ? 'healthy'
                        : 'degraded'
                    }
                  />
                </div>
              </div>

              <div className="text-xs text-gray-500 pt-3 border-t flex flex-wrap gap-x-6 gap-y-1">
                <span>Decision mutated: <span className="text-gray-700 font-medium">{integrity.decision_mutated ? 'yes' : 'no'}</span></span>
                <span>Adapter mode: <span className="text-gray-700 font-medium">{humanize(integrity.adapter_mode)}</span></span>
                <span>Freeze label: <span className="text-gray-700 font-medium">{integrity.freeze_label}</span></span>
                {data?.prediction_id && (
                  <span title={data.prediction_id}>
                    Prediction ID: <span className="text-gray-700 font-medium">{shortId(data.prediction_id)}</span>
                  </span>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
