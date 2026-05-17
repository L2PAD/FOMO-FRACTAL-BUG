/**
 * Sentiment Drift Service
 * =========================
 * 
 * BLOCK 10.1: Feature Drift Monitor using PSI.
 * 
 * Compares live feature distributions against training baseline.
 * Updates reliability state in registry.
 * 
 * Runs daily via cron job.
 */

import type { SentWindow } from './sentiment_feature_snapshot.model.js';
import { SentimentFeatureSnapshotModel } from './sentiment_feature_snapshot.model.js';
import { SentimentDriftResultModel, DriftStatus } from './sentiment_drift_result.model.js';
import { buildHistogram, computePSI, driftStatusFromScore, psiToUnit, createBinsFromValues, computeFeatureStats } from './psi.utils.js';
import { SentimentDirSampleModel } from '../dataset/sentiment-dir-sample.model.js';
import mongoose from 'mongoose';

// Default features to monitor for 24H window
const DEFAULT_FEATURES_24H = [
  'bias',
  'absBias',
  'confidence',
  'eventsCountLog',
] as const;

// Feature weights for drift score calculation
const FEATURE_WEIGHTS: Record<string, number> = {
  bias: 0.4,
  confidence: 0.3,
  signalStrength: 0.2,
  eventsCountLog: 0.1,
  absBias: 0.15,
  crowdSkew: 0.05,
  neutralRatio: 0.05,
};

export type DriftRunResult = {
  status: DriftStatus;
  driftScore: number;
  modelId: string;
  nLive: number;
  psiByFeature?: Record<string, { psi: number; weight: number; contribution: number }>;
};

export class SentimentDriftService {
  private lockKey(window: SentWindow): string {
    return `sent:drift:${window}`;
  }

  /**
   * Run drift check for a window
   */
  async runOnce(window: SentWindow, asOf: Date = new Date()): Promise<DriftRunResult> {
    const modelId = 'RULE_BASELINE'; // Default to rule baseline for now
    
    // Get baseline snapshot
    const baseline = await SentimentFeatureSnapshotModel.findOne({ 
      modelId, 
      window 
    }).lean();

    if (!baseline) {
      // No baseline - create one from current data
      console.log(`[Drift] No baseline for ${window}, creating from current data...`);
      await this.createBaselineSnapshot(window, modelId, asOf);
      
      await SentimentDriftResultModel.create({
        window,
        modelId,
        asOf,
        nLive: 0,
        status: 'WARN',
        driftScore: 0,
        psiByFeature: {},
        notes: ['BASELINE_CREATED'],
      }).catch(() => {}); // Ignore duplicate
      
      return { status: 'WARN', driftScore: 0, modelId, nLive: 0 };
    }

    const featureKeys = baseline.featureKeys?.length 
      ? baseline.featureKeys 
      : [...DEFAULT_FEATURES_24H];

    // Get live samples (last 200 finalized)
    const liveSamples = await SentimentDirSampleModel.find({
      window,
      finalizedAt: { $lte: asOf, $exists: true },
    })
      .sort({ asOf: -1 })
      .limit(200)
      .lean();

    const nLive = liveSamples.length;
    
    if (nLive < 30) {
      await SentimentDriftResultModel.create({
        window,
        modelId,
        asOf,
        nLive,
        status: 'WARN',
        driftScore: 0,
        psiByFeature: {},
        notes: ['INSUFFICIENT_LIVE_SAMPLES'],
      }).catch(() => {});
      
      return { status: 'WARN', driftScore: 0, modelId, nLive };
    }

    // Compute PSI for each feature
    const psiByFeature: Record<string, { psi: number; weight: number; contribution: number }> = {};
    let weightedSum = 0;
    let weightSum = 0;

    for (const key of featureKeys) {
      const baseStat = baseline.stats?.[key];
      if (!baseStat?.bins?.length) continue;

      // Extract values from samples
      const values: number[] = [];
      for (const s of liveSamples) {
        // Try direct field first, then features object
        let v = (s as any)[key];
        if (v === undefined && (s as any).features) {
          v = (s as any).features[key];
        }
        if (typeof v === 'number' && Number.isFinite(v)) {
          values.push(v);
        }
      }

      if (values.length < 20) {
        psiByFeature[key] = { psi: 0, weight: 0, contribution: 0 };
        continue;
      }

      // Build live histogram using baseline bin edges
      const binEdges = baseStat.bins.map(b => ({ lo: b.lo, hi: b.hi }));
      const liveBins = buildHistogram(values, binEdges);
      const psi = computePSI(baseStat.bins, liveBins);

      const w = FEATURE_WEIGHTS[key] || 0.05;
      const contrib = psiToUnit(psi) * w;
      
      psiByFeature[key] = { psi, weight: w, contribution: contrib };
      weightedSum += contrib;
      weightSum += w;
    }

    const driftScore = weightSum > 0 ? (weightedSum / weightSum) : 0;
    const status = driftStatusFromScore(driftScore);

    // Save result
    await SentimentDriftResultModel.findOneAndUpdate(
      { window, modelId, asOf: { $gte: new Date(asOf.getTime() - 3600_000) } },
      {
        $set: {
          window,
          modelId,
          asOf,
          nLive,
          status,
          driftScore,
          psiByFeature,
          notes: [],
        },
      },
      { upsert: true, new: true }
    );

    console.log(`[Drift] ${window}: status=${status}, score=${driftScore.toFixed(3)}, nLive=${nLive}`);

    return { status, driftScore, modelId, nLive, psiByFeature };
  }

