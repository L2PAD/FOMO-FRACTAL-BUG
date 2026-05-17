/**
 * META BRAIN V2 — DRIFT STATE REPOSITORY
 * ========================================
 *
 * Two collections:
 *   - meta_brain_drift_state:   latest drift score per (module, asset, horizon)
 *   - meta_brain_drift_history: daily snapshots for charting
 */

import { getMongoDb } from '../../../db/mongoose.js';

const STATE_COLLECTION = 'meta_brain_drift_state';
const HISTORY_COLLECTION = 'meta_brain_drift_history';

export interface DriftStateDoc {
  moduleId: string;
  asset: string;
  horizonDays: number;
  driftScore: number;        // composite [0..1]
  perfDrift: number;         // [0..1]
  signalDrift: number;       // [0..1]
  coverageDrift: number;     // [0..1]
  penalty: number;           // exp(-2*driftScore)
  status: 'OK' | 'WATCH' | 'DRIFT';
  explain: string[];         // top 3 reasons
  updatedAt: number;
}

export interface DriftHistoryDoc {
  moduleId: string;
  asset: string;
  horizonDays: number;
  dateBucket: string;        // YYYY-MM-DD
  driftScore: number;
  penalty: number;
  status: string;
  createdAt: number;
}

/** Get current drift state for all modules */
export async function getAllDriftStates(
  asset: string,
  horizonDays: number
): Promise<DriftStateDoc[]> {
  const db = getMongoDb();
  if (!db) return [];
  return (await db.collection(STATE_COLLECTION)
    .find({ asset, horizonDays }, { projection: { _id: 0 } })
    .toArray()) as DriftStateDoc[];
}

/** Get drift state for a single module */
export async function getDriftState(
  moduleId: string,
  asset: string,
  horizonDays: number
): Promise<DriftStateDoc | null> {
  const db = getMongoDb();
  if (!db) return null;
  return (await db.collection(STATE_COLLECTION).findOne(
    { moduleId, asset, horizonDays },
    { projection: { _id: 0 } }
  )) as DriftStateDoc | null;
}

/** Upsert drift state */
export async function saveDriftState(doc: DriftStateDoc): Promise<void> {
  const db = getMongoDb();
  if (!db) return;
  await db.collection(STATE_COLLECTION).updateOne(
    { moduleId: doc.moduleId, asset: doc.asset, horizonDays: doc.horizonDays },
    { $set: doc },
    { upsert: true }
  );
}

/** Append drift history entry */
export async function appendDriftHistory(doc: DriftHistoryDoc): Promise<void> {
  const db = getMongoDb();
  if (!db) return;
  // Upsert by (moduleId, asset, horizonDays, dateBucket) to avoid duplicates
  await db.collection(HISTORY_COLLECTION).updateOne(
    {
      moduleId: doc.moduleId,
      asset: doc.asset,
      horizonDays: doc.horizonDays,
      dateBucket: doc.dateBucket,
    },
    { $set: doc },
    { upsert: true }
  );
}

/** Get drift history for a module over N days */
export async function getDriftHistory(
  moduleId: string,
  asset: string,
  horizonDays: number,
  days: number = 30
): Promise<DriftHistoryDoc[]> {
  const db = getMongoDb();
  if (!db) return [];
  const cutoff = new Date(Date.now() - days * 24 * 3600 * 1000).toISOString().slice(0, 10);
  return (await db.collection(HISTORY_COLLECTION)
    .find(
      { moduleId, asset, horizonDays, dateBucket: { $gte: cutoff } },
      { projection: { _id: 0 } }
    )
    .sort({ dateBucket: 1 })
    .toArray()) as DriftHistoryDoc[];
}
