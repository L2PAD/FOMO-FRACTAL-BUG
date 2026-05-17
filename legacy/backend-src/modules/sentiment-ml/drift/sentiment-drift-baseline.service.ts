/**
 * Sentiment Drift Baseline Service
 * ==================================
 * 
 * BLOCK S2: Baseline versioning with URI gates.
 * 
 * Baseline is created ONLY when:
 * - URI >= 0.75 (AUTO) or >= 0.60 (MANUAL)
 * - DataHealth >= 0.80
 * - CapitalHealth >= 0.70
 * - CalibrationHealth >= 0.70
 * - Sufficient samples (>= 100)
 * 
 * This prevents "anchoring to bad regime".
 */

import { 
  SentWindow, 
  BaselineCreateReason, 
  FeatureDistribution,
  UriSnapshot,
  BASELINE_GATES,
  BASELINE_FEATURES,
} from './sentiment-drift-baseline.types.js';
import { SentimentDriftBaselineModel } from './sentiment-drift-baseline.model.js';
import { getSentimentReliabilityService } from '../reliability/sentiment-reliability.service.js';
import { SentimentDirSampleModel } from '../dataset/sentiment-dir-sample.model.js';
import { getEvidenceWriterService } from '../../shared/evidence-writer.service.js';
import { getSentimentManifestService } from '../../shared/module-manifest.service.js';
import mongoose from 'mongoose';

/**
 * Compute quantiles from sorted array
 */
function quantilesFromSorted(sorted: number[]): { p05: number; p25: number; p50: number; p75: number; p95: number } {
  const pick = (p: number): number => {
    if (sorted.length === 0) return 0;
    const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor(p * (sorted.length - 1))));
    return sorted[idx];
  };
  return {
    p05: pick(0.05),
    p25: pick(0.25),
    p50: pick(0.50),
    p75: pick(0.75),
    p95: pick(0.95),
  };
}

/**
 * Build histogram from values
 */
