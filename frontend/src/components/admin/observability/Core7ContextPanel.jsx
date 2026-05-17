/**
 * CORE7 Context panel — PHASE 2 / I1 / R5
 * Read-only observability of the CORE7 axis acceptance state.
 * Source: GET /api/ta-prediction-intelligence/live (core7_context block).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '../../ui/card';
import { fetchLive } from '../../../services/taPredictionApi';
import {
  ReadOnlyHeader,
  PanelStateBlock,
  EpistemicBanner,
  StateBadge,
  humanize,
} from './primitives';

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wide text-gray-500">{label}</span>
      <span className="text-sm text-gray-900">{children}</span>
    </div>
  );
}
// Replacement for previous <Mono> — Gilroy-styled value pill, no monospace.
function Val({ children }) {
  return <span className="text-gray-900 break-words">{children}</span>;
}

export default function Core7ContextPanel({ symbol = 'BTCUSDT', tf = '1d' }) {
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
    } finally {
      setLoading(false);
    }
  }, [symbol, tf]);

  useEffect(() => {
    let mounted = true;
    refetch();
    return () => { mounted = false; };
  }, [refetch]);

  const ctx = data?.core7_context || null;

  let state;
  if (loading && !data) state = 'loading';
  else if (error) state = 'error';
  else if (!ctx) state = 'unavailable';
  else if (!ctx.available) state = 'unavailable';
  else if (ctx.acceptance_state === 'rejected' || ctx.first_failing_axis) state = 'degraded';
  else state = 'healthy';

  return (
    <div className="p-6 space-y-4" data-testid="observability-core7-context">
      <ReadOnlyHeader
        title="CORE7 Context"
        subtitle="Regime axis acceptance · epistemic_only · read-only metadata"
        endpoint={`GET /api/ta-prediction-intelligence/live?symbol=${symbol}&tf=${tf}`}
        state={state}
        onRefresh={() => refetch()}
        loading={loading}
      />
      <Card>
        <CardContent className="p-4">
          {state === 'loading' || state === 'error' || state === 'unavailable' ? (
            <PanelStateBlock
              state={state}
              message={
                state === 'unavailable'
                  ? (ctx?.reason ? `Backend reason: ${ctx.reason}` : 'CORE7 mapping not available for this symbol / timeframe.')
                  : state === 'error'
                  ? (error instanceof Error ? error.message : 'Network or backend error.')
                  : undefined
              }
            />
          ) : (
            <div className="space-y-4">
              {ctx.reason && (
                <EpistemicBanner severity={state === 'degraded' ? 'warning' : 'info'} title="Backend reason">
                  {ctx.reason}
                </EpistemicBanner>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
                <Field label="Available">
                  <StateBadge state={ctx.available ? 'healthy' : 'unavailable'} override={ctx.available ? 'available' : 'not available'} />
                </Field>
                <Field label="Symbol · Timeframe"><Val>{ctx.symbol} · {ctx.timeframe}</Val></Field>
                <Field label="Regime key"><Val>{humanize(ctx.regime_key, { fallback: '—' })}</Val></Field>
                <Field label="Acceptance state"><Val>{humanize(ctx.acceptance_state, { fallback: '—' })}</Val></Field>
                <Field label="First failing axis"><Val>{humanize(ctx.first_failing_axis, { fallback: '—' })}</Val></Field>
                <Field label="Freeze label"><Val>{ctx.freeze_label}</Val></Field>
                <Field label="Adapter mode"><Val>{humanize(ctx.adapter_mode)}</Val></Field>
                <Field label="Mutates decision"><Val>{ctx.mutates_decision ? 'yes' : 'no (epistemic only)'}</Val></Field>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
