/**
 * Notification Emitters — Public barrel
 * ======================================
 * Thin product-level wrappers around pushRouter.routeEvent().
 * Import from here in signal pipeline / feed aggregator / schedulers.
 *
 *   import { emitConfirmedSignal, emitMissedSignal } from '../core/notifications/emitters';
 *
 * Day-1 policy (env PUSH_ENGINE_ALLOWED_TYPES):
 *   CONFIRMED + MISSED + PERSONAL — no FORMING push
 */

export { emitConfirmedSignal } from './confirmed.emitter.js';
export type { ConfirmedSignalInput } from './confirmed.emitter.js';
export { emitMissedSignal } from './missed.emitter.js';
export type { MissedSignalInput } from './missed.emitter.js';
