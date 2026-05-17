/**
 * OnChain V2 — Drift Service
 * ============================
 * 
 * O9.2: PSI Drift Layer (v1.0.0-rc.1)
 * Calculates PSI (Population Stability Index) drift 
 * between current distribution and baseline.
 * 
 * AUTO-BASELINE POLICY:
 * - Auto-update baseline ONLY when:
 *   1. sampleCount >= 200
 *   2. PSI < 0.15 for 3 consecutive cycles
 * - Otherwise: manual update via UI only
 */

import { BaselineModel, type IBaseline } from './baseline.model.js';
import { RollingStatsModel, type IRollingStats } from './rolling.model.js';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const EPSILON = 0.0001;  // Small value to avoid division by zero

// Auto-baseline policy
const AUTO_BASELINE_MIN_SAMPLES = 200;
const AUTO_BASELINE_STABLE_CYCLES = 3;
const AUTO_BASELINE_MAX_PSI = 0.15;

const DRIFT_THRESHOLDS = {
  warn: 0.15,
  degraded: 0.30,
  critical: 0.50,
};

export type DriftLevel = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';

// ═══════════════════════════════════════════════════════════════
// STABLE CYCLES TRACKING (for auto-baseline policy)
// ═══════════════════════════════════════════════════════════════

interface StableCycleState {
  consecutiveStableCycles: number;
  lastPsi: number;
  lastCheckedAt: number;
}

