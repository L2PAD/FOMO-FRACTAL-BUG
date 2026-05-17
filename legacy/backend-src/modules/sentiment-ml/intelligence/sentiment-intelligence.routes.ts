/**
 * Sentiment Intelligence Routes
 * ==============================
 * 
 * BLOCK P3: User-facing intelligence endpoint
 * Read-only, no mutations
 */

import type { FastifyInstance } from 'fastify';
import { getSentimentIntelligenceService } from './sentiment-intelligence.service.js';

export async function registerSentimentIntelligenceRoutes(fastify: FastifyInstance): Promise<void> {
  const service = getSentimentIntelligenceService();

  /**
   * GET /api/market/sentiment/intelligence-v1
   * 
   * Returns complete intelligence snapshot
   */
  fastify.get('/api/market/sentiment/intelligence-v1', async (request, reply) => {
    try {
      const result = await service.build();
      return reply.send(result);
    } catch (err: any) {
      console.error('[SentimentIntelligence] Error:', err.message);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  console.log('[Sentiment-Intelligence] Route registered: GET /api/market/sentiment/intelligence-v1');
}
