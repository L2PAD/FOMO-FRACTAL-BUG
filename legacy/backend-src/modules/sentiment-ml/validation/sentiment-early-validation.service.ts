/**
 * Sentiment Early Validation Service
 * ====================================
 * 
 * BLOCK 7: Early Validation Layer
 * 
 * Pure statistical validation — NO ML.
 * Answers the question: "Does bias predict anything or is it noise?"
 * 
 * Three validation layers:
 * 1. Raw Hit Rate — does direction match actual return?
 * 2. Correlation — Pearson(bias, forwardReturn)
 * 3. Strength Segmentation — does stronger bias = better return?
 * 
 * ISOLATION: Read-only, does NOT affect:
 * - Aggregation
 * - Finalize job
 * - UI Prediction
 */

import { SentimentDirSampleModel, SentimentWindow, DirDirection } from '../dataset/sentiment-dir-sample.model.js';

export type ValidationHorizon = '24H' | '7D' | '30D';

export interface StrengthBucket {
  range: string;
  min: number;
  max: number;
  samples: number;
  hitRate: number;
  avgReturn: number;
}

export interface WindowValidationStats {
  horizon: ValidationHorizon;
  sampleCount: number;
  hitRate: number;
  avgForwardReturn: number;
  avgReturnIfLong: number;
  avgReturnIfShort: number;
  avgReturnIfNeutral: number;
  correlation: number;
  strengthBuckets: StrengthBucket[];
}

export interface ValidationSummary {
  overall: {
    totalSamples: number;
    avgHitRate: number;
    avgCorrelation: number;
    hasEdge: boolean;
    edgeStrength: 'NONE' | 'WEAK' | 'MODERATE' | 'STRONG';
  };
  byHorizon: WindowValidationStats[];
  recommendation: string;
}

export class SentimentEarlyValidationService {
  /**
   * Calculate validation stats for a specific horizon
   */
  async calculateWindowStats(horizon: ValidationHorizon): Promise<WindowValidationStats> {
    // Map 24H to window field value
    const windowQuery = horizon as SentimentWindow;

    const samples = await SentimentDirSampleModel.find({
      window: windowQuery,
    }).lean();

    if (!samples.length) {
      return this.emptyStats(horizon);
    }

    const total = samples.length;

    let hits = 0;
    let sumReturn = 0;

    let longReturn = 0;
    let shortReturn = 0;
    let neutralReturn = 0;
    let longCount = 0;
    let shortCount = 0;
    let neutralCount = 0;

    const biasArr: number[] = [];
    const returnArr: number[] = [];

    for (const s of samples) {
      const forward = s.returnPct;
      const bias = s.bias;

      biasArr.push(bias);
      returnArr.push(forward);
      sumReturn += forward;

      // Hit = prediction direction matches actual return direction
      if (
        (bias > 0 && forward > 0) ||
        (bias < 0 && forward < 0) ||
        (bias === 0 && Math.abs(forward) < 0.003) // Within neutral threshold
      ) {
        hits++;
      }

      // Track returns by direction
      const dir = s.direction as DirDirection;
      if (dir === 'LONG') {
        longReturn += forward;
        longCount++;
      } else if (dir === 'SHORT') {
        shortReturn += forward;
        shortCount++;
      } else {
        neutralReturn += forward;
        neutralCount++;
      }
    }

    const correlation = this.pearson(biasArr, returnArr);
    const strengthBuckets = this.buildStrengthBuckets(samples);

    return {
      horizon,
      sampleCount: total,
      hitRate: hits / total,
      avgForwardReturn: sumReturn / total,
      avgReturnIfLong: longCount ? longReturn / longCount : 0,
      avgReturnIfShort: shortCount ? shortReturn / shortCount : 0,
      avgReturnIfNeutral: neutralCount ? neutralReturn / neutralCount : 0,
      correlation,
      strengthBuckets,
    };
  }

  /**
   * Get validation summary across all horizons
   */
  async getValidationSummary(): Promise<ValidationSummary> {
    const horizons: ValidationHorizon[] = ['24H', '7D', '30D'];
    
    const byHorizon = await Promise.all(
      horizons.map(h => this.calculateWindowStats(h))
    );

    const withSamples = byHorizon.filter(s => s.sampleCount > 0);
    
    const totalSamples = withSamples.reduce((sum, s) => sum + s.sampleCount, 0);
    const avgHitRate = withSamples.length 
      ? withSamples.reduce((sum, s) => sum + s.hitRate, 0) / withSamples.length 
      : 0;
    const avgCorrelation = withSamples.length 
      ? withSamples.reduce((sum, s) => sum + s.correlation, 0) / withSamples.length 
      : 0;

    // Determine edge strength
    const { hasEdge, edgeStrength } = this.evaluateEdge(avgHitRate, avgCorrelation, withSamples);

    // Generate recommendation
    const recommendation = this.generateRecommendation(hasEdge, edgeStrength, totalSamples, avgCorrelation);

    return {
      overall: {
        totalSamples,
        avgHitRate,
        avgCorrelation,
        hasEdge,
        edgeStrength,
      },
      byHorizon,
      recommendation,
    };
  }

  /**
   * Pearson correlation coefficient
   */
  private pearson(x: number[], y: number[]): number {
    const n = x.length;
    if (n < 2) return 0;

    const meanX = x.reduce((a, b) => a + b, 0) / n;
    const meanY = y.reduce((a, b) => a + b, 0) / n;

    let num = 0;
    let denX = 0;
    let denY = 0;

    for (let i = 0; i < n; i++) {
      const dx = x[i] - meanX;
      const dy = y[i] - meanY;
      num += dx * dy;
      denX += dx * dx;
      denY += dy * dy;
    }

    const denom = Math.sqrt(denX * denY);
    return denom === 0 ? 0 : num / denom;
  }

