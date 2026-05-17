/**
 * Sentiment Dataset Stats Service
 * =================================
 * 
 * BLOCK 6: Statistics and early performance validation.
 * 
 * Provides:
 * - Sample counts by window
 * - Label distribution
 * - Coverage date range
 * - Raw hit rate (sentiment direction vs actual return)
 * - Correlation metrics
 */

import { SentimentDirSampleModel, SentimentWindow, DirLabel } from './sentiment-dir-sample.model.js';

export interface WindowStats {
  window: SentimentWindow;
  count: number;
  labels: { UP: number; DOWN: number; NEUTRAL: number };
}

export interface DatasetStats {
  total: number;
  byWindow: WindowStats[];
  coverage: {
    from: Date | null;
    to: Date | null;
  };
}

export interface HitRateResult {
  window: SentimentWindow;
  sampleCount: number;
  hitCount: number;
  hitRate: number;
  byLabel: {
    UP: { total: number; correct: number; rate: number };
    DOWN: { total: number; correct: number; rate: number };
    NEUTRAL: { total: number; correct: number; rate: number };
  };
}

export interface CorrelationResult {
  window: SentimentWindow;
  sampleCount: number;
  biasReturnCorrelation: number;  // Pearson correlation
  avgReturnByDirection: {
    LONG: number;
    SHORT: number;
    NEUTRAL: number;
  };
}

export class SentimentDatasetStatsService {
  /**
   * Get overall dataset statistics
   */
  async getStats(): Promise<DatasetStats> {
    // Count by window
    const byWindowAgg = await SentimentDirSampleModel.aggregate([
      {
        $group: {
          _id: '$window',
          count: { $sum: 1 },
          upCount: { $sum: { $cond: [{ $eq: ['$label', 'UP'] }, 1, 0] } },
          downCount: { $sum: { $cond: [{ $eq: ['$label', 'DOWN'] }, 1, 0] } },
          neutralCount: { $sum: { $cond: [{ $eq: ['$label', 'NEUTRAL'] }, 1, 0] } },
        },
      },
      { $sort: { _id: 1 } },
    ]);

    const byWindow: WindowStats[] = byWindowAgg.map(w => ({
      window: w._id as SentimentWindow,
      count: w.count,
      labels: {
        UP: w.upCount,
        DOWN: w.downCount,
        NEUTRAL: w.neutralCount,
      },
    }));

    const total = byWindow.reduce((sum, w) => sum + w.count, 0);

    // Coverage range
    const oldest = await SentimentDirSampleModel.findOne({})
      .sort({ asOf: 1 })
      .select({ asOf: 1 })
      .lean();

    const newest = await SentimentDirSampleModel.findOne({})
      .sort({ asOf: -1 })
      .select({ asOf: 1 })
      .lean();

    return {
      total,
      byWindow,
      coverage: {
        from: oldest?.asOf ?? null,
        to: newest?.asOf ?? null,
      },
    };
  }

  /**
   * Calculate raw hit rate for a window.
   * Hit = sentiment direction matches actual price direction.
   */
  async getHitRate(window: SentimentWindow): Promise<HitRateResult> {
    const samples = await SentimentDirSampleModel.find({ window })
      .select({ direction: 1, label: 1, bias: 1, returnPct: 1 })
      .lean();

    const result: HitRateResult = {
      window,
      sampleCount: samples.length,
      hitCount: 0,
      hitRate: 0,
      byLabel: {
        UP: { total: 0, correct: 0, rate: 0 },
        DOWN: { total: 0, correct: 0, rate: 0 },
        NEUTRAL: { total: 0, correct: 0, rate: 0 },
      },
    };

    if (samples.length === 0) return result;

    for (const s of samples) {
      // Predicted direction
      const predicted = s.direction;
      // Actual direction (from label)
      const actual = s.label as DirLabel;

      // Map to comparable values
      const predDir = predicted === 'LONG' ? 'UP' : predicted === 'SHORT' ? 'DOWN' : 'NEUTRAL';

      // Count by label
      result.byLabel[actual].total++;

      // Check hit
      if (predDir === actual) {
        result.hitCount++;
        result.byLabel[actual].correct++;
      }
    }

    result.hitRate = result.hitCount / result.sampleCount;

    // Calculate rates per label
    for (const label of ['UP', 'DOWN', 'NEUTRAL'] as const) {
      if (result.byLabel[label].total > 0) {
        result.byLabel[label].rate = result.byLabel[label].correct / result.byLabel[label].total;
      }
    }

    return result;
  }

  /**
   * Calculate correlation between bias and forward return.
   * Also computes average return by sentiment direction.
   */
  async getCorrelation(window: SentimentWindow): Promise<CorrelationResult> {
    const samples = await SentimentDirSampleModel.find({ window })
      .select({ bias: 1, returnPct: 1, direction: 1 })
      .lean();

    const result: CorrelationResult = {
      window,
      sampleCount: samples.length,
      biasReturnCorrelation: 0,
      avgReturnByDirection: {
        LONG: 0,
        SHORT: 0,
        NEUTRAL: 0,
      },
    };

    if (samples.length < 2) return result;

    // Calculate Pearson correlation
    const biases = samples.map(s => s.bias);
    const returns = samples.map(s => s.returnPct);

    const meanBias = biases.reduce((a, b) => a + b, 0) / biases.length;
    const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length;

    let numerator = 0;
    let denomBias = 0;
    let denomReturn = 0;

    for (let i = 0; i < samples.length; i++) {
      const diffBias = biases[i] - meanBias;
      const diffReturn = returns[i] - meanReturn;
      numerator += diffBias * diffReturn;
      denomBias += diffBias * diffBias;
      denomReturn += diffReturn * diffReturn;
    }

    const denom = Math.sqrt(denomBias * denomReturn);
    if (denom > 0) {
      result.biasReturnCorrelation = numerator / denom;
    }

    // Average return by direction
    const byDir: Record<string, { sum: number; count: number }> = {
      LONG: { sum: 0, count: 0 },
      SHORT: { sum: 0, count: 0 },
      NEUTRAL: { sum: 0, count: 0 },
    };

    for (const s of samples) {
      const dir = s.direction || 'NEUTRAL';
      byDir[dir].sum += s.returnPct;
      byDir[dir].count++;
    }

    for (const dir of ['LONG', 'SHORT', 'NEUTRAL'] as const) {
      if (byDir[dir].count > 0) {
        result.avgReturnByDirection[dir] = byDir[dir].sum / byDir[dir].count;
      }
    }

    return result;
  }

  /**
   * Get recent samples for debugging
   */
  async getRecentSamples(limit = 10): Promise<any[]> {
    return SentimentDirSampleModel.find({})
      .sort({ createdAt: -1 })
      .limit(limit)
      .lean();
  }
}

// Singleton
let statsInstance: SentimentDatasetStatsService | null = null;

export function getSentimentDatasetStatsService(): SentimentDatasetStatsService {
  if (!statsInstance) {
    statsInstance = new SentimentDatasetStatsService();
  }
  return statsInstance;
}