  /**
   * Create baseline snapshot from current data
   */
  async createBaselineSnapshot(
    window: SentWindow,
    modelId: string,
    asOf: Date = new Date()
  ): Promise<void> {
    const samples = await SentimentDirSampleModel.find({
      window,
      finalizedAt: { $exists: true },
    })
      .sort({ asOf: -1 })
      .limit(500)
      .lean();

    if (samples.length < 50) {
      console.log(`[Drift] Not enough samples (${samples.length}) for baseline`);
      return;
    }

    const featureKeys = [...DEFAULT_FEATURES_24H];
    const stats: Record<string, any> = {};

    for (const key of featureKeys) {
      const values: number[] = [];
      for (const s of samples) {
        let v = (s as any)[key];
        if (v === undefined && (s as any).features) {
          v = (s as any).features[key];
        }
        if (typeof v === 'number' && Number.isFinite(v)) {
          values.push(v);
        }
      }

      if (values.length < 30) continue;

      const basicStats = computeFeatureStats(values);
      const bins = createBinsFromValues(values, 10);

      stats[key] = {
        mean: basicStats.mean,
        std: basicStats.std,
        min: basicStats.min,
        max: basicStats.max,
        n: basicStats.n,
        bins,
      };
    }

    await SentimentFeatureSnapshotModel.findOneAndUpdate(
      { modelId, window },
      {
        $set: {
          modelId,
          window,
          featureKeys,
          stats,
        },
      },
      { upsert: true }
    );

    console.log(`[Drift] Created baseline snapshot for ${window} with ${samples.length} samples`);
  }

  /**
   * Get latest drift result
   */
  async getLatest(window: SentWindow): Promise<any> {
    return SentimentDriftResultModel.findOne({ window })
      .sort({ asOf: -1 })
      .lean();
  }

  /**
   * Get drift history
   */
  async getHistory(window: SentWindow, days: number = 30): Promise<any[]> {
    const since = new Date(Date.now() - days * 24 * 3600_000);
    return SentimentDriftResultModel.find({
      window,
      asOf: { $gte: since },
    })
      .sort({ asOf: -1 })
      .lean();
  }
}

// Singleton
let driftServiceInstance: SentimentDriftService | null = null;

export function getSentimentDriftService(): SentimentDriftService {
  if (!driftServiceInstance) {
    driftServiceInstance = new SentimentDriftService();
  }
  return driftServiceInstance;
}

console.log('[Sentiment-ML] Drift Service loaded (BLOCK 10.1)');
