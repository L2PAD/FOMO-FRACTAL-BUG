/**
 * META BRAIN V2 — PERFORMANCE SERVICE
 * =====================================
 *
 * Provides accuracy multiplier for weight engine.
 *
 * Formula (Laplace smoothing):
 *   smoothedHitRate = (hits + 1) / (samples + 2)
 *   accuracyMult = clamp(0.75, 1.25, 0.5 + smoothedHitRate)
 *
 * Guard: samples < 20 → accuracyMult = 1.0 (no adjustment)
 */

import { getModulePerformance, getAllPerformances, ModulePerformanceDoc } from './performance.repo.js';

const MIN_SAMPLES = 20;

export interface AccuracyInfo {
  moduleId: string;
  samples: number;
  hitRate: number;
  smoothedHitRate: number;
  accuracyMult: number;
  hasEnoughData: boolean;
}

/**
 * Get accuracy multiplier for a single module.
 */
export async function getAccuracyMult(
  moduleId: string,
  asset: string,
  horizonDays: number
): Promise<AccuracyInfo> {
  const perf = await getModulePerformance(moduleId, asset, horizonDays);

  if (!perf || perf.samples < MIN_SAMPLES) {
    return {
      moduleId,
      samples: perf?.samples ?? 0,
      hitRate: perf?.hitRate ?? 0,
      smoothedHitRate: 0.5,
      accuracyMult: 1.0,
      hasEnoughData: false,
    };
  }

  const smoothedHitRate = (perf.hits + 1) / (perf.samples + 2);
  const accuracyMult = Math.max(0.75, Math.min(1.25, 0.5 + smoothedHitRate));

  return {
    moduleId,
    samples: perf.samples,
    hitRate: perf.hitRate,
    smoothedHitRate,
    accuracyMult,
    hasEnoughData: true,
  };
}

/**
 * Get accuracy multipliers for all modules at once.
 */
export async function getAllAccuracyMults(
  asset: string,
  horizonDays: number
): Promise<Record<string, AccuracyInfo>> {
  const perfs = await getAllPerformances(asset, horizonDays);
  const result: Record<string, AccuracyInfo> = {};

  for (const perf of perfs) {
    if (perf.samples < MIN_SAMPLES) {
      result[perf.moduleId] = {
        moduleId: perf.moduleId,
        samples: perf.samples,
        hitRate: perf.hitRate,
        smoothedHitRate: 0.5,
        accuracyMult: 1.0,
        hasEnoughData: false,
      };
    } else {
      const smoothedHitRate = (perf.hits + 1) / (perf.samples + 2);
      const accuracyMult = Math.max(0.75, Math.min(1.25, 0.5 + smoothedHitRate));
      result[perf.moduleId] = {
        moduleId: perf.moduleId,
        samples: perf.samples,
        hitRate: perf.hitRate,
        smoothedHitRate,
        accuracyMult,
        hasEnoughData: true,
      };
    }
  }

  return result;
}

/**
 * Get performance summary for API response.
 */
export async function getPerformanceSummary(
  asset: string,
  horizonDays: number
): Promise<Array<AccuracyInfo & { avgAbsErrorPct: number }>> {
  const perfs = await getAllPerformances(asset, horizonDays);
  return perfs.map(perf => {
    const smoothedHitRate = perf.samples >= MIN_SAMPLES
      ? (perf.hits + 1) / (perf.samples + 2)
      : 0.5;
    const accuracyMult = perf.samples >= MIN_SAMPLES
      ? Math.max(0.75, Math.min(1.25, 0.5 + smoothedHitRate))
      : 1.0;

    return {
      moduleId: perf.moduleId,
      samples: perf.samples,
      hitRate: perf.hitRate,
      smoothedHitRate,
      accuracyMult,
      hasEnoughData: perf.samples >= MIN_SAMPLES,
      avgAbsErrorPct: perf.avgAbsErrorPct,
    };
  });
}