function buildHistogram(values: number[], binCount: number = 20): { bins: number[]; min: number; max: number; binCount: number } {
  if (values.length === 0) {
    return { bins: Array(binCount).fill(0), min: 0, max: 0, binCount };
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1e-9;

  const bins = Array(binCount).fill(0);
  for (const v of values) {
    const t = (v - min) / range;
    const idx = Math.min(binCount - 1, Math.max(0, Math.floor(t * binCount)));
    bins[idx] += 1;
  }

  // Normalize
  const n = values.length;
  for (let i = 0; i < bins.length; i++) {
    bins[i] = bins[i] / n;
  }

  return { bins, min, max, binCount };
}

export type BaselineCreateResult = 
  | { ok: true; baseline: BaselineMeta }
  | { ok: false; code: 'GATE_BLOCKED' | 'NO_DATA' | 'COOLDOWN' | 'ERROR'; message: string; details?: any };

export interface BaselineMeta {
  window: SentWindow;
  version: number;
  createdAt: string;
  sampleCount: number;
  reason: BaselineCreateReason;
  uriAtCreation: { score: number; status: string; reasons: string[] };
}

export class SentimentDriftBaselineService {
  /**
   * Get latest baseline for window
   */
  async getLatestBaseline(window: SentWindow): Promise<any | null> {
    return SentimentDriftBaselineModel.findOne({ 
      module: 'sentiment', 
      window 
    })
      .sort({ createdAt: -1 })
      .lean();
  }

  /**
   * Check AUTO gate (stricter)
   */
  private checkAutoGate(uri: UriSnapshot): { ok: boolean; reason?: string } {
    if (uri.score < BASELINE_GATES.uriMinOk) {
      return { ok: false, reason: `URI ${(uri.score * 100).toFixed(0)}% < ${BASELINE_GATES.uriMinOk * 100}%` };
    }
    if (uri.dataHealth < BASELINE_GATES.dataHealthMin) {
      return { ok: false, reason: `DataHealth ${(uri.dataHealth * 100).toFixed(0)}% < ${BASELINE_GATES.dataHealthMin * 100}%` };
    }
    if (uri.capitalHealth < BASELINE_GATES.capitalHealthMin) {
      return { ok: false, reason: `CapitalHealth ${(uri.capitalHealth * 100).toFixed(0)}% < ${BASELINE_GATES.capitalHealthMin * 100}%` };
    }
    if (uri.calibrationHealth < BASELINE_GATES.calibrationHealthMin) {
      return { ok: false, reason: `CalibrationHealth ${(uri.calibrationHealth * 100).toFixed(0)}% < ${BASELINE_GATES.calibrationHealthMin * 100}%` };
    }
    return { ok: true };
  }

  /**
   * Check MANUAL gate (looser, but still has floor)
   */
  private checkManualGate(uri: UriSnapshot): { ok: boolean; reason?: string } {
    if (uri.score < BASELINE_GATES.uriMinFloor) {
      return { ok: false, reason: `URI ${(uri.score * 100).toFixed(0)}% < floor ${BASELINE_GATES.uriMinFloor * 100}%` };
    }
    return { ok: true };
  }

  /**
   * Check cooldown (min days between baselines)
   */
  private async checkCooldown(window: SentWindow): Promise<{ ok: boolean; reason?: string }> {
    const latest = await this.getLatestBaseline(window);
    if (!latest) return { ok: true };

    const daysSince = (Date.now() - new Date(latest.createdAt).getTime()) / (24 * 3600_000);
    if (daysSince < BASELINE_GATES.cooldownDays) {
      return { 
        ok: false, 
        reason: `Cooldown: ${daysSince.toFixed(1)} days since last baseline (min ${BASELINE_GATES.cooldownDays})` 
      };
    }
    return { ok: true };
  }

  /**
   * Build feature distributions from samples
   */
  private buildFeatureDistributions(
    samples: any[],
    features: readonly string[]
  ): Record<string, FeatureDistribution> {
    const result: Record<string, FeatureDistribution> = {};

    for (const feature of features) {
      const values: number[] = [];
      
      for (const s of samples) {
        // Try direct field first, then features object
        let v = s[feature];
        if (v === undefined && s.features) {
          v = s.features[feature];
        }
        if (typeof v === 'number' && Number.isFinite(v)) {
          values.push(v);
        }
      }

      if (values.length < 10) continue;

      const sorted = [...values].sort((a, b) => a - b);
      const hist = buildHistogram(values, 20);
      const q = quantilesFromSorted(sorted);

      result[feature] = {
        feature,
        hist,
        q,
        n: values.length,
      };
    }

    return result;
  }

  /**
   * Create baseline if gates allow
   */
  async createBaselineIfAllowed(
    window: SentWindow,
    reason: BaselineCreateReason = 'AUTO',
    notes?: string
  ): Promise<BaselineCreateResult> {
    const evidence = getEvidenceWriterService();
    const manifest = getSentimentManifestService();

    // F1: Check freeze status
    const freezeCheck = await manifest.gateMutation('baseline_create');
    if (freezeCheck.blocked) {
      return {
        ok: false,
        code: 'FROZEN',
        message: freezeCheck.reason || 'Module is frozen',
        details: {},
      };
    }

    try {
      // Get current URI status
      const reliability = getSentimentReliabilityService();
      const status = await reliability.computeStatus();
      
      const uri: UriSnapshot = {
        score: status.uriScore,
        status: status.level,
        dataHealth: status.components.dataHealth,
        driftHealth: status.components.driftHealth,
        capitalHealth: status.components.capitalHealth,
        calibrationHealth: status.components.calibrationHealth,
        reasons: status.reasons,
      };

      // F2: Log attempt
      await evidence.append(
        'sentiment',
        'baseline_create_attempted',
        'INFO',
        `Baseline create attempted (${reason}) for ${window}`,
        { manifestVersion: manifest.loadManifest().version, uriScore: uri.score, window },
        { uri, reason }
      );

      // Check gate
      const gateCheck = reason === 'AUTO' 
        ? this.checkAutoGate(uri) 
        : this.checkManualGate(uri);

      if (!gateCheck.ok) {
        // F2: Log blocked
        await evidence.append(
          'sentiment',
          'baseline_blocked',
          'WARN',
          `Baseline blocked: ${gateCheck.reason}`,
          { uriScore: uri.score, window },
          { uri, reason: gateCheck.reason }
        );

        return {
          ok: false,
          code: 'GATE_BLOCKED',
          message: `Baseline gate blocked: ${gateCheck.reason}`,
          details: { uri, gate: reason },
        };
      }

      // Check cooldown (skip for first baseline)
      const cooldownCheck = await this.checkCooldown(window);
      if (!cooldownCheck.ok && reason === 'AUTO') {
        return {
          ok: false,
          code: 'COOLDOWN',
          message: cooldownCheck.reason || 'Cooldown active',
          details: { window },
        };
      }

      // Get samples for baseline
      const samples = await SentimentDirSampleModel.find({
        window,
        finalizedAt: { $exists: true },
      })
        .sort({ asOf: -1 })
        .limit(500)
        .lean();

      if (samples.length < BASELINE_GATES.minSamples) {
        return {
          ok: false,
          code: 'NO_DATA',
          message: `Not enough samples: ${samples.length} < ${BASELINE_GATES.minSamples}`,
          details: { sampleCount: samples.length },
        };
      }

      // Build feature distributions
      const featureDistributions = this.buildFeatureDistributions(samples, BASELINE_FEATURES);

      if (Object.keys(featureDistributions).length === 0) {
        return {
          ok: false,
          code: 'NO_DATA',
          message: 'Could not build feature distributions',
          details: { sampleCount: samples.length },
        };
      }

      // Get next version
      const latest = await this.getLatestBaseline(window);
      const nextVersion = (latest?.version ?? 0) + 1;

      // Create baseline
      const doc = await SentimentDriftBaselineModel.create({
        module: 'sentiment',
        window,
        version: nextVersion,
        reason,
        notes,
        sampleCount: samples.length,
        source: 'samples',
        featureDistributions,
        uriAtCreation: uri,
      });

      // F2: Log success
      await evidence.append(
        'sentiment',
        'baseline_created',
        'INFO',
        `Baseline v${nextVersion} created for ${window}`,
        { manifestVersion: manifest.loadManifest().version, uriScore: uri.score, window },
        { version: nextVersion, sampleCount: samples.length, reason }
      );

      console.log(`[DriftBaseline] Created baseline v${nextVersion} for ${window} with ${samples.length} samples`);

      return {
        ok: true,
        baseline: {
          window,
          version: doc.version,
          createdAt: doc.createdAt.toISOString(),
          sampleCount: doc.sampleCount,
          reason: doc.reason,
          uriAtCreation: {
            score: uri.score,
            status: uri.status,
            reasons: uri.reasons,
          },
        },
      };
    } catch (err) {
      console.error('[DriftBaseline] Error creating baseline:', err);
      return {
        ok: false,
        code: 'ERROR',
        message: String(err),
      };
    }
  }

  /**
   * List baseline history
   */
  async listHistory(window: SentWindow, limit: number = 20): Promise<BaselineMeta[]> {
    const docs = await SentimentDriftBaselineModel.find({ 
      module: 'sentiment', 
      window 
    })
      .sort({ createdAt: -1 })
      .limit(Math.min(100, Math.max(1, limit)))
      .lean();

    return docs.map(d => ({
      window: d.window,
      version: d.version,
      createdAt: d.createdAt.toISOString(),
      sampleCount: d.sampleCount,
      reason: d.reason,
      uriAtCreation: {
        score: d.uriAtCreation.score,
        status: d.uriAtCreation.status,
        reasons: d.uriAtCreation.reasons,
      },
    }));
  }
}

// Singleton
let baselineServiceInstance: SentimentDriftBaselineService | null = null;

export function getSentimentDriftBaselineService(): SentimentDriftBaselineService {
  if (!baselineServiceInstance) {
    baselineServiceInstance = new SentimentDriftBaselineService();
  }
  return baselineServiceInstance;
}

console.log('[Sentiment-ML] Drift Baseline Service loaded (BLOCK S2)');
