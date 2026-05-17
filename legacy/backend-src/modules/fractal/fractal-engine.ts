/**
 * FRACTAL ENGINE (MINIMAL BUT PRODUCTION-READY)
 * =============================================
 * 
 * Simple market structure detector.
 * 
 * This is NOT ML.
 * This is basic trend + volatility + range detection.
 * 
 * Enough to give Meta Brain orthogonal structural signal.
 */

type Direction = 'UP' | 'DOWN' | 'NEUTRAL';
type Regime = 'TREND' | 'RANGE';

interface FractalForecast {
  direction: Direction;
  expectedReturn: number;
  low: number;
  high: number;
  confidence: number;
  regime: Regime;
  volatility: number;
}

function avg(arr: number[]): number {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function std(arr: number[]): number {
  if (arr.length < 2) return 0;
  const m = avg(arr);
  const variance = avg(arr.map(x => (x - m) ** 2));
  return Math.sqrt(variance);
}

function calcReturns(prices: number[]): number[] {
  const returns: number[] = [];
  for (let i = 1; i < prices.length; i++) {
    returns.push((prices[i] - prices[i - 1]) / prices[i - 1]);
  }
  return returns;
}

function detectTrend(prices: number[]): Direction {
  if (prices.length < 20) return 'NEUTRAL';
  
  // Short-term vs Long-term moving average
  const shortMA = avg(prices.slice(-5));
  const longMA = avg(prices.slice(-20));
  
  const delta = (shortMA - longMA) / longMA;
  
  if (delta > 0.015) return 'UP';    // 1.5% above long MA
  if (delta < -0.015) return 'DOWN'; // 1.5% below long MA
  return 'NEUTRAL';
}

function detectRegime(prices: number[]): Regime {
  if (prices.length < 10) return 'RANGE';
  
  // Calculate price range over last 20 candles
  const recent = prices.slice(-20);
  const high = Math.max(...recent);
  const low = Math.min(...recent);
  const current = prices[prices.length - 1];
  
  const rangeWidth = (high - low) / current;
  
  // If price moving in tight range, it's RANGE
  // If price has wider swings, it's TREND
  return rangeWidth < 0.05 ? 'RANGE' : 'TREND';
}

/**
 * Build fractal forecast from price series
 * 
 * @param prices - Price series (oldest to newest)
 * @returns Forecast with direction, expected return, range
 */
export function buildFractalForecast(prices: number[]): FractalForecast {
  if (prices.length < 20) {
    throw new Error('Not enough price data (need at least 20 candles)');
  }
  
  const currentPrice = prices[prices.length - 1];
  
  // Calculate returns and volatility
  const returns = calcReturns(prices);
  const volatility = std(returns);
  
  // Detect trend and regime
  const trend = detectTrend(prices);
  const regime = detectRegime(prices);
  
  // Determine direction and expected return
  let direction: Direction = 'NEUTRAL';
  let expectedReturn = 0;
  
  if (trend === 'UP') {
    direction = 'UP';
    // In uptrend, expect continuation scaled by volatility
    expectedReturn = Math.max(0.01, Math.min(0.08, volatility * 3));
  } else if (trend === 'DOWN') {
    direction = 'DOWN';
    // In downtrend, expect continuation scaled by volatility
    expectedReturn = -Math.max(0.01, Math.min(0.08, volatility * 3));
  } else {
    direction = 'NEUTRAL';
    expectedReturn = 0;
  }
  
  // Calculate range (low/high bands)
  const rangeWidth = Math.max(0.02, Math.min(0.15, volatility * 2.5));
  
  const low = currentPrice * (1 - rangeWidth);
  const high = currentPrice * (1 + rangeWidth);
  
  // Confidence based on:
  // - Strength of trend (abs expected return)
  // - Regime clarity (TREND = higher confidence)
  let confidence = 0.3 + Math.abs(expectedReturn) * 4;
  
  if (regime === 'TREND') {
    confidence *= 1.2; // Boost confidence in trending markets
  }
  
  confidence = Math.min(0.85, Math.max(0.2, confidence));
  
  return {
    direction,
    expectedReturn,
    low,
    high,
    confidence,
    regime,
    volatility,
  };
}

export default buildFractalForecast;
