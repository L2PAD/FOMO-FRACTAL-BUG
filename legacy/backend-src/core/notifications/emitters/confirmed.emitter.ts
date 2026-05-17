/**
 * Confirmed Signal Emitter
 * =========================
 * Product-level wrapper around pushRouter.routeEvent for CONFIRMED pushes.
 *
 * Call from signal pipeline / feed aggregator whenever a signal graduates
 * to stage === 'CONFIRMED'. Router handles dedupe (5-min TTL), fanout,
 * rules (cooldown 4h, daily_cap 2), and Telegram delivery.
 *
 * ONLY CONFIRMED events emit here — FORMING is suppressed at router level
 * (env PUSH_ENGINE_ALLOWED_TYPES) to avoid noise.
 */

import { pushRouter } from '../push-router.service.js';
import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

export interface ConfirmedSignalInput {
  id: string | number;                  // stable signal / cluster id
  asset: string;                        // 'BTC', 'ETH', ...
  stage?: string;                       // if given, must be 'CONFIRMED' to emit
  sourcesCount?: number;                // real aligned sources (for copy)
  minutesOld?: number;                  // time since first detection
  direction?: 'bullish' | 'bearish' | 'neutral' | string;
  velocity?: number;                    // >1.5 → "narrative accelerating"
  alpha?: number;                       // 0..1 confidence (default 0.7 for CONFIRMED)
  watchersCount?: number;               // real "N people watching" (if we have live count)
  reason?: string;
  deepLink?: string;
}

/**
 * Emit a CONFIRMED push for a signal. Safe to call repeatedly — router dedupes
 * identical (source,asset,stage,type,id) within PUSH_ROUTER_DEDUPE_MS (5 min).
 *
 * Returns the RouteResult so callers can log/observe. Never throws — any
 * transport error is captured in the result.sendFailures counter.
 */
export async function emitConfirmedSignal(input: ConfirmedSignalInput) {
  // Gate: only fire on CONFIRMED stage (callers can skip the gate themselves)
  if (input.stage && String(input.stage).toUpperCase() !== 'CONFIRMED') {
    return { eventId: `confirmed_${input.asset}_${input.id}`, skipped: 'not_confirmed' };
  }

  const event: UnifiedEvent = {
    id: `confirmed_${input.asset}_${input.id}`,
    category: 'retention',
    source: 'fomo',
    type: 'CONFIRMED',
    asset: input.asset,
    stage: 'CONFIRMED',
    alpha: typeof input.alpha === 'number' ? input.alpha : 0.7,
    reason: input.reason,
    deepLink: input.deepLink,
    timestamp: Date.now(),
    meta: {
      sourcesCount: input.sourcesCount ?? 5,
      minutesOld: input.minutesOld ?? 5,
      direction: input.direction ?? 'neutral',
      velocity: input.velocity ?? 1.2,
      ...(typeof input.watchersCount === 'number' ? { watchersCount: input.watchersCount } : {}),
    },
  };

  return pushRouter.routeEvent(event);
}
