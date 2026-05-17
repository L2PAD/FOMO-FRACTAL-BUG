/**
 * Exchange Capital Admin Routes
 * ===============================
 * 
 * EX-S4: Admin API for capital metrics and lifecycle gates.
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getExchangeCapitalWindowService } from './exchange_capital_window.service.js';
import { getExchangeCapitalGuard, EX_CAPITAL_GATE_CONFIG } from './exchange_capital_guard.js';

async function exchangeCapitalRoutes(app: FastifyInstance): Promise<void> {
  const capitalSvc = getExchangeCapitalWindowService();
  const capitalGuard = getExchangeCapitalGuard();

  /**
   * GET /window — Get rolling capital metrics
   */
  app.get('/window', async (req: FastifyRequest<{
    Querystring: { days?: string }
  }>) => {
    const days = parseInt(req.query.days || '30', 10);
    const metrics = await capitalSvc.getRollingWindow(days);

    if (!metrics) {
      return {
        ok: true,
        hasData: false,
        message: 'No trades in rolling window',
        params: { days },
      };
    }

    return {
      ok: true,
      hasData: true,
      params: { days },
      metrics: {
        nTrades: metrics.nTrades,
        expectancy: `${(metrics.expectancy * 100).toFixed(2)}%`,
        sharpeLike: metrics.sharpeLike.toFixed(3),
        maxDD: `${(metrics.maxDD * 100).toFixed(1)}%`,
        winRate: `${(metrics.winRate * 100).toFixed(1)}%`,
        equity: metrics.equity.toFixed(4),
        asOf: metrics.asOf.toISOString(),
      },
    };
  });

  /**
   * GET /score — Get capital score with status
   */
  app.get('/score', async (req: FastifyRequest<{
    Querystring: { days?: string }
  }>) => {
    const days = parseInt(req.query.days || '30', 10);
    const result = await capitalSvc.computeScore(days);

    return {
      ok: true,
      score: result.score,
      status: result.status,
      reasons: result.reasons,
      metrics: result.metrics ? {
        nTrades: result.metrics.nTrades,
        expectancy: `${(result.metrics.expectancy * 100).toFixed(2)}%`,
        sharpeLike: result.metrics.sharpeLike.toFixed(3),
        maxDD: `${(result.metrics.maxDD * 100).toFixed(1)}%`,
      } : null,
    };
  });

  /**
   * GET /gates — Get capital gate status for promotion/rollback
   */
  app.get('/gates', async () => {
    const status = await capitalGuard.getGateStatus();

    return {
      ok: true,
      config: EX_CAPITAL_GATE_CONFIG,
      promotion: {
        allowed: status.promotion.ok,
        reason: status.promotion.ok ? undefined : (status.promotion as any).reason,
      },
      rollback: {
        triggered: status.rollback.ok,
        reason: (status.rollback as any).reason,
      },
      health: {
        capitalScore: status.capitalScore,
        uri: `${(status.uriScore * 100).toFixed(0)}%`,
      },
      metrics: status.metrics ? {
        nTrades: status.metrics.nTrades,
        expectancy: `${(status.metrics.expectancy * 100).toFixed(2)}%`,
        sharpeLike: status.metrics.sharpeLike.toFixed(3),
        maxDD: `${(status.metrics.maxDD * 100).toFixed(1)}%`,
      } : null,
      asOf: status.asOf,
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
          minTrades: EX_CAPITAL_GATE_CONFIG.promotion.minTrades,
          maxDD: `${EX_CAPITAL_GATE_CONFIG.promotion.maxDD * 100}%`,
          minExpectancy: `>${EX_CAPITAL_GATE_CONFIG.promotion.minExpectancy * 100}%`,
          minSharpe: EX_CAPITAL_GATE_CONFIG.promotion.minSharpe,
          minCapitalScore: EX_CAPITAL_GATE_CONFIG.promotion.minCapitalScore,
          minURI: `${EX_CAPITAL_GATE_CONFIG.promotion.minURI * 100}%`,
        },
        rollback: {
          minTrades: EX_CAPITAL_GATE_CONFIG.rollback.minTrades,
          maxDD: `>${EX_CAPITAL_GATE_CONFIG.rollback.maxDD * 100}%`,
          maxCapitalScore: `<${EX_CAPITAL_GATE_CONFIG.rollback.maxCapitalScore}`,
        },
      },
    };
  });
}

export default fp(exchangeCapitalRoutes, {
  name: 'exchange-capital-routes',
  fastify: '4.x',
});

export { exchangeCapitalRoutes };
