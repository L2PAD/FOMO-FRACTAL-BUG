/**
 * Ingestion Module — Entry Point
 * ==============================
 * Registers routes and starts the ingestion scheduler.
 */

import type { FastifyInstance } from 'fastify';
import { ingestionLockService } from './ingestion.lock.service.js';
import { ingestionScheduler } from './ingestion.scheduler.js';

export async function registerIngestionModule(app: FastifyInstance): Promise<void> {
  // Ensure lock indexes
  await ingestionLockService.ensureIndexes();

  // Register admin routes (prefix applied by parent)
  const ingestionRoutes = await import('./ingestion.routes.js');
  await ingestionRoutes.registerIngestionRoutes(app);

  // Start scheduler (auto-ingestion every 5 min)
  const schedulerEnabled = process.env.INGESTION_SCHEDULER_ENABLED !== 'false';
  if (schedulerEnabled) {
    ingestionScheduler.start();
    console.log('[Ingestion] Scheduler auto-started');
  }

  console.log('[Ingestion] Module registered');
}

export { ingestionOrchestratorService } from './ingestion.orchestrator.service.js';
export { ingestionScheduler } from './ingestion.scheduler.js';
export { ingestionMetricsService } from './ingestion.metrics.service.js';
export { RawEventModel } from './models/raw-event.model.js';
export { newsAdapter } from './adapters/news.adapter.js';
export { bridgeTwitterAdapter } from './adapters/bridge-twitter.adapter.js';
export { newsDedupeService } from './dedupe/news-dedupe.service.js';
