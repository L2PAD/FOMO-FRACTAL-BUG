/**
 * Exchange Capital Guard
 * ========================
 * 
 * EX-S4: Capital gates for promotion and rollback decisions.
 * 
 * Promotion gates:
 * - CapitalScore >= 70
 * - MaxDD <= 15%
 * - Expectancy > 0
 * - SharpeLike >= 0.10
 * - URI >= 60%
 * 
 * Rollback triggers:
 * - (Expectancy < 0 OR MaxDD > 20% OR Sharpe < 0) AND CapitalScore < 50
 */

import { getExchangeCapitalWindowService, ExchangeCapitalMetrics } from './exchange_capital_window.service.js';
import { getExchangeReliabilityService } from '../reliability/exchange-reliability.service.js';

export const EX_CAPITAL_GATE_CONFIG = {
  promotion: {
    minTrades: 30,
    maxDD: 0.15,
    minExpectancy: 0,
    minSharpe: 0.10,
    minCapitalScore: 70,
    minURI: 0.60,
  },
  rollback: {
    minTrades: 20,
    maxDD: 0.20,
    maxCapitalScore: 50,
  },
};

export type CapitalGateDecision =
  | { ok: true; metrics: ExchangeCapitalMetrics | null }
  | { ok: false; reason: string; metrics?: ExchangeCapitalMetrics | null };

export interface ExchangeCapitalGateStatus {
  promotion: CapitalGateDecision;
  rollback: CapitalGateDecision;
  metrics: ExchangeCapitalMetrics | null;
  capitalScore: number;
  uriScore: number;
  asOf: string;
}

export class ExchangeCapitalGuard {
  /**
   * Check if promotion is allowed
   */
  async canPromote(): Promise<CapitalGateDecision> {
    const cfg = EX_CAPITAL_GATE_CONFIG.promotion;

    const capitalSvc = getExchangeCapitalWindowService();
    const capitalScore = await capitalSvc.computeScore(30);
    const metrics = capitalScore.metrics;

    if (!metrics || metrics.nTrades < cfg.minTrades) {
      return {
        ok: false,
        reason: `INSUFFICIENT_DATA:${metrics?.nTrades ?? 0}<${cfg.minTrades}`,
        metrics,
      };
    }

    if (capitalScore.score < cfg.minCapitalScore) {
      return {
        ok: false,
        reason: `CAPITAL_SCORE_LOW:${capitalScore.score}<${cfg.minCapitalScore}`,
        metrics,
      };
    }

    if (metrics.maxDD > cfg.maxDD) {
      return {
        ok: false,
        reason: `MAX_DD_HIGH:${(metrics.maxDD * 100).toFixed(1)}%>${cfg.maxDD * 100}%`,
        metrics,
      };
    }

    if (metrics.expectancy <= cfg.minExpectancy) {
      return {
        ok: false,
        reason: `EXPECTANCY_LOW:${(metrics.expectancy * 100).toFixed(2)}%`,
        metrics,
      };
    }

    if (metrics.sharpeLike < cfg.minSharpe) {
      return {
        ok: false,
        reason: `SHARPE_LOW:${metrics.sharpeLike.toFixed(2)}<${cfg.minSharpe}`,
        metrics,
      };
    }

    // Check URI
    const reliability = getExchangeReliabilityService();
    const uri = await reliability.computeStatus();

    if (uri.uriScore < cfg.minURI) {
      return {
        ok: false,
        reason: `URI_LOW:${(uri.uriScore * 100).toFixed(0)}%<${cfg.minURI * 100}%`,
        metrics,
      };
    }

    // Check drift status
    if (uri.components.driftHealth < 0.50) {
      return {
        ok: false,
        reason: `DRIFT_DEGRADED:${(uri.components.driftHealth * 100).toFixed(0)}%`,
        metrics,
      };
    }

    return { ok: true, metrics };
  }

  /**
   * Check if rollback should be triggered
   */
  async shouldRollback(): Promise<CapitalGateDecision> {
    const cfg = EX_CAPITAL_GATE_CONFIG.rollback;

    const capitalSvc = getExchangeCapitalWindowService();
    const capitalScore = await capitalSvc.computeScore(30);
    const metrics = capitalScore.metrics;

    if (!metrics || metrics.nTrades < cfg.minTrades) {
      return {
        ok: false,
        reason: 'INSUFFICIENT_DATA',
        metrics,
      };
    }

    // Check if capital is bad
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

    // Capital is bad - confirm with score
    if (capitalScore.score >= cfg.maxCapitalScore) {
      return {
        ok: false,
        reason: `SCORE_STILL_OK:${capitalScore.score}>=${cfg.maxCapitalScore}`,
        metrics,
      };
    }

    // Build reason
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
   * Check if training should be blocked
   */
  async trainingBlocked(): Promise<CapitalGateDecision> {
    const capitalSvc = getExchangeCapitalWindowService();
    const capitalScore = await capitalSvc.computeScore(30);

    if (capitalScore.score < 50) {
      return {
        ok: true,
        metrics: capitalScore.metrics,
        reason: `CAPITAL_SCORE_LOW:${capitalScore.score}<50`,
      };
    }

    return { ok: false, metrics: capitalScore.metrics };
  }

  /**
   * Get full gate status
   */
  async getGateStatus(): Promise<ExchangeCapitalGateStatus> {
    const capitalSvc = getExchangeCapitalWindowService();
    const capitalScore = await capitalSvc.computeScore(30);

    const reliability = getExchangeReliabilityService();
    const uri = await reliability.computeStatus();

    const [promotion, rollback] = await Promise.all([
      this.canPromote(),
      this.shouldRollback(),
    ]);

    return {
      promotion,
      rollback,
      metrics: capitalScore.metrics,
      capitalScore: capitalScore.score,
      uriScore: uri.uriScore,
      asOf: new Date().toISOString(),
    };
  }
}

// Singleton
let capitalGuardInstance: ExchangeCapitalGuard | null = null;

export function getExchangeCapitalGuard(): ExchangeCapitalGuard {
  if (!capitalGuardInstance) {
    capitalGuardInstance = new ExchangeCapitalGuard();
  }
  return capitalGuardInstance;
}

console.log('[Exchange-ML] Capital Guard loaded (EX-S4)');
