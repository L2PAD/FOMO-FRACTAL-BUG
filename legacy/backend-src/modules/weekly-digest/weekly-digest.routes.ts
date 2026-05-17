/**
 * Weekly Digest Routes
 *
 * POST /api/weekly-digest/generate    — Generate a new weekly digest
 * GET  /api/weekly-digest/latest      — Get the most recent digest
 * GET  /api/weekly-digest/history     — Get digest history
 */

import type { FastifyInstance } from 'fastify';
import { digestBuilderService } from './services/digest-builder.service.js';
import { telegramDeliveryOrchestrator } from '../telegram-delivery/services/telegram-delivery-orchestrator.service.js';

export async function weeklyDigestRoutes(app: FastifyInstance): Promise<void> {
  /**
   * POST /api/weekly-digest/generate — Generate new weekly digest
   */
  app.post<{ Body: { from?: string; to?: string } }>('/generate', async (request) => {
    const { from, to } = request.body || {};
    try {
      const digest = await digestBuilderService.generate(from, to);

      // Auto-deliver to Telegram subscribers
      if (digest?.comparison) {
        telegramDeliveryOrchestrator.deliverWeeklyDigest({
          systemState: digest.comparison.systemState,
          metricDeltas: digest.comparison.metricDeltas,
          executionDeltas: digest.comparison.executionDeltas,
          lessons: digest.lessons?.slice(0, 2),
          biggestImprovement: digest.comparison.biggestImprovement,
          biggestDegradation: digest.comparison.biggestDegradation,
        }).catch(() => {});
      }

      return { ok: true, digest };
    } catch (err: any) {
      return { ok: false, error: err?.message || 'Generation failed' };
    }
  });

  /**
   * GET /api/weekly-digest/latest — Most recent digest
   */
  app.get('/latest', async () => {
    const digest = await digestBuilderService.getLatest();
    return { ok: true, digest };
  });

  /**
   * GET /api/weekly-digest/history — Digest history
   */
  app.get<{ Querystring: { limit?: string } }>('/history', async (request) => {
    const limit = parseInt(request.query.limit || '10', 10);
    const digests = await digestBuilderService.getHistory(limit);
    return { ok: true, digests, count: digests.length };
  });
}
