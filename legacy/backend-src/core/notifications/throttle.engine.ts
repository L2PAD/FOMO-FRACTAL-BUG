/**
 * Anti-Spam Throttle Engine
 * =========================
 * Three layers of protection, applied in order:
 *
 *   1. CRITICAL_OVERRIDE   — priority >= 90 always passes everything.
 *   2. CIRCUIT_BREAKER     — global rate limit across ALL users.
 *                             If >= MAX_PUSH_10MIN pushes fired system-wide
 *                             in the last 10 min, block everything below
 *                             CRITICAL until the window clears.
 *   3. PER-USER SOFT CAP   — per-user 6h window. If user got >= SOFT_CAP
 *                             pushes in 6h, demote non-CRITICAL pushes to
 *                             in-app-only.
 *
 * Uses push_logs collection for both global & per-user counts.
 */

import mongoose from 'mongoose';
import { resolvePriority } from './priority.engine.js';

const SOFT_WINDOW_MS = 6 * 60 * 60 * 1000;
const SOFT_CAP = Number(process.env.PUSH_SOFT_CAP_6H || 5);
const CRITICAL_OVERRIDE_MIN = Number(process.env.PUSH_CRITICAL_OVERRIDE_MIN || 90);

// Circuit breaker — global guard against source-explosions (bad emitter loop,
// actor spam burst, etc.). Protects entire product, not just one user.
const CIRCUIT_WINDOW_MS = 10 * 60 * 1000;
const MAX_PUSH_10MIN = Number(process.env.PUSH_CIRCUIT_MAX_10MIN || 5);

// In-memory short cache for circuit counts — 5s TTL so we don't hammer Mongo
// on every push. Trades a tiny bit of staleness for latency.
let circuitCache: { count: number; at: number } | null = null;
const CIRCUIT_CACHE_TTL_MS = 5_000;

async function getGlobalPushCount10min(): Promise<number> {
  const now = Date.now();
  if (circuitCache && now - circuitCache.at < CIRCUIT_CACHE_TTL_MS) {
    return circuitCache.count;
  }
  try {
    const col = mongoose.connection.db?.collection('push_logs');
    if (!col) return 0;
    const since = new Date(now - CIRCUIT_WINDOW_MS);
    const count = await col.countDocuments({ ts: { $gte: since } });
    circuitCache = { count, at: now };
    return count;
  } catch {
    return 0;
  }
}

/**
 * Returns { allow, overrideToInApp }:
 *   allow=false           → fully skip push
 *   overrideToInApp=true  → save to in-app notifications but don't send via Telegram
 *
 * CRITICAL events (priority >= 90) always pass both circuit breaker & soft cap.
 */
export async function antiSpamCheck(
  userId: string,
  event: { type?: string; meta?: any },
): Promise<{ allow: boolean; overrideToInApp: boolean; priority: number; reason: string }> {
  const priority = resolvePriority(event);
  const eventType = String(event?.type || '').toUpperCase();

  // 0. MISSED bypass — retention, not noise.
  //    MISSED has its own per-user cooldown (6h) + daily cap (2) enforced
  //    upstream in missed.emitter.ts. It must pass the Circuit Breaker so
  //    retention loop never gets sacrificed to system-wide rate limits.
  if (eventType === 'MISSED') {
    return { allow: true, overrideToInApp: false, priority, reason: 'missed_retention_bypass' };
  }

  // 1. CRITICAL short-circuit — listings, exploits, ETFs, metabrain_shift, poly_mispricing
  if (priority >= CRITICAL_OVERRIDE_MIN) {
    return { allow: true, overrideToInApp: false, priority, reason: 'critical_override' };
  }

  // 2. Circuit breaker — system-wide 10min rate limit.
  //    Protects product from source-explosion scenarios. Under load we still
  //    let CRITICAL through (handled above) but demote everything else to
  //    in-app so Telegram doesn't become a firehose.
  try {
    const globalCount = await getGlobalPushCount10min();
    if (globalCount >= MAX_PUSH_10MIN) {
      return {
        allow: true,
        overrideToInApp: true,
        priority,
        reason: `circuit_breaker_${globalCount}/${MAX_PUSH_10MIN}_10min_demoted`,
      };
    }
  } catch { /* fall through */ }

  // 3. Per-user soft cap (6h window).
  try {
    const col = mongoose.connection.db?.collection('push_logs');
    if (!col) return { allow: true, overrideToInApp: false, priority, reason: 'no_db' };
    const since = new Date(Date.now() - SOFT_WINDOW_MS);
    const count = await col.countDocuments({ userId, ts: { $gte: since } });
    if (count >= SOFT_CAP) {
      return {
        allow: true,
        overrideToInApp: true,
        priority,
        reason: `soft_cap_6h_${count}/${SOFT_CAP}_demoted`,
      };
    }
    return { allow: true, overrideToInApp: false, priority, reason: 'ok' };
  } catch {
    return { allow: true, overrideToInApp: false, priority, reason: 'error_fallthrough' };
  }
}

/** Observability — expose circuit state for a future admin panel. */
export async function getThrottleState(): Promise<{
  globalCount10min: number;
  maxAllowed: number;
  isTripped: boolean;
}> {
  const globalCount10min = await getGlobalPushCount10min();
  return {
    globalCount10min,
    maxAllowed: MAX_PUSH_10MIN,
    isTripped: globalCount10min >= MAX_PUSH_10MIN,
  };
}
