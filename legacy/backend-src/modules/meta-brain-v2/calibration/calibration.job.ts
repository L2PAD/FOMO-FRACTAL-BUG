/**
 * META BRAIN V2 — CONFIDENCE CALIBRATION JOB
 * =============================================
 *
 * Builds calibration buckets from evaluated meta_brain_runs.
 *
 * For each (moduleId, asset, horizonDays):
 *   1. Load all evaluated runs
 *   2. For each signal, bin by confidence into [0.0-0.1, ..., 0.9-1.0]
 *   3. Count hits (signal.direction == run.actualDirection)
 *   4. Save bins to meta_brain_confidence_calibration
 *
 * Run: 1x/day or manually via POST /calibration/eval
 */

import { getMongoDb } from '../../../db/mongoose.js';
import { saveCalibration, ConfidenceCalibrationBin } from './calibration.repo.js';
import { getProviderKeys } from '../registry/providers.registry.js';

const RUNS_COLLECTION = 'meta_brain_runs';

/** Fixed 10 bins */
const BINS = Array.from({ length: 10 }, (_, i) => ({
  lo: i / 10,
  hi: (i + 1) / 10,
}));

export interface CalibrationJobResult {
  evaluated: string[];
  skipped: string[];
  totalRunsProcessed: number;
}

export async function runCalibrationJob(
  asset: string,
  horizonDays: number
): Promise<CalibrationJobResult> {
  const db = getMongoDb();
  if (!db) return { evaluated: [], skipped: [], totalRunsProcessed: 0 };

  const providerKeys = getProviderKeys();
  const nowTs = Date.now();

  // Load all evaluated runs for this asset+horizon
  const runs = await db.collection(RUNS_COLLECTION)
    .find(
      {
        asset,
        horizonDays,
        evaluatedAt: { $exists: true },
        actualDirection: { $exists: true },
      },
      { projection: { _id: 0, signals: 1, actualDirection: 1 } }
    )
    .toArray();

  const evaluated: string[] = [];
  const skipped: string[] = [];

  for (const moduleId of providerKeys) {
    // Collect all signals for this module across runs
    const binData: Array<{ lo: number; hi: number; hits: number; samples: number }> =
      BINS.map(b => ({ ...b, hits: 0, samples: 0 }));

    let totalSamples = 0;

    for (const run of runs) {
      const sig = (run.signals as any[])?.find((s: any) => s.moduleId === moduleId);
      if (!sig || sig.confidence === undefined) continue;

      const conf = sig.confidence;
      const binIdx = Math.min(9, Math.floor(conf * 10));
      binData[binIdx].samples++;
      totalSamples++;

      // Hit = signal direction matches actual
      if (sig.direction === run.actualDirection) {
        binData[binIdx].hits++;
      }
    }

    if (totalSamples === 0) {
      skipped.push(`${moduleId}: no evaluated signals`);
      continue;
    }

    // Build calibration bins
    const bins: ConfidenceCalibrationBin[] = binData.map(b => ({
      lo: b.lo,
      hi: b.hi,
      samples: b.samples,
      hits: b.hits,
      hitRate: b.samples > 0 ? b.hits / b.samples : 0,
      updatedAt: nowTs,
    }));

    await saveCalibration({
      moduleId,
      asset,
      horizonDays,
      bins,
      totalSamples,
      method: 'bucket_hit_rate_v1',
      updatedAt: nowTs,
    });

    evaluated.push(moduleId);
  }

  return { evaluated, skipped, totalRunsProcessed: runs.length };
}
