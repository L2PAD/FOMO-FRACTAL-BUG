/**
 * Push Engine — Module Entry
 * ==========================
 * Wires up admin routes and exposes start/stop for the scheduler.
 */

import type { FastifyInstance } from 'fastify';

export async function registerPushEngineModule(app: FastifyInstance): Promise<void> {
  const { registerPushAdminRoutes } = await import('./push_admin.routes.js');
  await registerPushAdminRoutes(app);
  console.log('[PushEngine] Admin routes registered');
}

export { startPushScheduler, stopPushScheduler, runCycleOnce } from './push_scheduler.js';
export { PushQueueModel, PushLogModel, PushSubscriberModel, PushStateModel } from './push_state.repository.js';
