/**
 * META BRAIN V2 — RUNS REPOSITORY
 * =================================
 *
 * Stores every Meta Brain run for future evaluation.
 * Collection: meta_brain_runs (append-only)
 *
 * Each run captures:
 *   - aligned signals per module (score, confidence, weight, direction)
 *   - meta verdict, score, regime
 *   - timestamp for future outcome evaluation
 */

import { getMongoDb } from '../../../db/mongoose.js';

const COLLECTION = 'meta_brain_runs';

export interface RunSignalDoc {
  moduleId: string;
  direction: string;
  score: number;
  confidence: number;
  weight: number;
  normalizedScore: number;
  weightedScore: number;
  health: string;
  asOfTs: number;
}

export interface MetaBrainRunDoc {
  runId: string;
  asset: string;
  horizonDays: number;
  anchorTs: number;
  createdAt: number;

  signals: RunSignalDoc[];
  droppedModules: Array<{ module: string; reason: string }>;

  metaRawScore: number;
  metaFinalVerdict: string;
  metaConfidence: number;
  regime: string;

  weights: Record<string, number>;

  /** Set by performance evaluator when outcome is known */
  evaluatedAt?: number;
  actualReturn?: number;
  actualDirection?: string;
}

/**
 * Save a run snapshot.
 */
export async function saveRun(doc: MetaBrainRunDoc): Promise<void> {
  const db = getMongoDb();
  if (!db) return;
  await db.collection(COLLECTION).insertOne(doc);
}

/**
 * Get unevaluated runs that have matured (anchorTs + horizon has passed).
 */
export async function getUnevaluatedRuns(
  asset: string,
  horizonDays: number,
  nowTs: number,
  limit: number = 200
): Promise<MetaBrainRunDoc[]> {
  const db = getMongoDb();
  if (!db) return [];

  const maturityMs = horizonDays * 24 * 3600 * 1000;
  const cutoff = nowTs - maturityMs;

  const docs = await db.collection(COLLECTION)
    .find(
      {
        asset,
        horizonDays,
        evaluatedAt: { $exists: false },
        anchorTs: { $lte: cutoff },
      },
      { projection: { _id: 0 } }
    )
    .sort({ anchorTs: 1 })
    .limit(limit)
    .toArray();

  return docs as MetaBrainRunDoc[];
}

/**
 * Mark a run as evaluated.
 */
export async function markRunEvaluated(
  runId: string,
  actualReturn: number,
  actualDirection: string,
  evaluatedAt: number
): Promise<void> {
  const db = getMongoDb();
  if (!db) return;

  await db.collection(COLLECTION).updateOne(
    { runId },
    { $set: { evaluatedAt, actualReturn, actualDirection } }
  );
}

/**
 * Get recent runs (for drift analysis).
 */
export async function getRecentRuns(
  asset: string,
  horizonDays: number,
  limit: number = 60
): Promise<MetaBrainRunDoc[]> {
  const db = getMongoDb();
  if (!db) return [];

  const docs = await db.collection(COLLECTION)
    .find(
      { asset, horizonDays },
      { projection: { _id: 0 } }
    )
    .sort({ createdAt: -1 })
    .limit(limit)
    .toArray();

  return docs as MetaBrainRunDoc[];
}
