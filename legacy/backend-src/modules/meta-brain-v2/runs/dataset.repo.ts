/**
 * META BRAIN V2 — ML DATASET REPOSITORY
 * ========================================
 *
 * Query layer for the ML dataset built by the Run Evaluator.
 * Provides stats, paginated runs, and accuracy breakdown.
 */

import { getMongoDb } from '../../../db/mongoose.js';

const COLLECTION = 'meta_brain_runs';

export interface DatasetStats {
  total: number;
  evaluated: number;
  unevaluated: number;
  hitRate: number;
  byHorizon: Array<{
    horizonDays: number;
    evaluated: number;
    hits: number;
    hitRate: number;
    avgReturn: number;
  }>;
  byVerdict: Array<{
    verdict: string;
    count: number;
    hits: number;
    hitRate: number;
  }>;
  lastEvaluatedAt: string | null;
}

export interface DatasetRunEntry {
  runId: string;
  asset: string;
  horizonDays: number;
  anchorTs: number;
  anchorDate: string;
  metaFinalVerdict: string;
  metaConfidence: number;
  regime: string;
  futureReturn: number;
  futureDirection: string;
  hit: boolean;
  entryPrice: number;
  exitPrice: number;
  mlEvaluatedAt: number;
}

/**
 * Get ML dataset statistics.
 */
export async function getDatasetStats(asset: string): Promise<DatasetStats> {
  const db = getMongoDb();
  if (!db) {
    return { total: 0, evaluated: 0, unevaluated: 0, hitRate: 0, byHorizon: [], byVerdict: [], lastEvaluatedAt: null };
  }

  const col = db.collection(COLLECTION);

  const [total, evaluated, hits] = await Promise.all([
    col.countDocuments({ asset }),
    col.countDocuments({ asset, futureReturn: { $exists: true } }),
    col.countDocuments({ asset, hit: true }),
  ]);

  // Per-horizon breakdown
  const horizonAgg = await col.aggregate([
    { $match: { asset, futureReturn: { $exists: true } } },
    {
      $group: {
        _id: '$horizonDays',
        evaluated: { $sum: 1 },
        hits: { $sum: { $cond: ['$hit', 1, 0] } },
        avgReturn: { $avg: '$futureReturn' },
      },
    },
    { $sort: { _id: 1 } },
  ]).toArray();

  const byHorizon = horizonAgg.map(h => ({
    horizonDays: h._id as number,
    evaluated: h.evaluated,
    hits: h.hits,
    hitRate: h.evaluated > 0 ? h.hits / h.evaluated : 0,
    avgReturn: Math.round((h.avgReturn ?? 0) * 10000) / 10000,
  }));

  // Per-verdict breakdown
  const verdictAgg = await col.aggregate([
    { $match: { asset, futureReturn: { $exists: true } } },
    {
      $group: {
        _id: '$metaFinalVerdict',
        count: { $sum: 1 },
        hits: { $sum: { $cond: ['$hit', 1, 0] } },
      },
    },
    { $sort: { _id: 1 } },
  ]).toArray();

  const byVerdict = verdictAgg.map(v => ({
    verdict: v._id as string,
    count: v.count,
    hits: v.hits,
    hitRate: v.count > 0 ? v.hits / v.count : 0,
  }));

  // Last evaluated timestamp
  const lastDoc = await col
    .find({ asset, mlEvaluatedAt: { $exists: true } }, { projection: { _id: 0, mlEvaluatedAt: 1 } })
    .sort({ mlEvaluatedAt: -1 })
    .limit(1)
    .toArray();

  const lastEvaluatedAt = lastDoc.length > 0
    ? new Date(lastDoc[0].mlEvaluatedAt).toISOString()
    : null;

  return {
    total,
    evaluated,
    unevaluated: total - evaluated,
    hitRate: evaluated > 0 ? hits / evaluated : 0,
    byHorizon,
    byVerdict,
    lastEvaluatedAt,
  };
}

/**
 * Get paginated evaluated runs for the ML dataset.
 */
export async function getDatasetRuns(
  asset: string,
  horizonDays?: number,
  limit: number = 50,
  skip: number = 0
): Promise<{ runs: DatasetRunEntry[]; total: number }> {
  const db = getMongoDb();
  if (!db) return { runs: [], total: 0 };

  const filter: any = { asset, futureReturn: { $exists: true } };
  if (horizonDays) filter.horizonDays = horizonDays;

  const col = db.collection(COLLECTION);

  const [docs, total] = await Promise.all([
    col.find(filter, { projection: { _id: 0 } })
      .sort({ mlEvaluatedAt: -1 })
      .skip(skip)
      .limit(limit)
      .toArray(),
    col.countDocuments(filter),
  ]);

  const runs: DatasetRunEntry[] = docs.map((d: any) => ({
    runId: d.runId,
    asset: d.asset,
    horizonDays: d.horizonDays,
    anchorTs: d.anchorTs,
    anchorDate: new Date(d.anchorTs).toISOString(),
    metaFinalVerdict: d.metaFinalVerdict,
    metaConfidence: d.metaConfidence,
    regime: d.regime,
    futureReturn: d.futureReturn,
    futureDirection: d.futureDirection,
    hit: d.hit,
    entryPrice: d.entryPrice,
    exitPrice: d.exitPrice,
    mlEvaluatedAt: d.mlEvaluatedAt,
  }));

  return { runs, total };
}
