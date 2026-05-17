/**
 * FRACTAL FORECAST PUBLISHER
 * ==========================
 * 
 * Transforms fractal_state/forecast into decision-ready prediction snapshots.
 * 
 * This is NOT an ML model.
 * This extracts forecast signals from fractal engine and standardizes them.
 * 
 * INPUT:  fractal_state (state metadata, forecast, scenario)
 * OUTPUT: fractal_prediction_snapshots (decision-ready artifacts)
 * 
 * CRITICAL: Does NOT publish bootstrap-only states without forecast signals.
 */

import mongoose from 'mongoose';

type Horizon = '24H' | '7D' | '30D';
type Direction = 'LONG' | 'SHORT' | 'NEUTRAL';

interface FractalPredictionSnapshot {
  asset: string;
  timestamp: number;
  horizon: Horizon;
  
  direction: Direction;
  score: number;              // -1..1
  confidence: number;         // 0..1
  strength: number;           // 0..1
  
  current_price: number;
  expected_return_pct: number;
  target_price: number;
  
  range_low: number;
  range_high: number;
  
  pattern_type: string;
  regime: string | null;
  
  diagnostics: {
    source_state_exists: boolean;
    scenario_exists: boolean;
    forecast_exists: boolean;
    expected_return_raw: number;
  };
  
  source: string;
  createdAt: Date;
}

function clamp(x: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, x));
}

function normalizeHorizon(raw: any): Horizon {
  const h = String(raw || '').toUpperCase();
  if (h.includes('30')) return '30D';
  if (h.includes('7')) return '7D';
  return '24H';
}

function directionFromReturn(ret: number): Direction {
  if (ret > 0.02) return 'LONG';
  if (ret < -0.02) return 'SHORT';
  return 'NEUTRAL';
}

/**
 * Publish forecast snapshot for a single asset
 * Only publishes if there is actual forecast signal (not bootstrap-only state)
 */
export async function publishFractalForecastSnapshot(
  asset: string
): Promise<{ ok: boolean; reason?: string; inserted?: number; direction?: Direction; horizon?: Horizon }> {
  const db = mongoose.connection.db;
  if (!db) {
    console.warn('[FractalPublisher] MongoDB not connected');
    return { ok: false, reason: 'db_not_connected' };
  }

  // Fetch fractal state for this asset
  // fractal_state can use different ID formats, try both
  let state = await db.collection('fractal_state').findOne({ asset });
  
  if (!state) {
    // Try composite key format (e.g., "BTC:7d")
    const possibleIds = [`${asset}:1d`, `${asset}:7d`, `${asset}:30d`];
    for (const id of possibleIds) {
      state = await db.collection('fractal_state').findOne({ _id: id });
      if (state) break;
    }
  }

  if (!state) {
    return { ok: false, reason: 'no_state' };
  }

  const forecast = state.forecast || {};
  const scenario = state.scenario || {};
  const diagnostics = state.diagnostics || {};
  const meta = state.meta || {};

  const currentPrice = Number(
    forecast.currentPrice ?? 
    scenario.currentPrice ?? 
    state.currentPrice ?? 
    meta.currentPrice ?? 
    0
  );

  if (!currentPrice || currentPrice <= 0) {
    return { ok: false, reason: 'no_price' };
  }

  // Try to resolve expected return from multiple possible sources
  const expectedReturnRaw = Number(
    forecast.expectedReturn ??
      scenario.expectedReturn ??
      state.expectedReturn ??
      (scenario.returns?.p50 ?? 0)
  );

  const horizon = normalizeHorizon(
    forecast.horizon ?? scenario.horizon ?? state.horizon ?? state.timeframe ?? '7D'
  );

  // Determine direction
  let direction: Direction = 'NEUTRAL';
  
  if (scenario.direction) {
    const dir = String(scenario.direction).toUpperCase();
    if (dir === 'UP' || dir === 'LONG') direction = 'LONG';
    else if (dir === 'DOWN' || dir === 'SHORT') direction = 'SHORT';
  } else {
    direction = directionFromReturn(expectedReturnRaw);
  }

  const strength = clamp(Math.abs(expectedReturnRaw), 0, 1);

  // Confidence from return magnitude and diagnostics
  let confidence = clamp(0.25 + Math.abs(expectedReturnRaw) * 2.0, 0.2, 0.9);
  
  // Adjust confidence based on diagnostics reliability
  if (diagnostics.reliability !== undefined) {
    const reliabilityBoost = Number(diagnostics.reliability) * 0.2;
    confidence = clamp(confidence + reliabilityBoost, 0.2, 0.9);
  }

  const sign = direction === 'LONG' ? 1 : direction === 'SHORT' ? -1 : 0;
  const targetPrice = currentPrice * (1 + sign * Math.abs(expectedReturnRaw));

  // Extract range (low/high)
  const low = Number(
    forecast.low ?? 
    forecast.rangeLow ?? 
    scenario.low ?? 
    scenario.returns?.p25 ?? 
    0
  );
  
  const high = Number(
    forecast.high ?? 
    forecast.rangeHigh ?? 
    scenario.high ?? 
    scenario.returns?.p75 ?? 
    0
  );

  // Fallback range if absent
  const fallbackBandPct = Math.max(0.01, Math.abs(expectedReturnRaw) * 0.6);
  const rangeLow = low > 0 ? currentPrice * (1 + low) : targetPrice * (1 - fallbackBandPct);
  const rangeHigh = high > 0 ? currentPrice * (1 + high) : targetPrice * (1 + fallbackBandPct);

  const patternType = String(
    state.pattern ??
      state.patternType ??
      scenario.patternType ??
      meta.pattern ??
      'unknown'
  );

  const regime = state.regime ?? scenario.regime ?? diagnostics.regime ?? null;

  // CRITICAL: Do not publish bootstrap-only states
  const hasForecastSignal =
    Math.abs(expectedReturnRaw) > 0 ||
    !!scenario.direction ||
    (low !== 0 && high !== 0) ||
    !!forecast.expectedReturn;

  if (!hasForecastSignal) {
    return { ok: false, reason: 'bootstrap_only' };
  }

  const doc: FractalPredictionSnapshot = {
    asset,
    timestamp: Date.now(),
    horizon,

    direction,
    score: Number(clamp(expectedReturnRaw * 4, -1, 1).toFixed(4)),
    confidence: Number(confidence.toFixed(4)),
    strength: Number(strength.toFixed(4)),

    current_price: Number(currentPrice.toFixed(2)),
    expected_return_pct: Number((expectedReturnRaw * 100).toFixed(4)),
    target_price: Number(targetPrice.toFixed(2)),

    range_low: Number(rangeLow.toFixed(2)),
    range_high: Number(rangeHigh.toFixed(2)),

    pattern_type: patternType,
    regime,

    diagnostics: {
      source_state_exists: true,
      scenario_exists: !!state.scenario,
      forecast_exists: !!state.forecast,
      expected_return_raw: Number(expectedReturnRaw.toFixed(6)),
    },

    source: 'fractal_engine_v2',
    createdAt: new Date(),
  };

  await db.collection('fractal_prediction_snapshots').insertOne(doc);

  console.log(`[FractalPublisher] ✅ ${asset} ${horizon}: ${direction} (ret=${(expectedReturnRaw * 100).toFixed(2)}%, conf=${confidence.toFixed(2)}, pattern=${patternType})`);

  return {
    ok: true,
    inserted: 1,
    direction,
    horizon,
  };
}

export default publishFractalForecastSnapshot;
