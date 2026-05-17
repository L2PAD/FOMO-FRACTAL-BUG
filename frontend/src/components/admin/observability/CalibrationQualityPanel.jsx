/**
 * Calibration Quality panel — PHASE 2 / I1 / R6
 * Source: GET /api/ta-prediction-intelligence/live (calibration_context block).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '../../ui/card';
import { fetchLive } from '../../../services/taPredictionApi';
import {
  ReadOnlyHeader,
  PanelStateBlock,
  EpistemicBanner,
  StateBadge,
} from './primitives';

const LOW_SAMPLE_THRESHOLD = 30;

const QUALITY_LABEL = {
  good:     { state: 'healthy',     pretty: 'good' },
  moderate: { state: 'degraded',    pretty: 'moderate' },
  poor:     { state: 'degraded',    pretty: 'poor' },
  unknown:  { state: 'unavailable', pretty: 'unknown' },
};
const STABILITY_LABEL = {
  high:    { state: 'healthy',     pretty: 'high' },
  mid:     { state: 'degraded',    pretty: 'mid' },
  low:     { state: 'degraded',    pretty: 'low' },
  unknown: { state: 'unavailable', pretty: 'unknown' },
};

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wide text-gray-500">{label}</span>
      <span>{children}</span>
    </div>
  );
}

export default function CalibrationQualityPanel({ symbol = 'BTCUSDT', tf = '1d' }) {
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

  const ctx = data?.calibration_context || null;

  let state;
  if (loading && !data) state = 'loading';
  else if (error) state = 'error';
  else if (!ctx || !ctx.available) state = 'unavailable';
  else if (ctx.sample_size < LOW_SAMPLE_THRESHOLD) state = 'empty_sample';
  else if (
    QUALITY_LABEL[ctx.quality]?.state !== 'healthy' ||
    STABILITY_LABEL[ctx.calibration_stability]?.state !== 'healthy'
  ) state = 'degraded';
  else state = 'healthy';

  const lowSample = ctx ? ctx.sample_size < LOW_SAMPLE_THRESHOLD : false;
  const qLabel = ctx ? QUALITY_LABEL[ctx.quality] || QUALITY_LABEL.unknown : null;
  const sLabel = ctx ? STABILITY_LABEL[ctx.calibration_stability] || STABILITY_LABEL.unknown : null;

  return (
    <div className="p-6 space-y-4" data-testid="observability-calibration">
      <ReadOnlyHeader
        title="Calibration Quality"
        subtitle="Probability-calibration model state · epistemic_only"
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
                state === 'unavailable' ? 'Calibration model not available for this scope.'
                  : state === 'error' ? (error instanceof Error ? error.message : 'Network or backend error.')
                  : undefined
              }
            />
          ) : (
            <>
              {lowSample && (
                <EpistemicBanner severity="warning" title="Insufficient calibration sample">
                  Only {ctx.sample_size} samples available—less than {LOW_SAMPLE_THRESHOLD}. Quality and stability metrics are not statistically meaningful at this size.
                </EpistemicBanner>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
                <Field label="Available"><StateBadge state="healthy" override="available" /></Field>
                <Field label="Quality"><StateBadge state={qLabel.state} override={qLabel.pretty} /></Field>
                <Field label="Stability"><StateBadge state={sLabel.state} override={sLabel.pretty} /></Field>
                <Field label="Sample size">
                  <span className={`tabular-nums ${lowSample ? 'text-amber-700 font-semibold' : 'text-gray-900'}`}>
                    {ctx.sample_size}
                  </span>
                </Field>
                <Field label="Best Brier (bucket)">
                  <span className="text-gray-900 tabular-nums">
                    {ctx.best_brier_bucket !== null && ctx.best_brier_bucket !== undefined ? ctx.best_brier_bucket.toFixed(6) : '—'}
                  </span>
                </Field>
                <Field label="Freeze label"><span className="text-gray-900 break-words">{ctx.freeze_label}</span></Field>
                {ctx.debug?.groups_with_data !== undefined && (
                  <Field label="Groups with data"><span className="text-gray-900 tabular-nums">{ctx.debug.groups_with_data}</span></Field>
                )}
                {ctx.debug?.buckets_total !== undefined && (
                  <Field label="Buckets total"><span className="text-gray-900 tabular-nums">{ctx.debug.buckets_total}</span></Field>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
