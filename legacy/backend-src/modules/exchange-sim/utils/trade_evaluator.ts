/**
 * Exchange Simulation Trade Evaluator
 * ====================================
 * 
 * Evaluates trades using the Combined Verdict (ENV + DIR).
 * This is the core logic for Capital-Centric simulation.
 */

import { TradeEvaluation } from '../exchange_sim.types.js';

// ═══════════════════════════════════════════════════════════════
// TRADE EVALUATION FUNCTION
// ═══════════════════════════════════════════════════════════════

/**
 * Evaluate a trade using the dual-model system.
 * 
 * Rules:
 * - If ENV != USE → trade skipped
 * - If DIR == NEUTRAL → trade skipped
 * - Otherwise: check if direction prediction was correct
 */
export function evaluateTrade(params: {
  env: { label: 'USE' | 'WARNING' | 'IGNORE'; confidence: number };
  dir: { label: 'UP' | 'DOWN' | 'NEUTRAL'; confidence: number };
  realizedReturn: number;
}): TradeEvaluation {
  const { env, dir, realizedReturn } = params;
  
  // ENV gate: IGNORE blocks trade
  if (env.label === 'IGNORE') {
    return {
      traded: false,
      envLabel: env.label,
      dirLabel: dir.label,
      realizedReturn,
      skippedReason: 'ENV_IGNORE',
    };
  }
  
  // DIR gate: NEUTRAL = no clear signal
  if (dir.label === 'NEUTRAL') {
    return {
      traded: false,
      envLabel: env.label,
      dirLabel: dir.label,
      realizedReturn,
      skippedReason: 'DIR_NEUTRAL',
    };
  }
  
  // WARNING mode: still trade but with reduced size
  // For simulation, we still count it as a trade
  
  // Trade was executed
  const directionCorrect =
    (dir.label === 'UP' && realizedReturn > 0) ||
    (dir.label === 'DOWN' && realizedReturn < 0);
  
  return {
    traded: true,
    win: directionCorrect,
    envLabel: env.label,
    dirLabel: dir.label,
    realizedReturn,
  };
}

// ═══════════════════════════════════════════════════════════════
// TRADE STATS ACCUMULATOR
// ═══════════════════════════════════════════════════════════════

export class TradeStatsAccumulator {
  private wins = 0;
  private losses = 0;
  private skipped = 0;
  private returns: number[] = [];
  
  add(evaluation: TradeEvaluation): void {
    if (!evaluation.traded) {
      this.skipped++;
      return;
    }
    
    if (evaluation.win) {
      this.wins++;
    } else {
      this.losses++;
    }
    
    this.returns.push(evaluation.realizedReturn);
  }
  
  getStats(): {
    totalTrades: number;
    wins: number;
    losses: number;
    skippedTrades: number;
    tradeWinRate: number;
  } {
    const totalTrades = this.wins + this.losses;
    
    return {
      totalTrades,
      wins: this.wins,
      losses: this.losses,
      skippedTrades: this.skipped,
      tradeWinRate: totalTrades > 0 ? this.wins / totalTrades : 0,
    };
  }
  
  getReturns(): number[] {
    return [...this.returns];
  }
  
  reset(): void {
    this.wins = 0;
    this.losses = 0;
    this.skipped = 0;
    this.returns = [];
  }
}

// ═══════════════════════════════════════════════════════════════
// EQUITY CURVE CALCULATOR
// ═══════════════════════════════════════════════════════════════

export function computeEquityCurve(returns: number[]): {
  equityFinal: number;
  maxDrawdown: number;
  sharpeLike: number;
  stabilityScore: number;
  avgReturn: number;
  stdReturn: number;
  consecutiveLossMax: number;
} {
  if (returns.length === 0) {
    return {
      equityFinal: 1.0,
      maxDrawdown: 0,
      sharpeLike: 0,
      stabilityScore: 0.5,
      avgReturn: 0,
      stdReturn: 0,
      consecutiveLossMax: 0,
    };
  }
  
  // Calculate equity curve and drawdown
  let equity = 1.0;
  let peak = 1.0;
  let maxDD = 0.0;
  
  for (const r of returns) {
    equity = equity * (1 + r);
    peak = Math.max(peak, equity);
    const dd = (peak - equity) / peak;
    maxDD = Math.max(maxDD, dd);
  }
  
  // Calculate returns statistics
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  
  let stdReturn = 0;
  if (returns.length >= 2) {
    const variance = returns.reduce((a, b) => a + (b - avgReturn) ** 2, 0) / (returns.length - 1);
    stdReturn = Math.sqrt(variance);
  }
  
  // Sharpe-like ratio
  const sharpeLike = stdReturn > 0 ? avgReturn / stdReturn : 0;
  
  // Consecutive losses
  let consecutiveLosses = 0;
  let maxConsecutiveLosses = 0;
  for (const r of returns) {
    if (r < 0) {
      consecutiveLosses++;
      maxConsecutiveLosses = Math.max(maxConsecutiveLosses, consecutiveLosses);
    } else {
      consecutiveLosses = 0;
    }
  }
  
  // Stability score
  let stabilityScore = 0.5;
  if (stdReturn > 0 && Math.abs(avgReturn) > 0.0001) {
    const volRatio = stdReturn / Math.abs(avgReturn);
    const base = 1 / (1 + volRatio);
    stabilityScore = Math.max(0, Math.min(1, base * (1 - maxDD)));
  }
  
  return {
    equityFinal: equity,
    maxDrawdown: Math.max(0, Math.min(1, maxDD)),
    sharpeLike,
    stabilityScore,
    avgReturn,
    stdReturn,
    consecutiveLossMax: maxConsecutiveLosses,
  };
}

console.log('[Exchange Sim] Trade evaluator loaded');
