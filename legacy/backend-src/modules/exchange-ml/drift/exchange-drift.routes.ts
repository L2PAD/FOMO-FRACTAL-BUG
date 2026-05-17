/**
 * Exchange Drift Routes
 * =======================
 * 
 * EX-S2 + EX-S3: Admin API for drift baseline and stabilizer.
 * 
 * Endpoints:
 * - GET /baseline/latest — get latest baseline
 * - GET /baseline/history — list baseline versions
 * - POST /baseline/create — create new baseline
 * - GET /stabilizer/status — get current drift state
 * - POST /stabilizer/run — manually run drift stabilizer
 * - POST /stabilizer/reset — reset streaks
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getExchangeDriftBaselineService, EX_BASELINE_GATES } from './exchange-drift-baseline.service.js';
import { getExchangeDriftStabilizerService, DriftRunInput } from './exchange-drift-stabilizer.service.js';

async function exchangeDriftRoutes(app: FastifyInstance): Promise<void> {
  const baselineSvc = getExchangeDriftBaselineService();
  const stabilizerSvc = getExchangeDriftStabilizerService();

  // ═══════════════════════════════════════════════════════════════
  // BASELINE ENDPOINTS (EX-S2)
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /baseline/latest
   */
  app.get('/baseline/latest', async () => {
    const latest = await baselineSvc.getLatestBaseline();

    if (!latest) {
      return {
        ok: false,
        code: 'NO_BASELINE',
        message: 'No baseline exists yet',
      };
    }

    return {
      ok: true,
      baseline: {
        version: latest.version,
        mode: latest.mode,
        createdAt: latest.createdAt,
        uriScore: `${(latest.uriScore * 100).toFixed(0)}%`,
        capitalHealth: `${(latest.capitalHealth * 100).toFixed(0)}%`,
        driftHealth: `${(latest.driftHealth * 100).toFixed(0)}%`,
        snapshot: latest.snapshot,
        notes: latest.notes,
      },
    };
  });

  /**
   * GET /baseline/history
   */
  app.get('/baseline/history', async (req: FastifyRequest<{
    Querystring: { limit?: string }
  }>) => {
    const limit = parseInt(req.query.limit || '20', 10);
    const history = await baselineSvc.listHistory(limit);

    return {
      ok: true,
      count: history.length,
      history: history.map(b => ({
        version: b.version,
        mode: b.mode,
        createdAt: b.createdAt,
        uriScore: `${(b.uriScore * 100).toFixed(0)}%`,
      })),
    };
  });

  /**
   * POST /baseline/create
   */
  app.post('/baseline/create', async (req: FastifyRequest<{
    Body: { mode?: string; notes?: string }
  }>, reply) => {
    const body = req.body || {};
    const mode = (body.mode?.toUpperCase() || 'MANUAL') as 'AUTO' | 'MANUAL';
    const notes = body.notes;

    const result = await baselineSvc.createBaselineIfAllowed(mode, notes);

    if (!result.ok) {
      return reply.code(409).send(result);
    }

    return result;
  });

  /**
   * GET /baseline/gates
   */
  app.get('/baseline/gates', async () => {
    return {
      ok: true,
      gates: {
        auto: {
          uriMin: `${EX_BASELINE_GATES.auto.uriMin * 100}%`,
          capitalHealthMin: `${EX_BASELINE_GATES.auto.capitalHealthMin * 100}%`,
          driftHealthMin: `${EX_BASELINE_GATES.auto.driftHealthMin * 100}%`,
          minTrades: EX_BASELINE_GATES.auto.minTrades,
        },
        manual: {
          uriMin: `${EX_BASELINE_GATES.manual.uriMin * 100}%`,
        },
        cooldownDays: EX_BASELINE_GATES.cooldownDays,
      },
    };
  });

  // ═══════════════════════════════════════════════════════════════
  // STABILIZER ENDPOINTS (EX-S3)
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /stabilizer/status
   */
  app.get('/stabilizer/status', async () => {
    const state = await stabilizerSvc.getState();

    if (!state) {
      return {
        ok: true,
        initialized: false,
        message: 'No state yet - run drift stabilizer first',
      };
    }

    return {
      ok: true,
      initialized: true,
      rawStatus: state.rawStatus,
      emaStatus: state.emaStatus,
      stabilizedStatus: state.stabilizedStatus,
      psiRaw: state.psiRaw.toFixed(3),
      psiEma: state.psiEma.toFixed(3),
      streaks: state.streaks,
      actions: state.actions,
    };
  });

  /**
   * POST /stabilizer/run
   */
  app.post('/stabilizer/run', async (req: FastifyRequest<{
    Body: {
      psiByFeature?: Record<string, number>;
      psiRaw?: number;
      baselineVersion?: number;
    }
  }>, reply) => {
    const body = req.body || {};

    if (!body.psiByFeature && body.psiRaw === undefined) {
      return reply.code(400).send({
        ok: false,
        code: 'INVALID_PAYLOAD',
        message: 'Either psiByFeature or psiRaw is required',
      });
    }

    const input: DriftRunInput = {
      psiByFeature: body.psiByFeature,
      psiRaw: body.psiRaw,
      baselineVersion: body.baselineVersion ?? null,
    };

    const result = await stabilizerSvc.run(input);

    return {
      ok: true,
      result: {
        rawStatus: result.rawStatus,
        emaStatus: result.emaStatus,
        stabilizedStatus: result.stabilizedStatus,
        psiRaw: result.psiRaw.toFixed(3),
        psiEma: result.psiEma.toFixed(3),
        streaks: result.streaks,
        actions: result.actions,
      },
    };
  });

  /**
   * POST /stabilizer/reset
   */
  app.post('/stabilizer/reset', async () => {
    await stabilizerSvc.resetStreaks();

    return {
      ok: true,
      message: 'Streaks reset to 0',
    };
  });
}

export default fp(exchangeDriftRoutes, {
  name: 'exchange-drift-routes',
  fastify: '4.x',
});

export { exchangeDriftRoutes };
