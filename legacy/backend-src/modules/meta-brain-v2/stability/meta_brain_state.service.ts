/**
 * META BRAIN V2 — STATE SERVICE
 * ==============================
 * 
 * Persists the last verdict to MongoDB for the Stability Layer.
 * Collection: meta_brain_state
 * 
 * Schema:
 *   asset          — "BTC" etc.
 *   horizon        — horizon days (1, 7, 30)
 *   lastVerdict    — "LONG" | "SHORT" | "NEUTRAL"
 *   lastScore      — final score after stability
 *   lastRawScore   — raw score before stability
 *   lastUpdatedTs  — epoch ms of last update
 *   cooldownUntilTs — epoch ms until verdict is locked
 */

import { getMongoDb } from '../../../db/mongoose.js';

const COLLECTION = 'meta_brain_state';

export interface MetaBrainState {
  asset: string;
  horizon: number;
  lastVerdict: string;
  lastScore: number;
  lastRawScore: number;
  lastUpdatedTs: number;
  cooldownUntilTs: number;
}

/**
 * Get last state for asset + horizon. Returns null if no prior state.
 */
export async function getState(asset: string, horizon: number): Promise<MetaBrainState | null> {
  const db = getMongoDb();
  if (!db) return null;

  const doc = await db.collection(COLLECTION).findOne(
    { asset: asset.toUpperCase(), horizon },
    { projection: { _id: 0 } }
  );

  return doc as MetaBrainState | null;
}

/**
 * Upsert state for asset + horizon.
 */
export async function saveState(state: MetaBrainState): Promise<void> {
  const db = getMongoDb();
  if (!db) return;

  await db.collection(COLLECTION).updateOne(
    { asset: state.asset, horizon: state.horizon },
    { $set: state },
    { upsert: true }
  );
}
