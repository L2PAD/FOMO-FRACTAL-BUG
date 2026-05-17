/**
 * Regime Score Service v1.1
 * ==========================
 * 
 * BLOCK 7.3: Production-grade proactive regime filter.
 * 
 * NO LOOKAHEAD - only uses data available at entry time.
 * 
 * Components:
 * - ATR Percentile (volatility vs rolling history)
 * - Slope Norm (trend strength via EMA)
 * - ADX Norm (directional strength)
 * 
 * Score formula:
 *   regimeScore = 0.4 * atrPercentile + 0.3 * slopeNorm + 0.3 * adxNorm
 * 
 * Classification:
 *   score < 0.35 → CHOP
 *   0.35-0.55   → TRANSITION  
 *   > 0.55     → TREND
 */

export type RegimeType = 'CHOP' | 'TRANSITION' | 'TREND';

export interface RegimeResult {
  regime: RegimeType;
  regimeScore: number;
  atrPercentile: number;
  slopeNorm: number;
  adxNorm: number;
  components: {
    atr14: number;
    ema20Current: number;
    ema20Lagged: number;
    slope20Raw: number;
    adx14: number;
  };
}

export interface RegimeConfig {
  atrPeriod: number;        // 14
  atrLookback: number;      // 180 days
  atrThreshold: number;     // 0.30 percentile threshold
  emaPeriod: number;        // 20
  slopeLookback: number;    // 20 bars
  slopeNormFactor: number;  // 0.003
  adxPeriod: number;        // 14
  adxMinThreshold: number;  // 15
  adxRange: number;         // 25
  chopThreshold: number;    // 0.35
  trendThreshold: number;   // 0.55
}

export const DEFAULT_REGIME_CONFIG: RegimeConfig = {
  atrPeriod: 14,
  atrLookback: 180,
  atrThreshold: 0.30,
  emaPeriod: 20,
  slopeLookback: 20,
  slopeNormFactor: 0.003,
  adxPeriod: 14,
  adxMinThreshold: 15,
  adxRange: 25,
  chopThreshold: 0.35,
  trendThreshold: 0.55,
};

export class RegimeScoreService {
  private config: RegimeConfig;

  constructor(config: Partial<RegimeConfig> = {}) {
    this.config = { ...DEFAULT_REGIME_CONFIG, ...config };
  }

  /**
   * Evaluate regime from OHLC price series
   * @param closes - Array of closing prices (oldest first, newest last)
   * @param highs - Array of high prices
   * @param lows - Array of low prices
   */
  evaluate(closes: number[], highs: number[], lows: number[]): RegimeResult {
    const { config } = this;
    
    // Need at least enough data for ATR lookback
    const minBars = Math.max(config.atrLookback, config.emaPeriod + config.slopeLookback, config.adxPeriod * 2);
    
    if (closes.length < minBars) {
      // Insufficient data - return conservative CHOP
      return this.makeConservativeResult('Insufficient data');
    }

    // 1. ATR Percentile (volatility)
    const atrSeries = this.computeATRSeries(highs, lows, closes, config.atrPeriod);
    const currentATR = atrSeries[atrSeries.length - 1];
    const lookbackATRs = atrSeries.slice(-config.atrLookback);
    const atrPercentile = this.percentileRank(currentATR, lookbackATRs);

    // 2. Slope Normalized (trend strength)
    const ema20 = this.computeEMA(closes, config.emaPeriod);
    const ema20Current = ema20[ema20.length - 1];
    const ema20Lagged = ema20[ema20.length - 1 - config.slopeLookback] || ema20[0];
    const currentPrice = closes[closes.length - 1];
    const slope20Raw = (ema20Current - ema20Lagged) / currentPrice;
    const slopeNorm = this.clamp(Math.abs(slope20Raw) / config.slopeNormFactor, 0, 1);

    // 3. ADX Normalized (directional dominance)
    const adx14 = this.computeADX(highs, lows, closes, config.adxPeriod);
    const adxNorm = this.clamp((adx14 - config.adxMinThreshold) / config.adxRange, 0, 1);

    // 4. Compute final score
    const regimeScore = 0.4 * atrPercentile + 0.3 * slopeNorm + 0.3 * adxNorm;

    // 5. Classify
    const regime = this.classify(regimeScore);

    return {
      regime,
      regimeScore,
      atrPercentile,
      slopeNorm,
      adxNorm,
      components: {
        atr14: currentATR,
        ema20Current,
        ema20Lagged,
        slope20Raw,
        adx14,
      },
    };
  }

  /**
   * Simplified evaluation with just closes (uses close as proxy for H/L)
   */
  evaluateFromCloses(closes: number[]): RegimeResult {
    // Create synthetic highs/lows from closes (conservative estimate)
    const highs = closes.map((c, i) => {
      if (i === 0) return c;
      return Math.max(c, closes[i - 1]) * 1.002; // ~0.2% above max
    });
    const lows = closes.map((c, i) => {
      if (i === 0) return c;
      return Math.min(c, closes[i - 1]) * 0.998; // ~0.2% below min
    });
    return this.evaluate(closes, highs, lows);
  }