  /**
   * Build strength buckets for bias segmentation
   */
  private buildStrengthBuckets(samples: any[]): StrengthBucket[] {
    const ranges: [number, number][] = [
      [0.0, 0.2],
      [0.2, 0.4],
      [0.4, 0.6],
      [0.6, 0.8],
      [0.8, 1.0],
    ];

    return ranges.map(([min, max]) => {
      // Filter by absolute bias strength
      const bucket = samples.filter(
        s => Math.abs(s.bias) >= min && Math.abs(s.bias) < (max === 1.0 ? 1.01 : max)
      );

      if (!bucket.length) {
        return {
          range: `${min.toFixed(1)}-${max.toFixed(1)}`,
          min,
          max,
          samples: 0,
          hitRate: 0,
          avgReturn: 0,
        };
      }

      // Count hits
      const hits = bucket.filter(s =>
        (s.bias > 0 && s.returnPct > 0) ||
        (s.bias < 0 && s.returnPct < 0)
      ).length;

      // Average return
      const avgReturn = bucket.reduce((a, b) => a + b.returnPct, 0) / bucket.length;

      return {
        range: `${min.toFixed(1)}-${max.toFixed(1)}`,
        min,
        max,
        samples: bucket.length,
        hitRate: hits / bucket.length,
        avgReturn,
      };
    });
  }

  /**
   * Evaluate if there's a tradeable edge
   */
  private evaluateEdge(
    avgHitRate: number,
    avgCorrelation: number,
    horizonStats: WindowValidationStats[]
  ): { hasEdge: boolean; edgeStrength: 'NONE' | 'WEAK' | 'MODERATE' | 'STRONG' } {
    // Check for strength gradient
    const hasGradient = horizonStats.some(h => {
      const buckets = h.strengthBuckets;
      if (buckets.length < 3) return false;
      
      // Compare lowest and highest buckets
      const low = buckets.find(b => b.min === 0)?.hitRate ?? 0;
      const high = buckets.find(b => b.min >= 0.6)?.hitRate ?? 0;
      return high > low + 0.05; // At least 5% improvement
    });

    // Correlation thresholds
    if (avgCorrelation >= 0.15 && avgHitRate >= 0.55 && hasGradient) {
      return { hasEdge: true, edgeStrength: 'STRONG' };
    }
    if (avgCorrelation >= 0.10 && avgHitRate >= 0.53) {
      return { hasEdge: true, edgeStrength: 'MODERATE' };
    }
    if (avgCorrelation >= 0.07 && avgHitRate >= 0.51) {
      return { hasEdge: true, edgeStrength: 'WEAK' };
    }
    
    return { hasEdge: false, edgeStrength: 'NONE' };
  }

  /**
   * Generate actionable recommendation
   */
  private generateRecommendation(
    hasEdge: boolean,
    edgeStrength: string,
    totalSamples: number,
    avgCorrelation: number
  ): string {
    if (totalSamples < 30) {
      return `Insufficient data (${totalSamples} samples). Need 30+ samples for reliable validation. Wait for more data accumulation.`;
    }

    if (!hasEdge) {
      if (avgCorrelation < 0.03) {
        return 'No detectable edge. Consider: (1) Increase Connections weight in bias formula, (2) Add bot penalty, (3) Improve symbol clustering.';
      }
      return 'Weak signal detected but below threshold. Continue data collection. May improve with more samples.';
    }

    switch (edgeStrength) {
      case 'STRONG':
        return 'Strong edge detected! Ready for ML layer. Freeze current weighting formula and proceed to Sentiment Lifecycle (training, shadow, promotion).';
      case 'MODERATE':
        return 'Moderate edge detected. Consider proceeding to ML layer or waiting for more validation data. Current formula shows promise.';
      case 'WEAK':
        return 'Weak edge detected. Continue monitoring. May benefit from weighting adjustments before ML implementation.';
      default:
        return 'Validation in progress. Continue data collection.';
    }
  }

  /**
   * Empty stats for horizon with no samples
   */
  private emptyStats(horizon: ValidationHorizon): WindowValidationStats {
    return {
      horizon,
      sampleCount: 0,
      hitRate: 0,
      avgForwardReturn: 0,
      avgReturnIfLong: 0,
      avgReturnIfShort: 0,
      avgReturnIfNeutral: 0,
      correlation: 0,
      strengthBuckets: [
        { range: '0.0-0.2', min: 0, max: 0.2, samples: 0, hitRate: 0, avgReturn: 0 },
        { range: '0.2-0.4', min: 0.2, max: 0.4, samples: 0, hitRate: 0, avgReturn: 0 },
        { range: '0.4-0.6', min: 0.4, max: 0.6, samples: 0, hitRate: 0, avgReturn: 0 },
        { range: '0.6-0.8', min: 0.6, max: 0.8, samples: 0, hitRate: 0, avgReturn: 0 },
        { range: '0.8-1.0', min: 0.8, max: 1.0, samples: 0, hitRate: 0, avgReturn: 0 },
      ],
    };
  }
}

// Singleton
let validationServiceInstance: SentimentEarlyValidationService | null = null;

export function getSentimentEarlyValidationService(): SentimentEarlyValidationService {
  if (!validationServiceInstance) {
    validationServiceInstance = new SentimentEarlyValidationService();
  }
  return validationServiceInstance;
}

console.log('[Sentiment-ML] Early Validation Service loaded (BLOCK 7)');
