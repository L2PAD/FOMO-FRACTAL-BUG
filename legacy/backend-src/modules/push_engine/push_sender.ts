/**
 * Push Sender (legacy compatibility stub)
 * =======================================
 * Since v2 (Unified Router), delivery is performed by
 * `core/notifications/push-router.service.ts`. This file is kept as a thin
 * shim so any external imports still resolve, but it no longer mutates state.
 */

export const PUSH_ENGINE_CHANNEL = (process.env.PUSH_ENGINE_CHANNEL || 'mock').toLowerCase() as 'mock' | 'telegram';

/**
 * @deprecated Use pushRouter.routeEvent() from core/notifications/push-router.service
 */
export async function sendPush(): Promise<void> {
  // no-op: router now handles everything
  return;
}

/**
 * @deprecated Flush is no longer needed — router delivers synchronously per event.
 */
export async function flushPending(): Promise<number> {
  return 0;
}