  /**
   * Classify based on score
   */
  private classify(score: number): RegimeType {
    if (score < this.config.chopThreshold) return 'CHOP';
    if (score < this.config.trendThreshold) return 'TRANSITION';
    return 'TREND';
  }

  /**
   * Conservative result when data is insufficient
   */
  private makeConservativeResult(reason: string): RegimeResult {
    console.log(`[RegimeScore] ${reason} - returning CHOP`);
    return {
      regime: 'CHOP',
      regimeScore: 0,
      atrPercentile: 0,
      slopeNorm: 0,
      adxNorm: 0,
      components: {
        atr14: 0,
        ema20Current: 0,
        ema20Lagged: 0,
        slope20Raw: 0,
        adx14: 0,
      },
    };
  }

  // ==================== Technical Analysis Utils ====================

  /**
   * Compute ATR series
   */
  private computeATRSeries(highs: number[], lows: number[], closes: number[], period: number): number[] {
    const trueRanges: number[] = [];
    
    for (let i = 0; i < closes.length; i++) {
      if (i === 0) {
        trueRanges.push(highs[i] - lows[i]);
      } else {
        const hl = highs[i] - lows[i];
        const hc = Math.abs(highs[i] - closes[i - 1]);
        const lc = Math.abs(lows[i] - closes[i - 1]);
        trueRanges.push(Math.max(hl, hc, lc));
      }
    }

    // ATR is SMA/EMA of true range
    return this.computeEMA(trueRanges, period);
  }

  /**
   * Compute EMA
   */
  private computeEMA(values: number[], period: number): number[] {
    if (values.length === 0) return [];
    
    const k = 2 / (period + 1);
    const ema: number[] = [values[0]];
    
    for (let i = 1; i < values.length; i++) {
      ema.push(values[i] * k + ema[i - 1] * (1 - k));
    }
    
    return ema;
  }

  /**
   * Compute ADX (simplified)
   */
  private computeADX(highs: number[], lows: number[], closes: number[], period: number): number {
    if (closes.length < period * 2) return 0;

    // +DM and -DM
    const plusDM: number[] = [];
    const minusDM: number[] = [];
    const tr: number[] = [];

    for (let i = 1; i < closes.length; i++) {
      const highDiff = highs[i] - highs[i - 1];
      const lowDiff = lows[i - 1] - lows[i];

      plusDM.push(highDiff > lowDiff && highDiff > 0 ? highDiff : 0);
      minusDM.push(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0);

      const hl = highs[i] - lows[i];
      const hc = Math.abs(highs[i] - closes[i - 1]);
      const lc = Math.abs(lows[i] - closes[i - 1]);
      tr.push(Math.max(hl, hc, lc));
    }

    // Smoothed values
    const smoothedPlusDM = this.computeEMA(plusDM, period);
    const smoothedMinusDM = this.computeEMA(minusDM, period);
    const smoothedTR = this.computeEMA(tr, period);

    // +DI and -DI
    const plusDI: number[] = [];
    const minusDI: number[] = [];
    const dx: number[] = [];

    for (let i = 0; i < smoothedTR.length; i++) {
      if (smoothedTR[i] === 0) {
        plusDI.push(0);
        minusDI.push(0);
        dx.push(0);
      } else {
        const pdi = (smoothedPlusDM[i] / smoothedTR[i]) * 100;
        const mdi = (smoothedMinusDM[i] / smoothedTR[i]) * 100;
        plusDI.push(pdi);
        minusDI.push(mdi);
        
        const sumDI = pdi + mdi;
        dx.push(sumDI === 0 ? 0 : (Math.abs(pdi - mdi) / sumDI) * 100);
      }
    }

    // ADX is smoothed DX
    const adxSeries = this.computeEMA(dx, period);
    return adxSeries[adxSeries.length - 1] || 0;
  }

  /**
   * Percentile rank
   */
  private percentileRank(value: number, series: number[]): number {
    if (series.length === 0) return 0;
    const count = series.filter(v => v <= value).length;
    return count / series.length;
  }

  /**
   * Clamp value between min and max
   */
  private clamp(v: number, min: number, max: number): number {
    return Math.max(min, Math.min(max, v));
  }
}

// Singleton
let regimeServiceInstance: RegimeScoreService | null = null;

export function getRegimeScoreService(config?: Partial<RegimeConfig>): RegimeScoreService {
  if (!regimeServiceInstance) {
    regimeServiceInstance = new RegimeScoreService(config);
  }
  return regimeServiceInstance;
}

console.log('[Sentiment-ML] Regime Score Service v1.1 loaded (BLOCK 7.3)');
