/**
 * Sentiment Trade Performance Service
 * =====================================
 * 
 * BLOCK 6: Computes equity, MaxDD, Sharpe, WinRate from paper trades.
 */

import { SentTradeModel } from './sent_trade.model.js';
import type { SentWindow, SentMode } from '../contracts/sentiment.risk.types.js';

export interface RollingMetrics {
  trades: number;
  winRate: number;
  expectancyPct: number;
  sharpeLike: number;
  maxDD: number;
  equity: number;
}

export class SentimentTradePerfService {
  /**
   * Compute rolling metrics for a window/mode
   */
  async computeRolling(window: SentWindow, days: number, mode: SentMode): Promise<RollingMetrics> {
    const since = new Date(Date.now() - days * 24 * 3600 * 1000);

    const trades = await SentTradeModel.find({ 
      window, 
      mode, 
      closedAt: { $gte: since } 
    })
      .sort({ closedAt: 1 })
      .lean();

    if (!trades.length) {
      return { 
        trades: 0, 
        winRate: 0, 
        expectancyPct: 0, 
        sharpeLike: 0, 
        maxDD: 0, 
        equity: 1 
      };
    }

    let equity = 1;
    let peak = 1;
    let maxDD = 0;
    const rets: number[] = [];
    let wins = 0;

    for (const t of trades) {
      const r = t.pnlPct;
      rets.push(r);
      if (r > 0) wins++;
      equity *= (1 + r);
      peak = Math.max(peak, equity);
      const dd = (peak - equity) / peak;
      maxDD = Math.max(maxDD, dd);
    }

    const expectancyPct = rets.reduce((a, b) => a + b, 0) / rets.length;
    const mean = expectancyPct;
    const variance = rets.reduce((a, x) => a + (x - mean) * (x - mean), 0) / Math.max(1, rets.length - 1);
    const std = Math.sqrt(variance);
    const sharpeLike = std > 1e-9 ? mean / std : 0;

    return {
      trades: trades.length,
      winRate: wins / trades.length,
      expectancyPct,
      sharpeLike,
      maxDD,
      equity,
    };
  }

  /**
   * Get equity series for charting
   */
  async getEquitySeries(window: SentWindow, days: number, mode: SentMode): Promise<Array<{ t: Date; equity: number }>> {
    const since = new Date(Date.now() - days * 24 * 3600 * 1000);

    const trades = await SentTradeModel.find({ 
      window, 
      mode, 
      closedAt: { $gte: since } 
    })
      .sort({ closedAt: 1 })
      .select({ closedAt: 1, pnlPct: 1 })
      .lean();

    let equity = 1;
    return trades.map(t => {
      equity *= (1 + (t.pnlPct ?? 0));
      return { t: t.closedAt, equity };
    });
  }

  /**
   * Get recent trades
   */
  async getRecentTrades(window: SentWindow, mode: SentMode, limit: number = 200) {
    return SentTradeModel.find({ window, mode })
      .sort({ closedAt: -1 })
      .limit(limit)
      .lean();
  }
}

// Singleton
let perfInstance: SentimentTradePerfService | null = null;

export function getSentimentTradePerfService(): SentimentTradePerfService {
  if (!perfInstance) {
    perfInstance = new SentimentTradePerfService();
  }
  return perfInstance;
}

console.log('[Sentiment-ML] Trade Perf Service loaded (BLOCK 6)');
