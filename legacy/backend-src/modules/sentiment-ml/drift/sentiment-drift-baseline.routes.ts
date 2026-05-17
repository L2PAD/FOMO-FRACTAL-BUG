/**
 * Sentiment Drift Baseline Routes
 * =================================
 * 
 * BLOCK S2: Admin API for baseline versioning.
 * 
 * Endpoints:
 * - GET /latest — get latest baseline
 * - GET /history — list baseline versions
 * - POST /create — create new baseline (if gates allow)
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getSentimentDriftBaselineService } from './sentiment-drift-baseline.service.js';
import { BASELINE_GATES } from './sentiment-drift-baseline.types.js';

async function sentimentDriftBaselineRoutes(app: FastifyInstance): Promise<void> {
  const baselineSvc = getSentimentDriftBaselineService();

  /**
   * GET /latest — Get latest baseline for window
   */
  app.get('/latest', async (req: FastifyRequest<{
    Querystring: { window?: string }
  }>) => {
    const window = (req.query.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    const latest = await baselineSvc.getLatestBaseline(window);

    if (!latest) {
      return {
        ok: false,
        code: 'NO_BASELINE',
        message: 'No baseline exists yet',
        window,
      };
    }

    return {
      ok: true,
      baseline: {
        window: latest.window,
        version: latest.version,
        createdAt: latest.createdAt,
        sampleCount: latest.sampleCount,
        reason: latest.reason,
        notes: latest.notes,
        featureCount: Object.keys(latest.featureDistributions || {}).length,
        uriAtCreation: {
          score: `${(latest.uriAtCreation.score * 100).toFixed(0)}%`,
          status: latest.uriAtCreation.status,
          reasons: latest.uriAtCreation.reasons,
        },
      },
    };
  });

  /**
   * GET /history — List baseline versions
   */
  app.get('/history', async (req: FastifyRequest<{
    Querystring: { window?: string; limit?: string }
  }>) => {
    const window = (req.query.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    const limit = parseInt(req.query.limit || '20', 10);

    const history = await baselineSvc.listHistory(window, limit);

    return {
      ok: true,
      window,
      count: history.length,
      history: history.map(b => ({
        ...b,
        uriAtCreation: {
          ...b.uriAtCreation,
          scoreFormatted: `${(b.uriAtCreation.score * 100).toFixed(0)}%`,
        },
      })),
    };
  });

  /**
   * POST /create — Create new baseline
   */
  app.post('/create', async (req: FastifyRequest<{
    Body: { window?: string; reason?: string; notes?: string }
  }>, reply) => {
    const body = req.body || {};
    const window = (body.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    const reason = (body.reason?.toUpperCase() || 'MANUAL') as 'AUTO' | 'MANUAL';
    const notes = body.notes;

    const result = await baselineSvc.createBaselineIfAllowed(window, reason, notes);

    if (!result.ok) {
      const statusCode = result.code === 'GATE_BLOCKED' ? 409 : 400;
      return reply.code(statusCode).send(result);
    }

    return result;
  });

  /**
   * GET /gates — Get current gate configuration
   */
  app.get('/gates', async () => {
    return {
      ok: true,
      gates: {
        uriMinOk: `${BASELINE_GATES.uriMinOk * 100}%`,
        uriMinFloor: `${BASELINE_GATES.uriMinFloor * 100}%`,
        dataHealthMin: `${BASELINE_GATES.dataHealthMin * 100}%`,
        capitalHealthMin: `${BASELINE_GATES.capitalHealthMin * 100}%`,
        calibrationHealthMin: `${BASELINE_GATES.calibrationHealthMin * 100}%`,
        minSamples: BASELINE_GATES.minSamples,
        cooldownDays: BASELINE_GATES.cooldownDays,
      },
      description: {
        AUTO: 'Requires URI >= 75% and all health components >= thresholds',
        MANUAL: 'Requires URI >= 60% (hard floor to prevent pinning garbage)',
      },
    };
  });
}

export default fp(sentimentDriftBaselineRoutes, {
  name: 'sentiment-drift-baseline-routes',
  fastify: '4.x',
});

export { sentimentDriftBaselineRoutes };
