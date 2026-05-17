/**
 * Signal of the Moment — Public Routes
 * =====================================
 *   GET /api/signals/top
 *
 * Returns the single highest-ranked push-router signal across all subscribers
 * for the last 6 hours, hero-style. Consumed by Expo HomeScreen
 * "🔥 Signal of the Moment" block.
 *
 * Not per-user — Signal of the Moment is a global "what matters right now"
 * pulse for every user (same as the news feed front page).
 */

import type { FastifyInstance } from 'fastify';
import { selectTopSignal } from './signal.selector.js';

export async function registerSignalPublicRoutes(app: FastifyInstance): Promise<void> {
  app.get('/top', async () => {
    const top = await selectTopSignal();
    if (!top) {
      return { ok: true, data: null };
    }
    return { ok: true, data: top };
  });

  app.get('/health', async () => ({ ok: true, data: { service: 'signals', ts: new Date().toISOString() } }));
}
