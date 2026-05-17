/**
 * Sentiment CHOP Gate Service
 * ============================
 * 
 * BLOCK 8: Production-grade CHOP filter without lookahead.
 * 
 * NO FUTURE DATA - only uses bars up to and including `index`.
 * 
 * Three independent filters (ALL must pass for CHOP):
 * 1. ATR Percentile < floor → low volatility
 * 2. Range Compression < floor → price squeeze
 * 3. Trend Slope < floor → no momentum
 */

import { ChopConfig, ChopTagResult, DEFAULT_CHOP_CONFIG } from './chop.types.js';

export class SentimentChopGateService {
  private config: ChopConfig;

  constructor(config: Partial<ChopConfig> = {}) {
    this.config = { ...DEFAULT_CHOP_CONFIG, ...config };
  }

  /**
   * Tag CHOP at specific index using ONLY data available at that time
   * @param prices - close prices array (oldest first)
   * @param highs - high prices array
   * @param lows - low prices array
   * @param index - current bar index (asOf)
   */
  tagChopAtIndex(
    prices: number[],
    highs: number[],
    lows: number[],
    index: number
  ): ChopTagResult {
    // Need enough data for ATR lookback
    const minBars = this.config.atrPeriod + this.config.atrLookback;
    
    if (index < minBars || prices.length <= index) {
      return {
        isChop: false,
        atrPercentile: 0.5,
        rangeN: 0.1,
        slope: 0.01,
        severityScore: 0,
        components: {
          atrPass: false,
          rangePass: false,
          slopePass: false,
        },
      };
    }

    // 1. ATR Percentile
    const atrPercentile = this.computeATRPercentile(highs, lows, prices, index);
    const atrPass = atrPercentile < this.config.atrPercentileFloor;

    // 2. Range Compression
    const rangeN = this.computeRangeN(highs, lows, prices, index);
    const rangePass = rangeN < this.config.rangeFloor;

    // 3. Trend Slope
    const slope = this.computeSlope(prices, index);
    const slopePass = Math.abs(slope) < this.config.slopeFloor;

    // CHOP = ALL THREE must pass (conservative AND logic)
    const isChop = atrPass && rangePass && slopePass;
    
    // Severity score: how CHOP-like is this condition? (0-1)
    // Lower ATR, Range, Slope = more CHOP-like
    const atrScore = 1 - atrPercentile;  // Low ATR = high score
    const rangeScore = 1 - Math.min(rangeN / 0.5, 1);  // Low range = high score
    const slopeScore = 1 - Math.min(Math.abs(slope) / 0.3, 1);  // Low slope = high score
    const severityScore = (atrScore + rangeScore + slopeScore) / 3;

    return {
      isChop,
      atrPercentile,
      rangeN,
      slope,
      severityScore,
      components: {
        atrPass,
        rangePass,
        slopePass,
      },
    };
  }

  /**
   * Update config for grid search
   */
  updateConfig(config: Partial<ChopConfig>): void {
    this.config = { ...this.config, ...config };
  }

  getConfig(): ChopConfig {
    return { ...this.config };
  }

  // -------------------------
  // ATR Calculation
  // -------------------------

  private computeATR(
    highs: number[],
    lows: number[],
    closes: number[],
    index: number
  ): number {
    const period = this.config.atrPeriod;
    let sumTR = 0;

    for (let i = index - period + 1; i <= index; i++) {
      const high = highs[i];
      const low = lows[i];
      const prevClose = i > 0 ? closes[i - 1] : closes[i];

      const tr = Math.max(
        high - low,
        Math.abs(high - prevClose),
        Math.abs(low - prevClose)
      );

      sumTR += tr;
    }

    return sumTR / period;
  }

  private computeATRPercentile(
    highs: number[],
    lows: number[],
    closes: number[],
    index: number
  ): number {
    const lookback = this.config.atrLookback;
    const startIdx = Math.max(this.config.atrPeriod, index - lookback + 1);
    const atrs: number[] = [];

    for (let i = startIdx; i <= index; i++) {
      atrs.push(this.computeATR(highs, lows, closes, i));
    }

    if (atrs.length === 0) return 0.5;

    const current = atrs[atrs.length - 1];
    const sorted = [...atrs].sort((a, b) => a - b);
    
    // Find percentile rank
    let rank = 0;
    for (let i = 0; i < sorted.length; i++) {
      if (sorted[i] <= current) rank = i + 1;
    }

    return rank / sorted.length;
  }

  // -------------------------
  // Range Compression
  // -------------------------

  private computeRangeN(
    highs: number[],
    lows: number[],
    closes: number[],
    index: number
  ): number {
    const N = this.config.rangeLookback;
    const startIdx = Math.max(0, index - N + 1);

    const windowHighs = highs.slice(startIdx, index + 1);
    const windowLows = lows.slice(startIdx, index + 1);

    const windowHigh = Math.max(...windowHighs);
    const windowLow = Math.min(...windowLows);
    const price = closes[index];

    if (price <= 0) return 0.1;

    return (windowHigh - windowLow) / price;
  }

  // -------------------------
  // Trend Slope
  // -------------------------

  private computeSlope(closes: number[], index: number): number {
    const L = this.config.slopeLookback;
    
    if (index < L) return 0.01;

    const prev = closes[index - L];
    const current = closes[index];

    if (current <= 0) return 0;

    return (current - prev) / current;
  }
}

// Singleton
let chopGateInstance: SentimentChopGateService | null = null;

export function getSentimentChopGateService(config?: Partial<ChopConfig>): SentimentChopGateService {
  if (!chopGateInstance) {
    chopGateInstance = new SentimentChopGateService(config);
  } else if (config) {
    chopGateInstance.updateConfig(config);
  }
  return chopGateInstance;
}

// Factory for grid search (creates new instance)
export function createChopGateService(config: Partial<ChopConfig>): SentimentChopGateService {
  return new SentimentChopGateService(config);
}

console.log('[Sentiment-ML] CHOP Gate Service loaded (BLOCK 8)');
