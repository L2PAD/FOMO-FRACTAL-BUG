/**
 * News Control Module — Entry Point
 * ==================================
 * Registers news control routes and initializes the source registry.
 *
 * CONTROL LAYER — no AI, no clustering, no ML impact.
 */

import type { FastifyInstance } from 'fastify';
import { newsSourceRegistryService } from './news-source-registry.service.js';

export async function registerNewsControlModule(app: FastifyInstance): Promise<void> {
  // Initialize source registry with defaults
  await newsSourceRegistryService.ensureDefaults();

  // Register routes
  const { registerNewsControlRoutes } = await import('./news-control.routes.js');
  await registerNewsControlRoutes(app);

  console.log('[NewsControl] Module registered');
}

export { newsSourceRegistryService } from './news-source-registry.service.js';
export { newsHealthService } from './news-health.service.js';
