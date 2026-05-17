/**
 * Engine Backtest Routes — Phase BT
 * ====================================
 * POST /engine/backtest/run   — Run a new backtest
 * GET  /engine/backtest/last  — Get last N results
 */

import type { FastifyInstance } from 'fastify';
import { runBacktest, getLastBacktestRuns } from './engine.backtest.service.js';
import type { BacktestRunRequest, Horizon, BacktestMode } from './contracts.js';

const VALID_HORIZONS = new Set([7, 14, 30, 90]);
const VALID_MODES: BacktestMode[] = ['BUY_ONLY', 'BUY_NEUTRAL'];
const VALID_WINDOWS = new Set(['24h', '7d', '30d']);

export async function engineBacktestRoutes(app: FastifyInstance) {

  app.post('/backtest/run', async (request, reply) => {
    const body = request.body as any;
    if (!body) {
      return reply.code(400).send({ ok: false, error: 'MISSING_BODY' });
    }

    const chainId = Number(body.chainId ?? 1);
    const from = String(body.from ?? '');
    const to = String(body.to ?? '');
    const stepDays = Math.max(1, Math.min(30, Number(body.stepDays ?? 7)));
    const window = String(body.window ?? '7d');
    const topK = Math.max(1, Math.min(50, Number(body.topK ?? 10)));
    const mode = (VALID_MODES.includes(body.mode) ? body.mode : 'BUY_ONLY') as BacktestMode;
    const horizons = (Array.isArray(body.horizons) ? body.horizons : [7, 14, 30])
      .map(Number)
      .filter((h: number) => VALID_HORIZONS.has(h)) as Horizon[];

    if (!from || !to || !from.match(/^\d{4}-\d{2}-\d{2}$/) || !to.match(/^\d{4}-\d{2}-\d{2}$/)) {
      return reply.code(400).send({ ok: false, error: 'INVALID_DATES', message: 'Provide from/to as YYYY-MM-DD' });
    }

    if (!VALID_WINDOWS.has(window)) {
      return reply.code(400).send({ ok: false, error: 'INVALID_WINDOW', message: 'Window must be 24h, 7d, or 30d' });
    }

    if (horizons.length === 0) {
      return reply.code(400).send({ ok: false, error: 'INVALID_HORIZONS', message: 'Provide at least one horizon: 7, 14, 30, 90' });
    }

    const req: BacktestRunRequest = { chainId, from, to, stepDays, window: window as any, topK, mode, horizons };

    try {
      const summary = await runBacktest(req);
      return { ok: true, summary };
    } catch (err) {
      console.error('[Backtest] Run error:', err);
      return reply.code(500).send({
        ok: false,
        error: 'BACKTEST_ERROR',
        message: err instanceof Error ? err.message : 'Internal error',
      });
    }
  });

  app.get('/backtest/last', async (request) => {
    const q = request.query as any;
    const chainId = Number(q.chainId ?? 1);
    const limit = Math.min(Number(q.limit ?? 10), 50);

    const runs = await getLastBacktestRuns(chainId, limit);
    return { ok: true, chainId, runs };
  });

  console.log('[Engine] Backtest routes registered');
}
