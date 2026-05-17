/**
 * CHOP Gate Types
 * ================
 * 
 * BLOCK 8: Production-grade CHOP filter without lookahead.
 * 
 * Three independent filters:
 * 1. ATR Percentile - volatility squeeze
 * 2. Range Compression - price range squeeze  
 * 3. Trend Slope - momentum absence
 * 
 * CHOP = ALL THREE conditions must be true (conservative AND logic)
 */

export interface ChopConfig {
  atrPeriod: number;           // 14
  atrLookback: number;         // 90 (for percentile)
  atrPercentileFloor: number;  // 0.25

  rangeLookback: number;       // 20
  rangeFloor: number;          // 0.06

  slopeLookback: number;       // 10
  slopeFloor: number;          // 0.002
}

export interface ChopTagResult {
  isChop: boolean;
  atrPercentile: number;
  rangeN: number;
  slope: number;
  severityScore: number;  // 0-1, higher = more CHOP-like, for position sizing
  components: {
    atrPass: boolean;    // atrPercentile < floor
    rangePass: boolean;  // rangeN < floor
    slopePass: boolean;  // abs(slope) < floor
  };
}

export const DEFAULT_CHOP_CONFIG: ChopConfig = {
  atrPeriod: 14,
  atrLookback: 90,
  atrPercentileFloor: 0.25,

  rangeLookback: 20,
  rangeFloor: 0.06,

  slopeLookback: 10,
  slopeFloor: 0.002,
};

console.log('[Sentiment-ML] CHOP Types loaded (BLOCK 8)');
