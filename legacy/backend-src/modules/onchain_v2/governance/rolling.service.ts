/**
 * OnChain V2 — Rolling Stats Service
 * ====================================
 * 
 * Computes 30-day rolling statistics from observations.
 * Used for institutional governance and drift detection.
 */

import { RollingStatsModel, type IRollingStats, type RollingWindow, type ScoreDistribution } from './rolling.model.js';
import { OnchainObservationModel } from '../core/persistence/models.js';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const WINDOW_MS: Record<RollingWindow, number> = {
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
  '90d': 90 * 24 * 60 * 60 * 1000,
};

const DEFAULT_THRESHOLDS = {
  minSamples: 200,
  maxStdScore: 25,
  minAvgConfidence: 0.35,
};

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class RollingStatsService {
  
  /**
   * Compute rolling statistics for a symbol
   */
  async computeRolling(params: {
    symbol: string;
    window?: RollingWindow;
    chainId?: number;
  }): Promise<IRollingStats> {
    const { symbol, window = '30d', chainId = 1 } = params;
    
    const now = Date.now();
    const windowMs = WINDOW_MS[window];
    const fromTs = now - windowMs;
    
    // Get observations from the window
    const observations = await OnchainObservationModel.find({
      symbol,
      t0: { $gte: fromTs, $lte: now },
    })
      .select('t0 state metrics diagnostics')
      .sort({ t0: 1 })
      .lean();
    
    // Compute statistics
    const stats = this.computeStats(observations);
    const scoreDistribution = this.computeScoreDistribution(observations);
    const stateDistribution = this.computeStateDistribution(observations);
    
    // Check health
    const health = {
      sufficientSamples: stats.sampleCount >= DEFAULT_THRESHOLDS.minSamples,
      stableVariance: stats.stdScore <= DEFAULT_THRESHOLDS.maxStdScore,
      recentActivity: this.hasRecentActivity(observations, now),
    };
    
    // Upsert rolling stats
    const rollingStats = await RollingStatsModel.findOneAndUpdate(
      { symbol, window, chainId },
      {
        $set: {
          symbol,
          window,
          chainId,
          
          computedAt: now,
          computedFromTs: fromTs,
          computedToTs: now,
          
          sampleCount: stats.sampleCount,
          
          avgScore: stats.avgScore,
          stdScore: stats.stdScore,
          minScore: stats.minScore,
          maxScore: stats.maxScore,
          medianScore: stats.medianScore,
          
          avgConfidence: stats.avgConfidence,
          stdConfidence: stats.stdConfidence,
          minConfidence: stats.minConfidence,
          maxConfidence: stats.maxConfidence,
          
          dexActivityAvg: stats.dexActivityAvg,
          dexImbalanceAvg: stats.dexImbalanceAvg,
          dexSwapCountAvg: stats.dexSwapCountAvg,
          
          stateDistribution,
          scoreDistribution,
          health,
          
          thresholds: DEFAULT_THRESHOLDS,
        },
      },
      { upsert: true, new: true }
    );
    
    return rollingStats;
  }
  
  /**
   * Get rolling stats for a symbol
   */
  async getRolling(params: {
    symbol: string;
    window?: RollingWindow;
    chainId?: number;
  }): Promise<IRollingStats | null> {
    const { symbol, window = '30d', chainId = 1 } = params;
    
    return RollingStatsModel.findOne({ symbol, window, chainId }).lean();
  }
  
  /**
   * Get all rolling stats
   */
  async getAllRolling(window: RollingWindow = '30d', chainId: number = 1): Promise<IRollingStats[]> {
    return RollingStatsModel.find({ chainId, window }).lean();
  }
  
  /**
   * Compute basic statistics from observations
   */
  private computeStats(observations: any[]): {
    sampleCount: number;
    avgScore: number;
    stdScore: number;
    minScore: number;
    maxScore: number;
    medianScore: number;
    avgConfidence: number;
    stdConfidence: number;
    minConfidence: number;
    maxConfidence: number;
    dexActivityAvg: number;
    dexImbalanceAvg: number;
    dexSwapCountAvg: number;
  } {
    if (observations.length === 0) {
      return {
        sampleCount: 0,
        avgScore: 0, stdScore: 0, minScore: 0, maxScore: 0, medianScore: 0,
        avgConfidence: 0, stdConfidence: 0, minConfidence: 0, maxConfidence: 0,
        dexActivityAvg: 0, dexImbalanceAvg: 0, dexSwapCountAvg: 0,
      };
    }
    
    const scores: number[] = [];
    const confidences: number[] = [];
    const dexActivities: number[] = [];
    const dexImbalances: number[] = [];
    const dexSwapCounts: number[] = [];
    
    for (const obs of observations) {
      const metrics = obs.metrics || {};
      
      // Score (flowScore)
      const score = metrics.flowScore ?? 0;
      scores.push(score);
      
      // Confidence
      const conf = metrics.confidence ?? 0;
      confidences.push(conf);
      
      // DEX metrics
      const dexActivity = metrics.dexActivity ?? 0;
      const dexImbalance = metrics.dexImbalance ?? 0;
      const dexSwaps = obs.diagnostics?.dex?.swaps ?? 0;
      
      dexActivities.push(dexActivity);
      dexImbalances.push(dexImbalance);
      dexSwapCounts.push(dexSwaps);
    }
    
    return {
      sampleCount: observations.length,
      
      // Score stats
      avgScore: this.mean(scores),
      stdScore: this.std(scores),
      minScore: Math.min(...scores),
      maxScore: Math.max(...scores),
      medianScore: this.median(scores),
      
      // Confidence stats
      avgConfidence: this.mean(confidences),
      stdConfidence: this.std(confidences),
      minConfidence: Math.min(...confidences),
      maxConfidence: Math.max(...confidences),
      
      // DEX stats
      dexActivityAvg: this.mean(dexActivities),
      dexImbalanceAvg: this.mean(dexImbalances),
      dexSwapCountAvg: this.mean(dexSwapCounts),
    };
  }
  
  /**
   * Compute score distribution for PSI drift
   * Score is normalized 0-1, so bucket size is 0.1
   */
  private computeScoreDistribution(observations: any[]): ScoreDistribution {
    const bucketCount = 10;
    const bucketSize = 0.1;  // Score range 0-1, 10 buckets of size 0.1
    const buckets = new Array(bucketCount).fill(0);
    
    for (const obs of observations) {
      const score = obs.metrics?.flowScore ?? 0;
      // Score is 0-1, so bucket index is floor(score / 0.1)
      const bucketIndex = Math.min(bucketCount - 1, Math.floor(score / bucketSize));
      buckets[bucketIndex]++;
    }
    
    return {
      buckets,
      bucketSize,
      totalSamples: observations.length,
    };
  }
  
  /**
   * Compute state distribution
   */
  private computeStateDistribution(observations: any[]): {
    ACCUMULATION: number;
    DISTRIBUTION: number;
    NEUTRAL: number;
    LOW_CONF: number;
    NO_DATA: number;
  } {
    const dist = {
      ACCUMULATION: 0,
      DISTRIBUTION: 0,
      NEUTRAL: 0,
      LOW_CONF: 0,
      NO_DATA: 0,
    };
    
    for (const obs of observations) {
      const state = obs.state as keyof typeof dist;
      if (state in dist) {
        dist[state]++;
      }
    }
    
    return dist;
  }
  
  /**
   * Check if there's recent activity (last 24h)
   */
  private hasRecentActivity(observations: any[], now: number): boolean {
    const oneDayAgo = now - 24 * 60 * 60 * 1000;
    return observations.some(obs => obs.t0 >= oneDayAgo);
  }
  
  // ═════════════════════════════════════════════════════════════
  // MATH HELPERS
  // ═════════════════════════════════════════════════════════════
  
  private mean(arr: number[]): number {
    if (arr.length === 0) return 0;
    return Math.round((arr.reduce((a, b) => a + b, 0) / arr.length) * 100) / 100;
  }
  
  private std(arr: number[]): number {
    if (arr.length < 2) return 0;
    const avg = this.mean(arr);
    const variance = arr.reduce((sum, x) => sum + Math.pow(x - avg, 2), 0) / arr.length;
    return Math.round(Math.sqrt(variance) * 100) / 100;
  }
  
  private median(arr: number[]): number {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0
      ? sorted[mid]
      : Math.round(((sorted[mid - 1] + sorted[mid]) / 2) * 100) / 100;
  }
}

// Singleton
export const rollingStatsService = new RollingStatsService();

console.log('[OnChain V2] Rolling Stats Service loaded');
