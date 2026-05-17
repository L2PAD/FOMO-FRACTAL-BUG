/**
 * Sentiment Drift Stabilizer Routes
 * ===================================
 * 
 * BLOCK S3: Admin API for drift stabilization testing.
 * 
 * Endpoints:
 * - GET /status — get current drift stabilizer state
 * - POST /run — manually run drift stabilizer with PSI payload (for testing)
 * - POST /reset — reset streaks (for testing)
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getSentimentDriftStabilizer, DriftRunInput } from './sentiment-drift-stabilizer.service.js';

async function sentimentDriftStabilizerRoutes(app: FastifyInstance): Promise<void> {
  const stabilizerSvc = getSentimentDriftStabilizer();

  /**
   * GET /status — Get current state for window
   */
  app.get('/status', async (req: FastifyRequest<{
    Querystring: { window?: string }
  }>) => {
    const window = (req.query.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    const state = await stabilizerSvc.getState(window);

    if (!state) {
      return {
        ok: true,
        window,
        initialized: false,
        message: 'No state yet - run drift stabilizer first',
      };
    }

    return {
      ok: true,
      window,
      initialized: true,
      rawStatus: state.rawStatus,
      emaStatus: state.emaStatus,
      stabilizedStatus: state.stabilizedStatus,
      streaks: state.streaks,
      psiEmaByFeature: state.psiEmaByFeature,
      actions: state.actions,
      baselineAge: state.baselineAge,
    };
  });

  /**
   * POST /run — Manually run drift stabilizer with PSI payload
   * 
   * Body:
   * {
   *   "window": "24H" | "7D" | "30D",
   *   "psiByFeature": { "feature1": 0.12, "feature2": 0.35, ... }
   * }
   */
  app.post('/run', async (req: FastifyRequest<{
    Body: {
      window?: string;
      psiByFeature: Record<string, number>;
      baselineVersion?: number;
    }
  }>, reply) => {
    const body = req.body || {};
    
    if (!body.psiByFeature || typeof body.psiByFeature !== 'object') {
      return reply.code(400).send({
        ok: false,
        code: 'INVALID_PAYLOAD',
        message: 'psiByFeature is required and must be an object with feature PSI values',
      });
    }

    const window = (body.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    
    const input: DriftRunInput = {
      window,
      psiByFeature: body.psiByFeature,
      baselineVersion: body.baselineVersion ?? null,
    };

    const result = await stabilizerSvc.run(input);

    return {
      ok: true,
      window,
      input: {
        psiByFeature: body.psiByFeature,
      },
      result: {
        rawStatus: result.rawStatus,
        emaStatus: result.emaStatus,
        stabilizedStatus: result.stabilizedStatus,
        psiEmaByFeature: result.psiEmaByFeature,
        streaks: result.streaks,
        actions: result.actions,
        baselineAge: result.baselineAge,
      },
    };
  });

  /**
   * POST /reset — Reset streaks for testing
   */
  app.post('/reset', async (req: FastifyRequest<{
    Body: { window?: string }
  }>) => {
    const body = req.body || {};
    const window = (body.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';

    await stabilizerSvc.resetStreaks(window);

    return {
      ok: true,
      window,
      message: 'Streaks reset to 0',
    };
  });
}

export default fp(sentimentDriftStabilizerRoutes, {
  name: 'sentiment-drift-stabilizer-routes',
  fastify: '4.x',
});

export { sentimentDriftStabilizerRoutes };
