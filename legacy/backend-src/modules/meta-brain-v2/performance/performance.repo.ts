/**
 * META BRAIN V2 — PERFORMANCE REPOSITORY
 * ========================================
 *
 * Stores per-module accuracy metrics.
 * Collection: meta_brain_module_performance
 *
 * One document per (moduleId, asset, horizonDays).
 * Updated incrementally by the performance evaluator.
 */

import { getMongoDb } from '../../../db/mongoose.js';

const COLLECTION = 'meta_brain_module_performance';

export interface ModulePerformanceDoc {
  moduleId: string;
  asset: string;
  horizonDays: number;
  samples: number;
  hits: number;
  hitRate: number;
  avgAbsErrorPct: number;
  updatedAt: number;
}

/**
 * Get performance for a module.
 */
export async function getModulePerformance(
  moduleId: string,
  asset: string,
  horizonDays: number
): Promise<ModulePerformanceDoc | null> {
  const db = getMongoDb();
  if (!db) return null;

  const doc = await db.collection(COLLECTION).findOne(
    { moduleId, asset, horizonDays },
    { projection: { _id: 0 } }
  );

  return doc as ModulePerformanceDoc | null;
}

/**
 * Get all module performances for an asset+horizon.
 */
export async function getAllPerformances(
  asset: string,
  horizonDays: number
): Promise<ModulePerformanceDoc[]> {
  const db = getMongoDb();
  if (!db) return [];

  const docs = await db.collection(COLLECTION)
    .find({ asset, horizonDays }, { projection: { _id: 0 } })
    .toArray();

  return docs as ModulePerformanceDoc[];
}

/**
 * Increment a module's performance counters.
 */
export async function incrementPerformance(
  moduleId: string,
  asset: string,
  horizonDays: number,
  hit: boolean,
  absErrorPct: number,
  nowTs: number
): Promise<void> {
  const db = getMongoDb();
  if (!db) return;

  // Upsert with atomic increment
  const existing = await db.collection(COLLECTION).findOne(
    { moduleId, asset, horizonDays }
  );

  if (!existing) {
    await db.collection(COLLECTION).insertOne({
      moduleId,
      asset,
      horizonDays,
      samples: 1,
      hits: hit ? 1 : 0,
      hitRate: hit ? 1.0 : 0.0,
      avgAbsErrorPct: absErrorPct,
      updatedAt: nowTs,
    });
    return;
  }

  const newSamples = existing.samples + 1;
  const newHits = existing.hits + (hit ? 1 : 0);
  const newHitRate = newHits / newSamples;
  const newAvgError = (existing.avgAbsErrorPct * existing.samples + absErrorPct) / newSamples;

  await db.collection(COLLECTION).updateOne(
    { moduleId, asset, horizonDays },
    {
      $set: {
        samples: newSamples,
        hits: newHits,
        hitRate: newHitRate,
        avgAbsErrorPct: newAvgError,
        updatedAt: nowTs,
      },
    }
  );
}
