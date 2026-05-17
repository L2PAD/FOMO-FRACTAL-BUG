/**
 * Exchange Capital Window Service
 * =================================
 * 
 * EX-S4: Rolling capital metrics from trade records.
 */

import mongoose from 'mongoose';

export interface ExchangeCapitalMetrics {
  windowDays: number;
  asOf: Date;
  nTrades: number;
  winRate: number;
  expectancy: number;
  sharpeLike: number;
  maxDD: number;
  equity: number;
}

export interface ExchangeCapitalScore {
  score: number;     // 0..100
  status: 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';
  reasons: string[];
  metrics: ExchangeCapitalMetrics | null;
}

export class ExchangeCapitalWindowService {
  /**
   * Get rolling capital metrics for a window
   */
  async getRollingWindow(windowDays: number = 30): Promise<ExchangeCapitalMetrics | null> {
    const db = mongoose.connection.db;
    if (!db) return null;

    const since = new Date(Date.now() - windowDays * 24 * 3600_000);

    // Try exchange_trades first
    let trades = await db.collection('exchange_trades')
      .find({ closedAt: { $gte: since }, mode: 'PROD' })
      .sort({ closedAt: 1 })
      .toArray();

    // Fallback to trade_records
    if (!trades.length) {
      trades = await db.collection('trade_records')
        .find({ closedAt: { $gte: since } })
        .sort({ closedAt: 1 })
        .toArray();
    }

    if (!trades.length) return null;

    const pnls = trades.map(t => {
      const p = t.pnlPct ?? t.returnPct ?? t.pnl ?? 0;
      return Number(p);
    }).filter(x => Number.isFinite(x));

    if (!pnls.length) return null;

    const n = pnls.length;
    const wins = pnls.filter(x => x > 0).length;
    const winRate = wins / n;

    const mean = pnls.reduce((a, b) => a + b, 0) / n;
    const variance = pnls.reduce((a, x) => a + (x - mean) * (x - mean), 0) / Math.max(1, n - 1);
    const std = Math.sqrt(variance);
    const sharpeLike = std > 1e-9 ? mean / std : 0;

    // Equity curve and MaxDD
    let eq = 1.0;
    let peak = 1.0;
    let maxDD = 0;
    for (const p of pnls) {
      eq *= (1 + p);
      peak = Math.max(peak, eq);
      const dd = (peak - eq) / peak;
      maxDD = Math.max(maxDD, dd);
    }

    return {
      windowDays,
      asOf: new Date(),
      nTrades: n,
      winRate,
      expectancy: mean,
      sharpeLike,
      maxDD,
      equity: eq,
    };
  }

  /**
   * Compute capital score from metrics
   */
  async computeScore(windowDays: number = 30): Promise<ExchangeCapitalScore> {
    const metrics = await this.getRollingWindow(windowDays);

    if (!metrics) {
      return {
        score: 50,
        status: 'WARN',
        reasons: ['NO_TRADES'],
        metrics: null,
      };
    }

    let score = 100;
    const reasons: string[] = [];

    // Scoring penalties
    if (metrics.maxDD > 0.25) {
      score -= 40;
      reasons.push('MAXDD_GT_25');
    } else if (metrics.maxDD > 0.15) {
      score -= 20;
      reasons.push('MAXDD_GT_15');
    }

    if (metrics.expectancy <= 0) {
      score -= 25;
      reasons.push('EXPECTANCY_LE_0');
    }

    if (metrics.sharpeLike < 0.10) {
      score -= 15;
      reasons.push('SHARPE_LT_0_10');
    } else if (metrics.sharpeLike < 0) {
      score -= 25;
      reasons.push('SHARPE_LT_0');
    }

    if (metrics.nTrades < 25) {
      score -= 15;
      reasons.push('LOW_TRADES');
    }

    score = Math.max(0, Math.min(100, score));

    let status: 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';
    if (score >= 75) status = 'OK';
    else if (score >= 60) status = 'WARN';
    else if (score >= 40) status = 'DEGRADED';
    else status = 'CRITICAL';

    return { score, status, reasons, metrics };
  }
}

// Singleton
let capitalWindowInstance: ExchangeCapitalWindowService | null = null;

export function getExchangeCapitalWindowService(): ExchangeCapitalWindowService {
  if (!capitalWindowInstance) {
    capitalWindowInstance = new ExchangeCapitalWindowService();
  }
  return capitalWindowInstance;
}

console.log('[Exchange-ML] Capital Window Service loaded (EX-S4)');