const stableCycleStates = new Map<string, StableCycleState>();

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class DriftService {
  
  /**
   * Create a new baseline from current rolling stats
   */
  async createBaseline(params: {
    symbol: string;
    metric?: 'score' | 'confidence' | 'dexActivity';
    window?: '30d';
    chainId?: number;
  }): Promise<IBaseline> {
    const { symbol, metric = 'score', window = '30d', chainId = 1 } = params;
    
    // Get current rolling stats
    const rolling = await RollingStatsModel.findOne({ 
      symbol, 
      window,
      chainId,
    }).lean();
    
    if (!rolling) {
      throw new Error(`No rolling stats found for ${symbol}. Run compute-rolling first.`);
    }
    
    if (rolling.sampleCount < 50) {
      throw new Error(`Insufficient samples (${rolling.sampleCount}). Need at least 50 for baseline.`);
    }
    
    // Get latest version
    const latestBaseline = await BaselineModel.findOne({ chainId, symbol, metric })
      .sort({ version: -1 })
      .lean();
    
    const newVersion = latestBaseline ? latestBaseline.version + 1 : 1;
    
    // Deactivate old baselines
    await BaselineModel.updateMany(
      { chainId, symbol, metric, active: true },
      { $set: { active: false } }
    );
    
    // Normalize buckets to ratios (sum = 1)
    const rawBuckets = rolling.scoreDistribution.buckets;
    const total = rawBuckets.reduce((a, b) => a + b, 0);
    const normalizedBuckets = rawBuckets.map(b => 
      total > 0 ? b / total : 1 / rawBuckets.length
    );
    
    // Create new baseline
    const baseline = await BaselineModel.create({
      chainId,
      symbol,
      metric,
      version: newVersion,
      createdAt: Date.now(),
      sampleCount: rolling.sampleCount,
      sourceWindow: window,
      distribution: {
        buckets: normalizedBuckets,
        bucketSize: rolling.scoreDistribution.bucketSize,
        rawBuckets,
      },
      stats: {
        avgScore: rolling.avgScore,
        stdScore: rolling.stdScore,
        medianScore: rolling.medianScore,
      },
      active: true,
    });
    
    return baseline;
  }
  
  /**
   * Get active baseline for a symbol
   */
  async getBaseline(params: {
    symbol: string;
    metric?: 'score';
    chainId?: number;
  }): Promise<IBaseline | null> {
    const { symbol, metric = 'score', chainId = 1 } = params;
    return BaselineModel.findOne({ chainId, symbol, metric, active: true }).lean();
  }
  
  /**
   * Calculate PSI drift between current and baseline
   */
  async calculateDrift(params: {
    symbol: string;
    metric?: 'score';
    window?: '30d';
    chainId?: number;
  }): Promise<{
    psi: number;
    level: DriftLevel;
    hasBaseline: boolean;
    sampleCount: number;
    bucketComparison: {
      bucket: number;
      expected: number;
      actual: number;
      contribution: number;
    }[];
    thresholds: typeof DRIFT_THRESHOLDS;
  }> {
    const { symbol, metric = 'score', window = '30d', chainId = 1 } = params;
    
    // Get baseline
    const baseline = await this.getBaseline({ symbol, metric, chainId });
    
    if (!baseline) {
      return {
        psi: 0,
        level: 'OK',
        hasBaseline: false,
        sampleCount: 0,
        bucketComparison: [],
        thresholds: DRIFT_THRESHOLDS,
      };
    }
    
    // Get current rolling stats
    const rolling = await RollingStatsModel.findOne({ chainId, symbol, window }).lean();
    
    if (!rolling) {
      return {
        psi: 0,
        level: 'OK',
        hasBaseline: true,
        sampleCount: 0,
        bucketComparison: [],
        thresholds: DRIFT_THRESHOLDS,
      };
    }
    
    // Normalize current buckets
    const currentRaw = rolling.scoreDistribution.buckets;
    const currentTotal = currentRaw.reduce((a, b) => a + b, 0);
    const currentNormalized = currentRaw.map(b => 
      currentTotal > 0 ? b / currentTotal : 1 / currentRaw.length
    );
    
    // Calculate PSI
    const expected = baseline.distribution.buckets;
    const actual = currentNormalized;
    
    let psi = 0;
    const bucketComparison = [];
    
    for (let i = 0; i < expected.length; i++) {
      const e = Math.max(expected[i], EPSILON);
      const a = Math.max(actual[i], EPSILON);
      
      const contribution = (a - e) * Math.log(a / e);
      psi += contribution;
      
      bucketComparison.push({
        bucket: i,
        expected: Math.round(expected[i] * 10000) / 10000,
        actual: Math.round(actual[i] * 10000) / 10000,
        contribution: Math.round(contribution * 10000) / 10000,
      });
    }
    
    psi = Math.round(psi * 10000) / 10000;
    
    // Determine level
    let level: DriftLevel = 'OK';
    if (psi >= DRIFT_THRESHOLDS.critical) {
      level = 'CRITICAL';
    } else if (psi >= DRIFT_THRESHOLDS.degraded) {
      level = 'DEGRADED';
    } else if (psi >= DRIFT_THRESHOLDS.warn) {
      level = 'WARN';
    }
    
    return {
      psi,
      level,
      hasBaseline: true,
      sampleCount: rolling.sampleCount,
      bucketComparison,
      thresholds: DRIFT_THRESHOLDS,
    };
  }
  
  /**
   * Check if auto-baseline update is allowed
   * Returns true only if:
   * - sampleCount >= 200
   * - PSI < 0.15 for 3 consecutive cycles
   */
  checkAutoBaselineEligibility(params: {
    symbol: string;
    psi: number;
    sampleCount: number;
  }): { eligible: boolean; reason: string; stableCycles: number } {
    const { symbol, psi, sampleCount } = params;
    const key = symbol;
    
    // Get or create state
    let state = stableCycleStates.get(key);
    if (!state) {
      state = { consecutiveStableCycles: 0, lastPsi: psi, lastCheckedAt: Date.now() };
      stableCycleStates.set(key, state);
    }
    
    // Update stable cycles
    if (psi < AUTO_BASELINE_MAX_PSI) {
      state.consecutiveStableCycles++;
    } else {
      state.consecutiveStableCycles = 0;
    }
    state.lastPsi = psi;
    state.lastCheckedAt = Date.now();
    
    // Check eligibility
    if (sampleCount < AUTO_BASELINE_MIN_SAMPLES) {
      return {
        eligible: false,
        reason: `Insufficient samples: ${sampleCount} < ${AUTO_BASELINE_MIN_SAMPLES}`,
        stableCycles: state.consecutiveStableCycles,
      };
    }
    
    if (state.consecutiveStableCycles < AUTO_BASELINE_STABLE_CYCLES) {
      return {
        eligible: false,
        reason: `Need ${AUTO_BASELINE_STABLE_CYCLES} stable cycles, have ${state.consecutiveStableCycles}`,
        stableCycles: state.consecutiveStableCycles,
      };
    }
    
    return {
      eligible: true,
      reason: 'Eligible for auto-baseline update',
      stableCycles: state.consecutiveStableCycles,
    };
  }
  
  /**
   * Get auto-baseline policy config
   */
  getAutoBaselinePolicy(): {
    minSamples: number;
    stableCycles: number;
    maxPsi: number;
  } {
    return {
      minSamples: AUTO_BASELINE_MIN_SAMPLES,
      stableCycles: AUTO_BASELINE_STABLE_CYCLES,
      maxPsi: AUTO_BASELINE_MAX_PSI,
    };
  }
  
  /**
   * Get all baselines
   */
  async getAllBaselines(chainId: number = 1): Promise<IBaseline[]> {
    return BaselineModel.find({ chainId, active: true }).lean();
  }
}

// Singleton
export const driftService = new DriftService();

console.log('[OnChain V2] Drift Service loaded (v1.0.0-rc.1)');
