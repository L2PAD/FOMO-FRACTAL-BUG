/**
 * META BRAIN V2 — CORRELATION SERVICE
 * ======================================
 *
 * Computes pairwise correlation between module signals from historical runs.
 *
 * Problem:
 *   If fractal & exchange always agree, Meta Brain double-counts the signal.
 *
 * Solution:
 *   1. Build correlation matrix from recent runs
 *   2. Apply correlationPenalty to weight engine:
 *      penalizedWeight_i = weight_i × (1 − avgCorrelation_i × penaltyK)
 *
 * Correlation method: Pearson correlation on normalizedScores.
 *
 * Storage: meta_brain_correlation collection (one doc per asset+horizon).
 */

import { getMongoDb } from '../../../db/mongoose.js';

const RUNS_COLLECTION = 'meta_brain_runs';
const CORR_COLLECTION = 'meta_brain_correlation';

export interface CorrelationPair {
  a: string;
  b: string;
  correlation: number;
  samples: number;
}

export interface CorrelationMatrix {
  pairs: CorrelationPair[];
  modules: string[];
  avgCorrelation: Record<string, number>;
  updatedAt: number;
  runsAnalyzed: number;
}

/**
 * Compute Pearson correlation between two arrays.
 */
function pearson(x: number[], y: number[]): number {
  const n = x.length;
  if (n < 5) return 0;

  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
  for (let i = 0; i < n; i++) {
    sumX += x[i];
    sumY += y[i];
    sumXY += x[i] * y[i];
    sumX2 += x[i] * x[i];
    sumY2 += y[i] * y[i];
  }

  const num = n * sumXY - sumX * sumY;
  const denX = n * sumX2 - sumX * sumX;
  const denY = n * sumY2 - sumY * sumY;

  // Guard: constant series → no correlation
  if (denX <= 0 || denY <= 0) return 0;

  const den = Math.sqrt(denX * denY);
  if (den === 0 || !isFinite(den)) return 0;

  const r = num / den;
  if (!isFinite(r)) return 0;

  return Math.max(-1, Math.min(1, r));
}

/**
 * Compute correlation matrix from historical runs.
 */
export async function computeCorrelationMatrix(
  asset: string,
  horizonDays: number,
  limit: number = 100
): Promise<CorrelationMatrix> {
  const db = getMongoDb();
  const nowTs = Date.now();

  if (!db) {
    return { pairs: [], modules: [], avgCorrelation: {}, updatedAt: nowTs, runsAnalyzed: 0 };
  }

  // Get recent runs with signals
  const runs = await db.collection(RUNS_COLLECTION)
    .find(
      { asset, horizonDays },
      { projection: { _id: 0, signals: 1 } }
    )
    .sort({ createdAt: -1 })
    .limit(limit)
    .toArray();

  if (runs.length < 10) {
    return { pairs: [], modules: [], avgCorrelation: {}, updatedAt: nowTs, runsAnalyzed: runs.length };
  }

  // Build per-module score arrays
  const moduleScores: Record<string, number[]> = {};

  for (const run of runs) {
    const signals = (run as any).signals as Array<{ moduleId: string; normalizedScore: number }>;
    if (!signals) continue;

    for (const sig of signals) {
      if (!moduleScores[sig.moduleId]) moduleScores[sig.moduleId] = [];
    }
  }

  const moduleIds = Object.keys(moduleScores);

  // Fill arrays (use 0 for missing modules in a run)
  for (const run of runs) {
    const signals = (run as any).signals as Array<{ moduleId: string; normalizedScore: number }>;
    const runMap: Record<string, number> = {};
    if (signals) {
      for (const sig of signals) {
        runMap[sig.moduleId] = sig.normalizedScore;
      }
    }
    for (const mod of moduleIds) {
      moduleScores[mod].push(runMap[mod] ?? 0);
    }
  }

  // Compute pairwise correlations
  const pairs: CorrelationPair[] = [];

  for (let i = 0; i < moduleIds.length; i++) {
    for (let j = i + 1; j < moduleIds.length; j++) {
      const a = moduleIds[i];
      const b = moduleIds[j];
      const corr = pearson(moduleScores[a], moduleScores[b]);
      pairs.push({ a, b, correlation: Math.round(corr * 1000) / 1000, samples: runs.length });
    }
  }

  // Compute average absolute correlation per module
  const avgCorrelation: Record<string, number> = {};
  for (const mod of moduleIds) {
    const related = pairs.filter(p => p.a === mod || p.b === mod);
    if (related.length === 0) {
      avgCorrelation[mod] = 0;
    } else {
      avgCorrelation[mod] = Math.round(
        (related.reduce((s, p) => s + Math.abs(p.correlation), 0) / related.length) * 1000
      ) / 1000;
    }
  }

  const matrix: CorrelationMatrix = {
    pairs,
    modules: moduleIds,
    avgCorrelation,
    updatedAt: nowTs,
    runsAnalyzed: runs.length,
  };

  // Persist to DB
  await db.collection(CORR_COLLECTION).updateOne(
    { asset, horizonDays },
    { $set: { ...matrix, asset, horizonDays } },
    { upsert: true }
  );

  return matrix;
}

/**
 * Get stored correlation matrix (or empty if not computed yet).
 */
export async function getCorrelationMatrix(
  asset: string,
  horizonDays: number
): Promise<CorrelationMatrix> {
  const db = getMongoDb();
  if (!db) {
    return { pairs: [], modules: [], avgCorrelation: {}, updatedAt: 0, runsAnalyzed: 0 };
  }

  const doc = await db.collection(CORR_COLLECTION).findOne(
    { asset, horizonDays },
    { projection: { _id: 0, asset: 0, horizonDays: 0 } }
  );

  if (!doc) {
    return { pairs: [], modules: [], avgCorrelation: {}, updatedAt: 0, runsAnalyzed: 0 };
  }

  return doc as unknown as CorrelationMatrix;
}

/**
 * Get correlation penalties for weight engine.
 * Returns a Record<moduleId, penalty multiplier>.
 * penalty = 1 - avgCorrelation × K (clamped to [0.5, 1.0])
 */
export async function getCorrelationPenalties(
  asset: string,
  horizonDays: number,
  penaltyK: number = 0.3
): Promise<Record<string, number>> {
  const matrix = await getCorrelationMatrix(asset, horizonDays);
  const penalties: Record<string, number> = {};

  for (const [mod, avgCorr] of Object.entries(matrix.avgCorrelation)) {
    const penalty = Math.max(0.5, 1 - avgCorr * penaltyK);
    penalties[mod] = Math.round(penalty * 1000) / 1000;
  }

  return penalties;
}
