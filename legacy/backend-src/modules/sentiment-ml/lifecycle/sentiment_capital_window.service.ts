/**
 * Sentiment Capital Window Service
 * ==================================
 * 
 * BLOCK S4: Provides rolling capital metrics for lifecycle gates.
 * 
 * Single source of truth for capital performance:
 * - expectancy
 * - sharpeLike
 * - maxDD
 * - winRate
 * - nTrades
 */

import { getSentimentTradePerfService, SentimentTradePerfService } from '../risk/sent_trade_perf.service.js';
import type { SentWindow, SentMode } from '../contracts/sentiment.risk.types.js';

export interface CapitalWindowMetrics {
  windowDays: number;
  asOf: Date;
  nTrades: number;
  expectancy: number;    // e.g. 0.0016 -> 0.16%
  sharpeLike: number;    // e.g. 0.10
  maxDD: number;         // 0..1
  winRate: number;       // 0..1
  equity: number;        // final equity value
}

export class SentimentCapitalWindowService {
  private perf: SentimentTradePerfService;

  constructor() {
    this.perf = getSentimentTradePerfService();
  }

  /**
   * Get rolling capital metrics for a window
   */
  async getRollingWindow(
    sentWindow: SentWindow = '24H',
    windowDays: number = 30,
    mode: SentMode = 'RULE'
  ): Promise<CapitalWindowMetrics | null> {
    const rolling = await this.perf.computeRolling(sentWindow, windowDays, mode);

    if (!rolling.trades) {
      return null;
    }

    return {
      windowDays,
      asOf: new Date(),
      nTrades: rolling.trades,
      expectancy: rolling.expectancyPct,
      sharpeLike: rolling.sharpeLike,
      maxDD: rolling.maxDD,
      winRate: rolling.winRate,
      equity: rolling.equity,
    };
  }

  /**
   * Get rolling metrics for the currently active mode
   * (tries ML first, falls back to RULE)
   */
  async getRollingWindowForActive(
    sentWindow: SentWindow = '24H',
    windowDays: number = 30
  ): Promise<{ metrics: CapitalWindowMetrics | null; mode: SentMode }> {
    // Try ML first
    const mlMetrics = await this.getRollingWindow(sentWindow, windowDays, 'ML');
    if (mlMetrics && mlMetrics.nTrades >= 10) {
      return { metrics: mlMetrics, mode: 'ML' };
    }

    // Fallback to RULE
    const ruleMetrics = await this.getRollingWindow(sentWindow, windowDays, 'RULE');
    return { metrics: ruleMetrics, mode: 'RULE' };
  }

  /**
   * Get combined metrics for both modes (for comparison)
   */
  async getComparison(
    sentWindow: SentWindow = '24H',
    windowDays: number = 30
  ): Promise<{
    rule: CapitalWindowMetrics | null;
    ml: CapitalWindowMetrics | null;
  }> {
    const [rule, ml] = await Promise.all([
      this.getRollingWindow(sentWindow, windowDays, 'RULE'),
      this.getRollingWindow(sentWindow, windowDays, 'ML'),
    ]);

    return { rule, ml };
  }
}

// Singleton
let capitalWindowInstance: SentimentCapitalWindowService | null = null;

export function getSentimentCapitalWindowService(): SentimentCapitalWindowService {
  if (!capitalWindowInstance) {
    capitalWindowInstance = new SentimentCapitalWindowService();
  }
  return capitalWindowInstance;
}

console.log('[Sentiment-ML] Capital Window Service loaded (BLOCK S4)');
