/**
 * Sentiment Capital Guard
 * =========================
 * 
 * BLOCK S4: Capital gates for promotion and rollback decisions.
 * 
 * Promotion requires:
 * - CapitalHealth >= 70%
 * - MaxDD <= 15%
 * - Expectancy > 0
 * - SharpeLike >= 0.10
 * 
 * Rollback triggers when:
 * - Expectancy < 0 OR MaxDD > 20% OR SharpeLike < 0
 * - AND CapitalHealth < 50%
 */

import {
  SentimentCapitalWindowService,
  getSentimentCapitalWindowService,
  CapitalWindowMetrics
} from './sentiment_capital_window.service.js';
import { getSentimentReliabilityService } from '../reliability/sentiment-reliability.service.js';
import type { SentWindow } from '../contracts/sentiment.risk.types.js';

// Configuration thresholds
export const CAPITAL_GATE_CONFIG = {
  // Promotion thresholds
  promotion: {
    minTrades: 20,
    maxDD: 0.15,           // 15%
    minExpectancy: 0,      // > 0
    minSharpe: 0.10,
    minCapitalHealth: 0.70, // 70%
    minURI: 0.60,          // 60%
  },
  // Rollback thresholds
  rollback: {
    minTrades: 20,
    maxDD: 0.20,           // 20% triggers
    maxCapitalHealth: 0.50, // must be below 50%
  },
};

export type CapitalGateDecision =
  | { ok: true; metrics: CapitalWindowMetrics; reason?: string }
  | { ok: false; reason: string; metrics?: CapitalWindowMetrics | null };

export interface CapitalGateStatus {
  promotion: CapitalGateDecision;
  rollback: CapitalGateDecision;
  metrics: CapitalWindowMetrics | null;
  capitalHealth: number;
  uriScore: number;
  asOf: string;
}

export class SentimentCapitalGuard {
  private capitalService: SentimentCapitalWindowService;

  constructor() {
    this.capitalService = getSentimentCapitalWindowService();
  }

  /**
   * Check if promotion is allowed based on capital metrics
   */
  async canPromote(sentWindow: SentWindow = '24H'): Promise<CapitalGateDecision> {
    const cfg = CAPITAL_GATE_CONFIG.promotion;

    // Get metrics for ML mode (what we're trying to promote)
    const metrics = await this.capitalService.getRollingWindow(sentWindow, 30, 'ML');

    if (!metrics || metrics.nTrades < cfg.minTrades) {
      return {
        ok: false,
        reason: 'INSUFFICIENT_CAPITAL_DATA',
        metrics,
      };
    }

    // Check MaxDD
    if (metrics.maxDD > cfg.maxDD) {
      return {
        ok: false,
        reason: `MAX_DD_TOO_HIGH:${(metrics.maxDD * 100).toFixed(1)}%>${(cfg.maxDD * 100)}%`,
        metrics,
      };
    }

    // Check Expectancy
    if (metrics.expectancy <= cfg.minExpectancy) {
      return {
        ok: false,
        reason: `EXPECTANCY_NOT_POSITIVE:${(metrics.expectancy * 100).toFixed(2)}%`,
        metrics,
      };
    }

    // Check Sharpe
    if (metrics.sharpeLike < cfg.minSharpe) {
      return {
        ok: false,
        reason: `SHARPE_TOO_LOW:${metrics.sharpeLike.toFixed(2)}<${cfg.minSharpe}`,
        metrics,
      };
    }

    // Check URI and Capital Health
    const reliability = getSentimentReliabilityService();
    const uri = await reliability.computeStatus();

    if (uri.uriScore < cfg.minURI) {
      return {
        ok: false,
        reason: `URI_TOO_LOW:${(uri.uriScore * 100).toFixed(0)}%<${(cfg.minURI * 100)}%`,
        metrics,
      };
    }

    if (uri.components.capitalHealth < cfg.minCapitalHealth) {
      return {
        ok: false,
        reason: `CAPITAL_HEALTH_TOO_LOW:${(uri.components.capitalHealth * 100).toFixed(0)}%<${(cfg.minCapitalHealth * 100)}%`,
        metrics,
      };
    }

    // Check Drift status
    const drift = uri.components.driftHealth;
    if (drift < 0.50) {
      return {
        ok: false,
        reason: `DRIFT_NOT_OK:health=${(drift * 100).toFixed(0)}%`,
        metrics,
      };
    }

    return { ok: true, metrics };
  }

  /**
   * Check if rollback should be triggered based on capital metrics
   */
  async shouldRollback(sentWindow: SentWindow = '24H'): Promise<CapitalGateDecision> {
    const cfg = CAPITAL_GATE_CONFIG.rollback;

    // Get metrics for currently active mode
    const { metrics, mode } = await this.capitalService.getRollingWindowForActive(sentWindow, 30);

    // Only consider rollback if ML is active
    if (mode !== 'ML') {
      return {
        ok: false,
        reason: 'NOT_ML_ACTIVE',
        metrics,
      };
    }

    if (!metrics || metrics.nTrades < cfg.minTrades) {
      return {
        ok: false,
        reason: 'INSUFFICIENT_CAPITAL_DATA',
        metrics,
      };
    }

    // Check if capital is actually bad
    const capitalBad =
      metrics.expectancy < 0 ||
      metrics.maxDD > cfg.maxDD ||
      metrics.sharpeLike < 0;

    if (!capitalBad) {
      return {
        ok: false,
        reason: 'CAPITAL_OK',
        metrics,
      };
    }

    // Capital is bad - now check if CapitalHealth confirms
    const reliability = getSentimentReliabilityService();
    const uri = await reliability.computeStatus();

    if (uri.components.capitalHealth >= cfg.maxCapitalHealth) {
      return {
        ok: false,
        reason: `CAPITAL_HEALTH_STILL_OK:${(uri.components.capitalHealth * 100).toFixed(0)}%>=${(cfg.maxCapitalHealth * 100)}%`,
        metrics,
      };
    }

    // Build detailed reason
    const badReasons: string[] = [];
    if (metrics.expectancy < 0) badReasons.push(`NEG_EXP:${(metrics.expectancy * 100).toFixed(2)}%`);
    if (metrics.maxDD > cfg.maxDD) badReasons.push(`HIGH_DD:${(metrics.maxDD * 100).toFixed(1)}%`);
    if (metrics.sharpeLike < 0) badReasons.push(`NEG_SHARPE:${metrics.sharpeLike.toFixed(2)}`);

    return {
      ok: true,
      metrics,
      reason: `CAPITAL_DEGRADED:${badReasons.join(',')}`,
    };
  }

  /**
   * Get full gate status for admin view
   */
  async getGateStatus(sentWindow: SentWindow = '24H'): Promise<CapitalGateStatus> {
    const [promotion, rollback, reliability] = await Promise.all([
      this.canPromote(sentWindow),
      this.shouldRollback(sentWindow),
      getSentimentReliabilityService().computeStatus(),
    ]);

    const { metrics } = await this.capitalService.getRollingWindowForActive(sentWindow, 30);

    return {
      promotion,
      rollback,
      metrics,
      capitalHealth: reliability.components.capitalHealth,
      uriScore: reliability.uriScore,
      asOf: new Date().toISOString(),
    };
  }
}

// Singleton
let capitalGuardInstance: SentimentCapitalGuard | null = null;

export function getSentimentCapitalGuard(): SentimentCapitalGuard {
  if (!capitalGuardInstance) {
    capitalGuardInstance = new SentimentCapitalGuard();
  }
  return capitalGuardInstance;
}

console.log('[Sentiment-ML] Capital Guard loaded (BLOCK S4)');
