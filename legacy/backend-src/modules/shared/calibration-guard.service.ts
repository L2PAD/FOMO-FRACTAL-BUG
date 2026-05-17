/**
 * Calibration Guard Service
 * ===========================
 * 
 * F4: Monitors confidence calibration using Beta-Binomial posterior.
 * 
 * Key concepts:
 * - Buckets: confidence ranges [0.50-0.60), [0.60-0.70), etc.
 * - Prior: Beta(2,2) - uninformative, handles small samples
 * - ECE: Expected Calibration Error (weighted average of bucket errors)
 * 
 * Status levels:
 * - OK: ECE < 5%
 * - WARN: ECE 5-10%
 * - DEGRADED: ECE 10-15%
 * - CRITICAL: ECE > 15%
 * - UNKNOWN: insufficient samples (<80)
 */

import {
  CalibrationBucketModel,
  CalibrationSnapshotModel,
  CalibrationBucketDoc,
} from './calibration.model.js';
import { getEvidenceWriterService } from './evidence-writer.service.js';

export type CalibrationStatus = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL' | 'UNKNOWN';

export interface CalibrationDecision {
  confidence: number;
  correct: boolean;
  channel?: string;
}

export interface CalibrationResult {
  status: CalibrationStatus;
  ece: number;
  total: number;
  buckets: Array<{
    range: string;
    n: number;
    wins: number;
    posteriorMean: number;
    midpoint: number;
    error: number;
  }>;
  confidenceMultiplier: number;
  promotionAllowed: boolean;
}

// Configuration
const BUCKET_RANGES = [
  { min: 0.50, max: 0.60 },
  { min: 0.60, max: 0.70 },
  { min: 0.70, max: 0.80 },
  { min: 0.80, max: 0.90 },
  { min: 0.90, max: 1.01 },
];

const MIN_SAMPLES = 80;
const PRIOR_ALPHA = 2;
const PRIOR_BETA = 2;

const ECE_THRESHOLDS = {
  OK: 0.05,
  WARN: 0.10,
  DEGRADED: 0.15,
};

export class CalibrationGuardService {
  private moduleKey: string;

  constructor(moduleKey: 'sentiment' | 'exchange') {
    this.moduleKey = moduleKey;
  }

  /**
   * Run calibration analysis on finalized decisions
   */
  async run(
    window: string,
    decisions: CalibrationDecision[],
    channel: string = 'RULE'
  ): Promise<CalibrationResult> {
    const evidence = getEvidenceWriterService();

    if (decisions.length < MIN_SAMPLES) {
      const result: CalibrationResult = {
        status: 'UNKNOWN',
        ece: 0,
        total: decisions.length,
        buckets: [],
        confidenceMultiplier: 0.9,
        promotionAllowed: true,
      };

      return result;
    }

    const total = decisions.length;
    const bucketStats: CalibrationResult['buckets'] = [];
    let weightedError = 0;

    // Process each bucket
    for (const range of BUCKET_RANGES) {
      const bucketDecisions = decisions.filter(
        d => d.confidence >= range.min && d.confidence < range.max
      );

      const n = bucketDecisions.length;
      if (n === 0) continue;

      const wins = bucketDecisions.filter(d => d.correct).length;
      const posteriorMean = (wins + PRIOR_ALPHA) / (n + PRIOR_ALPHA + PRIOR_BETA);
      const midpoint = (range.min + range.max) / 2;
      const error = Math.abs(posteriorMean - midpoint);

      weightedError += (n / total) * error;

      bucketStats.push({
        range: `${range.min.toFixed(2)}-${range.max.toFixed(2)}`,
        n,
        wins,
        posteriorMean,
        midpoint,
        error,
      });

      // Update bucket in DB
      await this.updateBucket(window, channel, range.min, range.max, n, wins);
    }

    const ece = weightedError;
    const status = this.eceToStatus(ece);
    const { confidenceMultiplier, promotionAllowed } = this.statusToActions(status);

    // Save snapshot
    await CalibrationSnapshotModel.create({
      moduleKey: this.moduleKey,
      window,
      total,
      ece,
      status,
      buckets: bucketStats,
    });

    // Log to evidence
    await evidence.append(
      this.moduleKey as any,
      'calibration_status_changed' as any,
      status === 'CRITICAL' ? 'CRITICAL' : status === 'DEGRADED' ? 'WARN' : 'INFO',
      `Calibration ${status}: ECE=${(ece * 100).toFixed(1)}%, n=${total}`,
      { window },
      { ece, status, total, bucketCount: bucketStats.length }
    );

    console.log(`[CalibrationGuard] ${this.moduleKey}:${window} → ${status} (ECE=${(ece*100).toFixed(1)}%, n=${total})`);

    return {
      status,
      ece,
      total,
      buckets: bucketStats,
      confidenceMultiplier,
      promotionAllowed,
    };
  }

