/**
 * FRACTAL SNAPSHOT BUILDER
 * ========================
 * 
 * Transforms raw fractal_state into decision-ready snapshots
 * for Meta Brain V2 consumption.
 * 
 * INPUT:  fractal_state (raw fractal analysis, patterns, scenarios)
 * OUTPUT: fractal_prediction_snapshots (standardized decision format)
 * 
 * Meta Brain reads ONLY from snapshots, never from raw state.
 */

import mongoose from 'mongoose';

interface FractalSnapshot {
  asset: string;
  horizon: '1D' | '7D' | '30D';
  timestamp: Date;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  score: number;
  confidence: number;
  range: {
    low: number;
    high: number;
    median: number;
  };
  pattern: string;
  source: string;
  metadata: {
    sampleSize?: number;
    reliability?: number;
    entropy?: number;
  };
}

/**
 * Build Fractal snapshot from latest fractal state
 */
export async function buildFractalSnapshot(
  asset: string,
  horizon: '1D' | '7D' | '30D' = '7D'
): Promise<FractalSnapshot | null> {
  const db = mongoose.connection.db;
  if (!db) {
    console.warn('[FractalSnapshotBuilder] MongoDB not connected');
    return null;
  }

  // Map horizon to fractal focus keys
  const focusMap: Record<string, string> = {
    '1D': '1d',
    '7D': '7d',
    '30D': '30d',
  };
  const timeframe = focusMap[horizon];

  // Fetch latest fractal state for this asset
  // fractal_state uses composite key: "BTC:1d", "BTC:7d", etc
  const stateId = `${asset}:${timeframe}`;
  
  const state = await db
    .collection('fractal_state')
    .findOne({ _id: stateId });

  if (!state) {
    console.warn(`[FractalSnapshotBuilder] No fractal state for ${asset} ${horizon}`);
    return null;
  }

  // Extract forecast data
  const scenario = state.scenario || {};
  const diagnostics = state.diagnostics || {};
  const meta = state.meta || {};

  // Returns (p25, p50, p75)
  const returns = scenario.returns || {};
  const p50 = returns.p50 ?? 0; // median expected return
  const p25 = returns.p25 ?? p50 - 0.05;
  const p75 = returns.p75 ?? p50 + 0.05;

  // Probabilities
  const probUp = scenario.probUp ?? 0.5;
  const probDown = scenario.probDown ?? 0.5;

  // Determine direction
  let direction: 'LONG' | 'SHORT' | 'NEUTRAL' = 'NEUTRAL';
  let score = 0;

  if (probUp > 0.55 && p50 > 0.02) {
    direction = 'LONG';
    score = Math.min(1, p50 * 10); // scale to [0..1]
  } else if (probDown > 0.55 && p50 < -0.02) {
    direction = 'SHORT';
    score = Math.max(-1, p50 * 10); // scale to [-1..0]
  }

  // Confidence from reliability score
  const reliability = diagnostics.reliability ?? 0.5;
  const confidence = Math.min(0.90, Math.max(0, reliability));

  // Pattern detection
  const pattern = state.patternType || diagnostics.regime || 'unknown';

  const snapshot: FractalSnapshot = {
    asset,
    horizon,
    timestamp: new Date(),
    direction,
    score,
    confidence,
    range: {
      low: p25,
      median: p50,
      high: p75,
    },
    pattern,
    source: 'fractal_v2',
    metadata: {
      sampleSize: scenario.sampleSize,
      reliability: diagnostics.reliability,
      entropy: diagnostics.entropy,
    },
  };

  // Save to snapshots collection
  await db.collection('fractal_prediction_snapshots').insertOne(snapshot);

  console.log(`[FractalSnapshotBuilder] ✅ ${asset} ${horizon}: ${direction} (score=${score.toFixed(3)}, conf=${confidence.toFixed(2)}, pattern=${pattern})`);

  return snapshot;
}

/**
 * Build snapshots for all horizons for a given asset
 */
export async function buildAllFractalSnapshots(asset: string): Promise<void> {
  const horizons: Array<'1D' | '7D' | '30D'> = ['1D', '7D', '30D'];
  
  for (const horizon of horizons) {
    try {
      await buildFractalSnapshot(asset, horizon);
    } catch (err: any) {
      console.error(`[FractalSnapshotBuilder] Error for ${asset} ${horizon}:`, err.message);
    }
  }
}

export default buildFractalSnapshot;
