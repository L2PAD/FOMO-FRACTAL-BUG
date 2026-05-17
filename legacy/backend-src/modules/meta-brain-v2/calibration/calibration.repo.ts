/**
 * META BRAIN V2 — CONFIDENCE CALIBRATION REPOSITORY
 * ===================================================
 *
 * Collection: meta_brain_confidence_calibration
 * Index: { moduleId, asset, horizonDays } UNIQUE
 *
 * Stores per-module reliability buckets:
 *   confidence bucket → empirical hitRate
 */

import { getMongoDb } from '../../../db/mongoose.js';

const COLLECTION = 'meta_brain_confidence_calibration';

export interface ConfidenceCalibrationBin {
  lo: number;
  hi: number;
  samples: number;
  hits: number;
  hitRate: number;
  updatedAt: number;
}

export interface ConfidenceCalibrationDoc {
  moduleId: string;
  asset: string;
  horizonDays: number;
  bins: ConfidenceCalibrationBin[];
  totalSamples: number;
  method: string;
  updatedAt: number;
}

/** Get calibration for a module */
export async function getCalibrationDoc(
  moduleId: string,
  asset: string,
  horizonDays: number
): Promise<ConfidenceCalibrationDoc | null> {
  const db = getMongoDb();
  if (!db) return null;
  return (await db.collection(COLLECTION).findOne(
    { moduleId, asset, horizonDays },
    { projection: { _id: 0 } }
  )) as ConfidenceCalibrationDoc | null;
}

/** Get all calibrations for an asset+horizon */
export async function getAllCalibrations(
  asset: string,
  horizonDays: number
): Promise<ConfidenceCalibrationDoc[]> {
  const db = getMongoDb();
  if (!db) return [];
  return (await db.collection(COLLECTION)
    .find({ asset, horizonDays }, { projection: { _id: 0 } })
    .toArray()) as ConfidenceCalibrationDoc[];
}

/** Upsert calibration doc */
export async function saveCalibration(doc: ConfidenceCalibrationDoc): Promise<void> {
  const db = getMongoDb();
  if (!db) return;
  await db.collection(COLLECTION).updateOne(
    { moduleId: doc.moduleId, asset: doc.asset, horizonDays: doc.horizonDays },
    { $set: doc },
    { upsert: true }
  );
}
