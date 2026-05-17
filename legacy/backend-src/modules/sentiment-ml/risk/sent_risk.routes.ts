/**
 * Sentiment Risk Admin Routes
 * =============================
 * 
 * BLOCK 6: Admin API for Capital & Risk Layer.
 * 
 * Endpoints:
 * - GET /summary — Rolling metrics (equity, MaxDD, Sharpe, WinRate)
 * - GET /equity/series — Equity series for charting
 * - GET /trades — Recent trades list
 * - GET /positions — Active positions
 * - GET /exposure — Current exposure stats
 * - POST /build — Trigger trade builder
 * - POST /finalize-positions — Close expired positions
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getSentimentTradePerfService } from './sent_trade_perf.service.js';
import { getSentTradeBuilderService } from './sent_trade_builder.service.js';
import { getSentRiskGuardService } from './sent_risk_guard.service.js';
import { SentPositionStateModel } from './sent_position_state.model.js';
import { SentTradeModel } from './sent_trade.model.js';
import type { SentWindow, SentMode } from '../contracts/sentiment.risk.types.js';

function parseWindow(v?: string): SentWindow {
  if (v === '7D' || v === '30D' || v === '24H') return v;
  return '24H';
}

function parseMode(v?: string): SentMode {
  return v === 'ML' ? 'ML' : 'RULE';
}

function parseIntSafe(v: any, d: number): number {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : d;
}

async function sentimentRiskRoutes(app: FastifyInstance): Promise<void> {
  const perf = getSentimentTradePerfService();
  const builder = getSentTradeBuilderService();
  const guard = getSentRiskGuardService();

  /**
   * GET /summary — Rolling metrics
   */
  app.get('/summary', async (req: FastifyRequest<{ Querystring: { window?: string; mode?: string; days?: string } }>) => {
    const window = parseWindow(req.query.window);
    const mode = parseMode(req.query.mode);
    const days = parseIntSafe(req.query.days, 365);

    const m = await perf.computeRolling(window, days, mode);

    return {
      ok: true,
      window,
      mode,
      days,
      metrics: {
        trades: m.trades,
        winRate: m.winRate,
        expectancyPct: m.expectancyPct,
        sharpeLike: m.sharpeLike,
        maxDD: m.maxDD,
        equity: m.equity,
      },
      formatted: {
        winRate: `${(m.winRate * 100).toFixed(1)}%`,
        expectancy: `${(m.expectancyPct * 100).toFixed(2)}%`,
        sharpe: m.sharpeLike.toFixed(3),
        maxDD: `${(m.maxDD * 100).toFixed(1)}%`,
        equity: m.equity.toFixed(4),
      },
    };
  });

  /**
   * GET /equity/series — Equity series for charting
   */
  app.get('/equity/series', async (req: FastifyRequest<{ Querystring: { window?: string; mode?: string; days?: string } }>) => {
    const window = parseWindow(req.query.window);
    const mode = parseMode(req.query.mode);
    const days = parseIntSafe(req.query.days, 365);

    const series = await perf.getEquitySeries(window, days, mode);

    return {
      ok: true,
      window,
      mode,
      days,
      points: series.length,
      data: series,
    };
  });

  /**
   * GET /trades — Recent trades
   */
  app.get('/trades', async (req: FastifyRequest<{ Querystring: { window?: string; mode?: string; limit?: string } }>) => {
    const window = parseWindow(req.query.window);
    const mode = parseMode(req.query.mode);
    const limit = Math.min(parseIntSafe(req.query.limit, 200), 500);

    const trades = await perf.getRecentTrades(window, mode, limit);

    return {
      ok: true,
      window,
      mode,
      limit,
      count: trades.length,
      trades: trades.map(t => ({
        symbol: t.symbol,
        direction: t.direction,
        asOf: t.asOf,
        pnlPct: t.pnlPct,
        bias: t.bias,
        closedAt: t.closedAt,
      })),
    };
  });

  /**
   * GET /positions — Active positions
   */
  app.get('/positions', async () => {
    const active = await SentPositionStateModel.find({ status: 'ACTIVE' })
      .sort({ openedAt: -1 })
      .lean();

    return {
      ok: true,
      count: active.length,
      positions: active.map(p => ({
        symbol: p.symbol,
        window: p.window,
        mode: p.mode,
        openedAt: p.openedAt,
        closesAt: p.closesAt,
      })),
    };
  });

  /**
   * GET /exposure — Current exposure stats
   */
  app.get('/exposure', async () => {
    const stats = await guard.getExposureStats();

    return {
      ok: true,
      ...stats,
    };
  });

  /**
   * POST /build — Trigger trade builder
   */
  app.post('/build', async () => {
    const results = await builder.buildAll();

    let totalCreated = 0;
    let totalProcessed = 0;

    for (const r of Object.values(results)) {
      totalCreated += r.created;
      totalProcessed += r.processed;
    }

    return {
      ok: true,
      totalProcessed,
      totalCreated,
      details: results,
    };
  });

  /**
   * POST /finalize-positions — Close expired positions
   */
  app.post('/finalize-positions', async () => {
    const now = new Date();
    
    const toClose = await SentPositionStateModel.find({
      status: 'ACTIVE',
      closesAt: { $lte: now },
    });

    let closed = 0;
    for (const p of toClose) {
      p.status = 'CLOSED';
      p.lastClosedAt = p.closesAt;
      await p.save();
      closed++;
    }

    return {
      ok: true,
      closed,
    };
  });

  /**
   * GET /dashboard — Combined risk dashboard
   */
  app.get('/dashboard', async () => {
    const windows: Record<string, any> = {};

    for (const window of ['24H', '7D', '30D'] as SentWindow[]) {
      const rule = await perf.computeRolling(window, 365, 'RULE');
      const ml = await perf.computeRolling(window, 365, 'ML');

      windows[window] = {
        rule: {
          trades: rule.trades,
          winRate: rule.winRate,
          maxDD: rule.maxDD,
          equity: rule.equity,
        },
        ml: {
          trades: ml.trades,
          winRate: ml.winRate,
          maxDD: ml.maxDD,
          equity: ml.equity,
        },
      };
    }

    const exposure = await guard.getExposureStats();
    const tradeCount = await SentTradeModel.countDocuments();

    return {
      ok: true,
      totalTrades: tradeCount,
      exposure,
      windows,
    };
  });

  console.log('[Sentiment-ML] Risk admin routes registered (BLOCK 6)');
}

// Export wrapped in fastify-plugin
export default fp(sentimentRiskRoutes, {
  name: 'sentiment-risk-routes',
  fastify: '4.x',
});

export { sentimentRiskRoutes };
