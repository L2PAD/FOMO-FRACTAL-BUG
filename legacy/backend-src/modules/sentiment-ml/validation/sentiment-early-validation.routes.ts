/**
 * Sentiment Early Validation Routes
 * ===================================
 * 
 * BLOCK 7: Admin API for early validation monitoring.
 * 
 * Endpoints:
 * - GET /summary — Overall validation summary
 * - GET /window — Stats for specific horizon
 * - GET /correlation — Correlation breakdown
 * - GET /strength — Bias strength segmentation
 * 
 * All endpoints are READ-ONLY monitoring.
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { 
  getSentimentEarlyValidationService, 
  ValidationHorizon 
} from './sentiment-early-validation.service.js';

async function sentimentEarlyValidationRoutes(app: FastifyInstance): Promise<void> {
  const service = getSentimentEarlyValidationService();

  /**
   * GET /summary — Full validation summary
   */
  app.get('/summary', async () => {
    const summary = await service.getValidationSummary();
    
    return {
      ok: true,
      data: summary,
    };
  });

  /**
   * GET /window — Stats for specific horizon
   */
  app.get('/window', async (req: FastifyRequest<{ Querystring: { horizon?: string } }>) => {
    const horizon = (req.query.horizon?.toUpperCase() || '7D') as ValidationHorizon;
    
    if (!['24H', '7D', '30D'].includes(horizon)) {
      return {
        ok: false,
        error: 'Invalid horizon. Use 24H, 7D, or 30D.',
      };
    }

    const stats = await service.calculateWindowStats(horizon);

    return {
      ok: true,
      data: stats,
    };
  });

  /**
   * GET /correlation — Correlation breakdown by horizon
   */
  app.get('/correlation', async () => {
    const horizons: ValidationHorizon[] = ['24H', '7D', '30D'];
    
    const results = await Promise.all(
      horizons.map(async h => {
        const stats = await service.calculateWindowStats(h);
        return {
          horizon: h,
          correlation: stats.correlation,
          sampleCount: stats.sampleCount,
          // Color indicator
          indicator: getCorrelationIndicator(stats.correlation),
        };
      })
    );

    return {
      ok: true,
      data: results,
    };
  });

  /**
   * GET /strength — Bias strength segmentation
   */
  app.get('/strength', async (req: FastifyRequest<{ Querystring: { horizon?: string } }>) => {
    const horizon = (req.query.horizon?.toUpperCase() || '7D') as ValidationHorizon;
    
    if (!['24H', '7D', '30D'].includes(horizon)) {
      return {
        ok: false,
        error: 'Invalid horizon. Use 24H, 7D, or 30D.',
      };
    }

    const stats = await service.calculateWindowStats(horizon);

    // Check for gradient
    const buckets = stats.strengthBuckets;
    const lowBucket = buckets.find(b => b.min === 0);
    const highBucket = buckets.find(b => b.min >= 0.6);
    
    const hasGradient = lowBucket && highBucket && highBucket.hitRate > lowBucket.hitRate + 0.05;

    return {
      ok: true,
      horizon,
      sampleCount: stats.sampleCount,
      buckets: stats.strengthBuckets,
      hasGradient,
      gradientStrength: hasGradient 
        ? ((highBucket?.hitRate ?? 0) - (lowBucket?.hitRate ?? 0)).toFixed(2)
        : '0.00',
    };
  });

  console.log('[Sentiment-ML] Early Validation routes registered (BLOCK 7)');
}

/**
 * Get color indicator for correlation value
 */
function getCorrelationIndicator(corr: number): 'gray' | 'yellow' | 'green' {
  const absCorr = Math.abs(corr);
  if (absCorr < 0.05) return 'gray';
  if (absCorr < 0.10) return 'yellow';
  return 'green';
}

// Export wrapped in fastify-plugin
export default fp(sentimentEarlyValidationRoutes, {
  name: 'sentiment-early-validation-routes',
  fastify: '4.x',
});

export { sentimentEarlyValidationRoutes };
