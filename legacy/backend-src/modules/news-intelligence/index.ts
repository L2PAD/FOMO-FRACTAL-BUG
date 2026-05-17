/**
 * News Intelligence Module — Entry Point
 * =======================================
 * Registers news intelligence routes.
 *
 * This module processes raw_events into clustered, scored events.
 * STRICTLY SEPARATE from ML pipeline.
 */

import type { FastifyInstance } from 'fastify';
import { sourceQualityService } from './source-quality.service.js';

export async function registerNewsIntelligenceModule(app: FastifyInstance): Promise<void> {
  const { registerNewsIntelligenceRoutes } = await import('./news-intelligence.routes.js');
  await registerNewsIntelligenceRoutes(app);

  // Start source quality scoring
  sourceQualityService.start();
  
  app.addHook('onClose', async () => {
    sourceQualityService.stop();
  });

  console.log('[NewsIntelligence] Module registered with source quality scoring');
}

export { newsIntelligencePipeline } from './pipeline.service.js';
export { newsClusteringService } from './clustering.service.js';
export { newsScoringService } from './scoring.service.js';
export { sourceQualityService } from './source-quality.service.js';