  /**
   * Update a single bucket with incremental data
   */
  private async updateBucket(
    window: string,
    channel: string,
    bucketMin: number,
    bucketMax: number,
    n: number,
    wins: number
  ): Promise<void> {
    const losses = n - wins;
    const posteriorMean = (wins + PRIOR_ALPHA) / (n + PRIOR_ALPHA + PRIOR_BETA);
    const empiricalWinRate = n > 0 ? wins / n : 0;
    const midpoint = (bucketMin + bucketMax) / 2;
    const calibrationError = Math.abs(posteriorMean - midpoint);

    await CalibrationBucketModel.findOneAndUpdate(
      {
        moduleKey: this.moduleKey,
        channel,
        window,
        bucketMin,
        bucketMax,
      },
      {
        $set: {
          n,
          wins,
          losses,
          alpha: PRIOR_ALPHA,
          beta: PRIOR_BETA,
          posteriorMean,
          empiricalWinRate,
          calibrationError,
        },
      },
      { upsert: true }
    );
  }

  /**
   * Convert ECE to status
   */
  private eceToStatus(ece: number): CalibrationStatus {
    if (ece < ECE_THRESHOLDS.OK) return 'OK';
    if (ece < ECE_THRESHOLDS.WARN) return 'WARN';
    if (ece < ECE_THRESHOLDS.DEGRADED) return 'DEGRADED';
    return 'CRITICAL';
  }

  /**
   * Convert status to actions
   */
  private statusToActions(status: CalibrationStatus): { confidenceMultiplier: number; promotionAllowed: boolean } {
    switch (status) {
      case 'OK':
        return { confidenceMultiplier: 1.0, promotionAllowed: true };
      case 'WARN':
        return { confidenceMultiplier: 0.9, promotionAllowed: true };
      case 'DEGRADED':
        return { confidenceMultiplier: 0.75, promotionAllowed: false };
      case 'CRITICAL':
        return { confidenceMultiplier: 0.5, promotionAllowed: false };
      case 'UNKNOWN':
        return { confidenceMultiplier: 0.9, promotionAllowed: true };
    }
  }

  /**
   * Get latest calibration status (without running)
   */
  async getLatestStatus(window: string): Promise<CalibrationResult | null> {
    const snapshot = await CalibrationSnapshotModel.findOne({
      moduleKey: this.moduleKey,
      window,
    }).sort({ createdAt: -1 }).lean();

    if (!snapshot) return null;

    const { confidenceMultiplier, promotionAllowed } = this.statusToActions(snapshot.status as CalibrationStatus);

    return {
      status: snapshot.status as CalibrationStatus,
      ece: snapshot.ece,
      total: snapshot.total,
      buckets: snapshot.buckets as any,
      confidenceMultiplier,
      promotionAllowed,
    };
  }

  /**
   * Get all buckets for a window
   */
  async getBuckets(window: string, channel: string = 'RULE'): Promise<CalibrationBucketDoc[]> {
    return CalibrationBucketModel.find({
      moduleKey: this.moduleKey,
      window,
      channel,
    }).sort({ bucketMin: 1 }).lean();
  }

  /**
   * Reset buckets (only if not frozen)
   */
  async resetBuckets(window: string): Promise<number> {
    const result = await CalibrationBucketModel.deleteMany({
      moduleKey: this.moduleKey,
      window,
    });

    const evidence = getEvidenceWriterService();
    await evidence.append(
      this.moduleKey as any,
      'calibration_status_changed' as any,
      'WARN',
      `Calibration buckets RESET for ${window}`,
      { window },
      { deleted: result.deletedCount }
    );

    return result.deletedCount;
  }

  /**
   * Map status to health score for URI
   */
  statusToHealthScore(status: CalibrationStatus): number {
    switch (status) {
      case 'OK': return 1.0;
      case 'WARN': return 0.75;
      case 'DEGRADED': return 0.5;
      case 'CRITICAL': return 0.2;
      case 'UNKNOWN': return 0.7;
    }
  }
}

// Singletons
let sentimentCalibrationGuard: CalibrationGuardService | null = null;
let exchangeCalibrationGuard: CalibrationGuardService | null = null;

export function getSentimentCalibrationGuard(): CalibrationGuardService {
  if (!sentimentCalibrationGuard) {
    sentimentCalibrationGuard = new CalibrationGuardService('sentiment');
  }
  return sentimentCalibrationGuard;
}

export function getExchangeCalibrationGuard(): CalibrationGuardService {
  if (!exchangeCalibrationGuard) {
    exchangeCalibrationGuard = new CalibrationGuardService('exchange');
  }
  return exchangeCalibrationGuard;
}

console.log('[Shared] Calibration Guard Service loaded (F4)');
