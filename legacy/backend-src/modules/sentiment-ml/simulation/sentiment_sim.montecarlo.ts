/**
 * Sentiment Simulation Monte Carlo
 * ==================================
 * 
 * BLOCK 7: Monte Carlo stress testing for robustness validation.
 * 
 * Runs N random permutations of trade sequence to compute:
 * - Confidence intervals for final equity
 * - Max drawdown distribution
 * - Win rate stability
 */

import type { SimTrade } from './sentiment_sim.types.js';

export interface MonteCarloConfig {
  iterations: number;  // 1000+
  startCapital: number;
}

export interface MonteCarloResult {
  iterations: number;
  equityDistribution: {
    p5: number;
    p25: number;
    median: number;
    p75: number;
    p95: number;
    mean: number;
    std: number;
  };
  maxDDDistribution: {
    p5: number;
    p25: number;
    median: number;
    p75: number;
    p95: number;
  };
  probabilityOfProfit: number;  // % of runs ending > start
  riskOfRuin: number;           // % of runs with DD > 30%
}

/**
 * Shuffle array (Fisher-Yates)
 */
function shuffle<T>(array: T[]): T[] {
  const arr = [...array];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/**
 * Simulate one equity path from shuffled returns
 */
function simulatePath(
  returns: number[],
  startCapital: number,
): { finalEquity: number; maxDD: number } {
  let capital = startCapital;
  let peak = startCapital;
  let maxDD = 0;

  for (const ret of returns) {
    capital *= (1 + ret);
    peak = Math.max(peak, capital);
    const dd = (peak - capital) / peak;
    maxDD = Math.max(maxDD, dd);
  }

  return { finalEquity: capital, maxDD };
}

/**
 * Compute percentile from sorted array
 */
function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.floor((p / 100) * sorted.length);
  return sorted[Math.min(idx, sorted.length - 1)];
}

/**
 * Run Monte Carlo simulation
 */
export function runMonteCarlo(
  trades: SimTrade[],
  config: MonteCarloConfig,
): MonteCarloResult {
  const returns = trades.map(t => t.returnPct);
  
  if (returns.length === 0) {
    return {
      iterations: 0,
      equityDistribution: { p5: 1, p25: 1, median: 1, p75: 1, p95: 1, mean: 1, std: 0 },
      maxDDDistribution: { p5: 0, p25: 0, median: 0, p75: 0, p95: 0 },
      probabilityOfProfit: 0,
      riskOfRuin: 0,
    };
  }

  const equities: number[] = [];
  const maxDDs: number[] = [];
  let profitCount = 0;
  let ruinCount = 0;

  for (let i = 0; i < config.iterations; i++) {
    const shuffled = shuffle(returns);
    const { finalEquity, maxDD } = simulatePath(shuffled, config.startCapital);
    
    equities.push(finalEquity);
    maxDDs.push(maxDD);
    
    if (finalEquity > config.startCapital) profitCount++;
    if (maxDD > 0.30) ruinCount++;
  }

  // Sort for percentile calculation
  equities.sort((a, b) => a - b);
  maxDDs.sort((a, b) => a - b);

  // Compute stats
  const mean = equities.reduce((a, b) => a + b, 0) / equities.length;
  const variance = equities.reduce((a, x) => a + (x - mean) ** 2, 0) / equities.length;
  const std = Math.sqrt(variance);

  return {
    iterations: config.iterations,
    equityDistribution: {
      p5: percentile(equities, 5),
      p25: percentile(equities, 25),
      median: percentile(equities, 50),
      p75: percentile(equities, 75),
      p95: percentile(equities, 95),
      mean,
      std,
    },
    maxDDDistribution: {
      p5: percentile(maxDDs, 5),
      p25: percentile(maxDDs, 25),
      median: percentile(maxDDs, 50),
      p75: percentile(maxDDs, 75),
      p95: percentile(maxDDs, 95),
    },
    probabilityOfProfit: profitCount / config.iterations,
    riskOfRuin: ruinCount / config.iterations,
  };
}

console.log('[Sentiment-ML] Simulation Monte Carlo loaded (BLOCK 7)');
