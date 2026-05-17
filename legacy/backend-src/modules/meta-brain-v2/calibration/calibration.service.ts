/**
 * META BRAIN V2 — CONFIDENCE CALIBRATION SERVICE
 * =================================================
 *
 * Translates raw model confidence → calibrated probability.
 *
 * Buckets: [0.0-0.1, 0.1-0.2, ..., 0.9-1.0]
 * Calibrated = empirical hitRate in that bucket (with shrinkage).
 *
 * Shrinkage formula:
 *   hitRate' = (hitRate × samples + 0.5 × k) / (samples + k)
 *   k = 20 (shrinkage strength toward 0.5)
 *
 * Guards:
 *   - totalSamples < MIN_TOTAL (50) → return raw
 *   - bin.samples < MIN_BIN (10) → return raw
 */

import {
  getCalibrationDoc,
  getAllCalibrations,
  ConfidenceCalibrationDoc,
} from './calibration.repo.js';

const MIN_TOTAL_SAMPLES = 50;
const MIN_BIN_SAMPLES = 10;
const SHRINKAGE_K = 20;

export type CalibrationStatus = 'CALIBRATED' | 'INSUFFICIENT_DATA' | 'INSUFFICIENT_BIN' | 'RAW';

export interface CalibrationResult {
  confidence: number;
  confidenceRaw: number;
  status: CalibrationStatus;
  binRange?: string;
  binSamples?: number;
  binHitRate?: number;
}

/**
 * Calibrate a single confidence value.
 */
export async function calibrate(
  moduleId: string,
  asset: string,
  horizonDays: number,
  confidenceRaw: number
): Promise<CalibrationResult> {
  const doc = await getCalibrationDoc(moduleId, asset, horizonDays);

  // No calibration data at all
  if (!doc || doc.totalSamples < MIN_TOTAL_SAMPLES) {
    return {
      confidence: confidenceRaw,
      confidenceRaw,
      status: 'INSUFFICIENT_DATA',
    };
  }

  // Find matching bin
  const bin = doc.bins.find(b => confidenceRaw >= b.lo && confidenceRaw < b.hi);

  if (!bin || bin.samples < MIN_BIN_SAMPLES) {
    return {
      confidence: confidenceRaw,
      confidenceRaw,
      status: 'INSUFFICIENT_BIN',
      binRange: bin ? `${bin.lo}-${bin.hi}` : undefined,
      binSamples: bin?.samples,
    };
  }

  // Apply shrinkage toward 0.5 (prior)
  const shrunk = (bin.hitRate * bin.samples + 0.5 * SHRINKAGE_K) / (bin.samples + SHRINKAGE_K);
  const calibrated = Math.max(0, Math.min(1, shrunk));

  return {
    confidence: calibrated,
    confidenceRaw,
    status: 'CALIBRATED',
    binRange: `${bin.lo}-${bin.hi}`,
    binSamples: bin.samples,
    binHitRate: bin.hitRate,
  };
}

/**
 * Get calibration summary for all modules (for API).
 */
export async function getCalibrationSummary(
  asset: string,
  horizonDays: number
): Promise<Array<{
  moduleId: string;
  totalSamples: number;
  method: string;
  bins: Array<{ range: string; samples: number; hitRate: number }>;
  updatedAt: number;
  active: boolean;
}>> {
  const docs = await getAllCalibrations(asset, horizonDays);
  return docs.map(doc => ({
    moduleId: doc.moduleId,
    totalSamples: doc.totalSamples,
    method: doc.method,
    bins: doc.bins.map(b => ({
      range: `${b.lo}-${b.hi}`,
      samples: b.samples,
      hitRate: b.hitRate,
    })),
    updatedAt: doc.updatedAt,
    active: doc.totalSamples >= MIN_TOTAL_SAMPLES,
  }));
}
