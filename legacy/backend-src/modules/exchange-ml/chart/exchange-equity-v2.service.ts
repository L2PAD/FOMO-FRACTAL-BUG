/**
 * Exchange Equity V2 Service
 * ============================
 * 
 * BLOCK E2.2: Mini equity curve for paper performance
 * Symmetric with Sentiment Equity V2
 */

import {
  ExchangeEquityResponse,
  ExchangeEquityPoint,
  ExchangeEquityStats,
} from './exchange-chart-v2.types.js';

export class ExchangeEquityV2Service {
  /**
   * Get equity curve data
   */
  async getEquity(symbol: string, period: string = '90d'): Promise<ExchangeEquityResponse> {
    const days = period === '30d' ? 30 : period === '180d' ? 180 : 90;
    
    // Generate synthetic equity curve (in production, use actual paper trading data)
    const points = this.generateEquityCurve(days);
    const stats = this.calculateStats(points);

    return {
      ok: true,
      symbol,
      period,
      points,
      stats,
    };
  }

  /**
   * Generate equity curve points
   */
  private generateEquityCurve(days: number): ExchangeEquityPoint[] {
    const points: ExchangeEquityPoint[] = [];
    const now = Date.now();
    let equity = 100; // Start at 100

    for (let i = days; i >= 0; i--) {
      const time = new Date(now - i * 86400000).toISOString().split('T')[0];
      
      // Random daily return with slight positive drift
      const dailyReturn = (Math.random() - 0.48) * 0.02; // Slight positive bias
      equity *= (1 + dailyReturn);
      
      points.push({
        time,
        equity: Math.round(equity * 100) / 100,
      });
    }

    return points;
  }

  /**
   * Calculate stats from equity curve
   */
  private calculateStats(points: ExchangeEquityPoint[]): ExchangeEquityStats {
    if (points.length < 2) {
      return { totalReturn: 0, maxDD: 0, sharpe: 0, trades: 0 };
    }

    const startEquity = points[0].equity;
    const endEquity = points[points.length - 1].equity;
    const totalReturn = (endEquity - startEquity) / startEquity;

    // Calculate max drawdown
    let peak = points[0].equity;
    let maxDD = 0;
    for (const p of points) {
      if (p.equity > peak) peak = p.equity;
      const dd = (peak - p.equity) / peak;
      if (dd > maxDD) maxDD = dd;
    }

    // Calculate Sharpe (simplified)
    const returns = points.slice(1).map((p, i) => 
      (p.equity - points[i].equity) / points[i].equity
    );
    const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
    const stdDev = Math.sqrt(
      returns.reduce((a, b) => a + Math.pow(b - avgReturn, 2), 0) / returns.length
    );
    const sharpe = stdDev > 0 ? (avgReturn * 252) / (stdDev * Math.sqrt(252)) : 0;

    // Estimate trades (roughly 1 per day on average)
    const trades = Math.floor(points.length * 0.7);

    return {
      totalReturn: Math.round(totalReturn * 10000) / 100, // As percentage
      maxDD: Math.round(maxDD * 10000) / 100, // As percentage
      sharpe: Math.round(sharpe * 100) / 100,
      trades,
    };
  }
}

// Singleton
let instance: ExchangeEquityV2Service | null = null;

export function getExchangeEquityV2Service(): ExchangeEquityV2Service {
  if (!instance) {
    instance = new ExchangeEquityV2Service();
  }
  return instance;
}
