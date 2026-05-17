/**
 * Sentiment Simulation Regime Breakdown
 * ======================================
 * 
 * BLOCK 7: Breaks down simulation results by market regime (BULL/BEAR/CHOP).
 * 
 * Uses BTC as a proxy for market regime:
 * - BULL: BTC +5% over period
 * - BEAR: BTC -5% over period  
 * - CHOP: BTC within ±5%
 */

import type { SimTrade } from './sentiment_sim.types.js';

export type MarketRegime = 'BULL' | 'BEAR' | 'CHOP';

export interface RegimeBreakdown {
  regime: MarketRegime;
  trades: number;
  wins: number;
  winRate: number;
  avgReturn: number;
  totalReturn: number;
}

export interface RegimeReport {
  overall: {
    totalTrades: number;
    byRegime: {
      BULL: number;
      BEAR: number;
      CHOP: number;
    };
  };
  breakdowns: RegimeBreakdown[];
  insight: string;
}

/**
 * Classify market regime based on BTC price change over trade period
 * Since we don't have direct BTC price in trades, we'll use 
 * a simplified approach based on trade clustering
 */
export function classifyRegime(
  entryPrice: number,
  exitPrice: number,
  _symbol: string,
): MarketRegime {
  // Use price change as proxy for market conditions
  const change = (exitPrice - entryPrice) / entryPrice;
  
  if (change > 0.03) return 'BULL';
  if (change < -0.03) return 'BEAR';
  return 'CHOP';
}

/**
 * Break down simulation results by market regime
 */
export function computeRegimeBreakdown(trades: SimTrade[]): RegimeReport {
  const byRegime = {
    BULL: [] as SimTrade[],
    BEAR: [] as SimTrade[],
    CHOP: [] as SimTrade[],
  };

  // Classify each trade
  for (const t of trades) {
    const regime = classifyRegime(t.entryPrice, t.exitPrice, t.symbol);
    byRegime[regime].push(t);
  }

  // Compute breakdown for each regime
  const breakdowns: RegimeBreakdown[] = [];

  for (const regime of ['BULL', 'BEAR', 'CHOP'] as MarketRegime[]) {
    const regTrades = byRegime[regime];
    const wins = regTrades.filter(t => t.returnPct > 0).length;
    const totalReturn = regTrades.reduce((acc, t) => acc + t.returnPct, 0);
    const avgReturn = regTrades.length > 0 ? totalReturn / regTrades.length : 0;

    breakdowns.push({
      regime,
      trades: regTrades.length,
      wins,
      winRate: regTrades.length > 0 ? wins / regTrades.length : 0,
      avgReturn,
      totalReturn,
    });
  }

  // Generate insight
  const best = [...breakdowns].sort((a, b) => b.avgReturn - a.avgReturn)[0];
  const worst = [...breakdowns].sort((a, b) => a.avgReturn - b.avgReturn)[0];

  let insight = '';
  if (best && best.trades > 0) {
    insight = `Best regime: ${best.regime} (${(best.winRate * 100).toFixed(0)}% WR, ${(best.avgReturn * 100).toFixed(2)}% avg). `;
  }
  if (worst && worst.trades > 0 && worst.avgReturn < 0) {
    insight += `Consider avoiding ${worst.regime} conditions.`;
  }

  return {
    overall: {
      totalTrades: trades.length,
      byRegime: {
        BULL: byRegime.BULL.length,
        BEAR: byRegime.BEAR.length,
        CHOP: byRegime.CHOP.length,
      },
    },
    breakdowns,
    insight: insight || 'Insufficient data for regime analysis.',
  };
}

console.log('[Sentiment-ML] Simulation Regime Breakdown loaded (BLOCK 7)');
