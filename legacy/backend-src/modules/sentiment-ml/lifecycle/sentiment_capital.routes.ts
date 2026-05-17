/**
 * Sentiment Capital Admin Routes
 * ================================
 * 
 * BLOCK S4: Admin API for capital metrics and lifecycle gates.
 * 
 * Endpoints:
 * - GET /window — get rolling capital metrics
 * - GET /gates — get promotion/rollback gate status
 * - GET /comparison — compare RULE vs ML capital performance
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getSentimentCapitalWindowService } from './sentiment_capital_window.service.js';
import { getSentimentCapitalGuard, CAPITAL_GATE_CONFIG } from './sentiment_capital_guard.js';

async function sentimentCapitalRoutes(app: FastifyInstance): Promise<void> {
  const capitalSvc = getSentimentCapitalWindowService();
  const capitalGuard = getSentimentCapitalGuard();

  /**
   * GET /window — Get rolling capital metrics
   */
  app.get('/window', async (req: FastifyRequest<{
    Querystring: { window?: string; days?: string; mode?: string }
  }>) => {
    const sentWindow = (req.query.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    const days = parseInt(req.query.days || '30', 10);
    const mode = (req.query.mode?.toUpperCase() || 'RULE') as 'RULE' | 'ML';

    const metrics = await capitalSvc.getRollingWindow(sentWindow, days, mode);

    if (!metrics) {
      return {
        ok: true,
        hasData: false,
        message: 'No trades in rolling window',
        params: { sentWindow, days, mode },
      };
    }

    return {
      ok: true,
      hasData: true,
      params: { sentWindow, days, mode },
      metrics: {
        nTrades: metrics.nTrades,
        expectancy: `${(metrics.expectancy * 100).toFixed(2)}%`,
        expectancyRaw: metrics.expectancy,
        sharpeLike: metrics.sharpeLike.toFixed(3),
        maxDD: `${(metrics.maxDD * 100).toFixed(1)}%`,
        maxDDRaw: metrics.maxDD,
        winRate: `${(metrics.winRate * 100).toFixed(1)}%`,
        winRateRaw: metrics.winRate,
        equity: metrics.equity.toFixed(4),
        asOf: metrics.asOf.toISOString(),
      },
    };
  });

  /**
   * GET /gates — Get capital gate status for promotion/rollback
   */
  app.get('/gates', async (req: FastifyRequest<{
    Querystring: { window?: string }
  }>) => {
    const sentWindow = (req.query.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';

    const status = await capitalGuard.getGateStatus(sentWindow);

    return {
      ok: true,
      sentWindow,
      config: CAPITAL_GATE_CONFIG,
      promotion: {
        allowed: status.promotion.ok,
        reason: status.promotion.ok ? undefined : status.promotion.reason,
      },
      rollback: {
        triggered: status.rollback.ok,
        reason: status.rollback.reason,
      },
      health: {
        capitalHealth: `${(status.capitalHealth * 100).toFixed(0)}%`,
        uri: `${(status.uriScore * 100).toFixed(0)}%`,
      },
      metrics: status.metrics ? {
        nTrades: status.metrics.nTrades,
        expectancy: `${(status.metrics.expectancy * 100).toFixed(2)}%`,
        sharpeLike: status.metrics.sharpeLike.toFixed(3),
        maxDD: `${(status.metrics.maxDD * 100).toFixed(1)}%`,
        winRate: `${(status.metrics.winRate * 100).toFixed(1)}%`,
      } : null,
      asOf: status.asOf,
    };
  });

  /**
   * GET /comparison — Compare RULE vs ML capital performance
   */
  app.get('/comparison', async (req: FastifyRequest<{
    Querystring: { window?: string; days?: string }
  }>) => {
    const sentWindow = (req.query.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    const days = parseInt(req.query.days || '30', 10);

    const comparison = await capitalSvc.getComparison(sentWindow, days);

    const formatMetrics = (m: any) => m ? {
      nTrades: m.nTrades,
      expectancy: `${(m.expectancy * 100).toFixed(2)}%`,
      sharpeLike: m.sharpeLike.toFixed(3),
      maxDD: `${(m.maxDD * 100).toFixed(1)}%`,
      winRate: `${(m.winRate * 100).toFixed(1)}%`,
      equity: m.equity.toFixed(4),
    } : null;

    return {
      ok: true,
      params: { sentWindow, days },
      rule: formatMetrics(comparison.rule),
      ml: formatMetrics(comparison.ml),
      delta: comparison.rule && comparison.ml ? {
        expectancy: `${((comparison.ml.expectancy - comparison.rule.expectancy) * 100).toFixed(2)}%`,
        sharpe: (comparison.ml.sharpeLike - comparison.rule.sharpeLike).toFixed(3),
        maxDD: `${((comparison.ml.maxDD - comparison.rule.maxDD) * 100).toFixed(1)}%`,
      } : null,
    };
  });

  /**
   * GET /config — Get capital gate configuration
   */
  app.get('/config', async () => {
    return {
      ok: true,
      config: {
        promotion: {
          minTrades: CAPITAL_GATE_CONFIG.promotion.minTrades,
          maxDD: `${(CAPITAL_GATE_CONFIG.promotion.maxDD * 100)}%`,
          minExpectancy: `>${(CAPITAL_GATE_CONFIG.promotion.minExpectancy * 100)}%`,
          minSharpe: CAPITAL_GATE_CONFIG.promotion.minSharpe,
          minCapitalHealth: `${(CAPITAL_GATE_CONFIG.promotion.minCapitalHealth * 100)}%`,
          minURI: `${(CAPITAL_GATE_CONFIG.promotion.minURI * 100)}%`,
        },
        rollback: {
          minTrades: CAPITAL_GATE_CONFIG.rollback.minTrades,
          maxDD: `>${(CAPITAL_GATE_CONFIG.rollback.maxDD * 100)}%`,
          maxCapitalHealth: `<${(CAPITAL_GATE_CONFIG.rollback.maxCapitalHealth * 100)}%`,
        },
      },
      description: {
        promotion: 'All conditions must be met for ML promotion',
        rollback: 'Capital degradation triggers automatic rollback to RULE',
      },
    };
  });
}

export default fp(sentimentCapitalRoutes, {
  name: 'sentiment-capital-routes',
  fastify: '4.x',
});

export { sentimentCapitalRoutes };
