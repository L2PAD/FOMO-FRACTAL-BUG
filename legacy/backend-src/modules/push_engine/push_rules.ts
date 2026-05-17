/**
 * Push Rules — eligibility filters
 * =================================
 * Per-user filtering applied BEFORE enqueuing a push.
 *
 * Rules:
 *   1. Subscriber not muted
 *   2. Cooldown: at least 4 hours since last push to this user
 *   3. Rate limit: <= 3 pushes / 24h (reset rolling)
 *   4. Anti-dup per asset: last pushed asset !== current asset
 *   5. PERSONAL type requires asset ∈ user.recentAssets
 *   6. Broadcast (TENSION) skips per-user asset checks but keeps cooldown
 */

import type { DetectedEvent, PushSubscriber } from './types.js';
import { resolvePriority } from '../../core/notifications/priority.engine.js';

const COOLDOWN_MS = Number(process.env.PUSH_COOLDOWN_MS || 4 * 60 * 60 * 1000);   // 4h
const DAILY_CAP = Number(process.env.PUSH_DAILY_CAP || 3);
const CRITICAL_DAILY_CAP = Number(process.env.PUSH_CRITICAL_DAILY_CAP || 6);      // stricter ceiling for CRITICAL
const RESET_MS = 24 * 60 * 60 * 1000;
const EVENT_ALPHA_MIN = Number(process.env.PUSH_EVENT_ALPHA_MIN || 0.25);

export interface RuleResult {
  allowed: boolean;
  reason?: string;
}

export function resetCounterIfNeeded(sub: PushSubscriber): PushSubscriber {
  const now = Date.now();
  const resetAt = sub.pushCount24hResetAt ? new Date(sub.pushCount24hResetAt).getTime() : 0;
  if (now - resetAt > RESET_MS) {
    return { ...sub, pushCount24h: 0, pushCount24hResetAt: new Date() };
  }
  return sub;
}

export function shouldSendToUser(sub: PushSubscriber | null, event: DetectedEvent): RuleResult {
  if (!sub) return { allowed: false, reason: 'no_subscriber' };
  if (sub.muted) return { allowed: false, reason: 'muted' };

  const fresh = resetCounterIfNeeded(sub);
  // CRITICAL events (LISTING/EXPLOIT/ETF/POLY_MISPRICING/METABRAIN_SHIFT and
  // any other priority >= 90) BYPASS cooldown + same-asset anti-dup.
  // Cooldown is a soft user-comfort rule — real emergencies must not get
  // silently dropped for 4h. Daily-cap still applies (CRITICAL_DAILY_CAP).
  const priority = resolvePriority({ type: event.type as string, meta: (event as any).meta });
  const isCritical = priority >= 90;
  const isMissed = event.type === 'MISSED';

  // MISSED has its own cooldown (6h) and daily cap (2). Dedupe + per-user
  // cooldown are already enforced by missed.emitter.ts; here we just make
  // sure cooldown + anti-dup-by-asset don't double-block it.
  if (isMissed) {
    // daily cap for MISSED is capped at 2 (much tighter than normal DAILY_CAP)
    const missedCount = Number((fresh as any).missedCount24h || 0);
    if (missedCount >= 2) return { allowed: false, reason: 'missed_daily_cap_2' };
    return { allowed: true };
  }

  // 1. Cooldown — skipped for CRITICAL
  if (!isCritical && fresh.lastPushAt) {
    const sinceLast = Date.now() - new Date(fresh.lastPushAt).getTime();
    if (sinceLast < COOLDOWN_MS) {
      return { allowed: false, reason: `cooldown ${Math.round((COOLDOWN_MS - sinceLast) / 60_000)}m` };
    }
  }

  // 2. Daily cap — CRITICAL gets a higher ceiling
  const cap = isCritical ? CRITICAL_DAILY_CAP : DAILY_CAP;
  if (fresh.pushCount24h >= cap) {
    return { allowed: false, reason: `daily_cap=${cap}` };
  }

  // 3. Anti-dup by asset — skipped for CRITICAL (new setup > comfort)
  if (!isCritical && event.asset && fresh.lastPushedAsset === event.asset) {
    return { allowed: false, reason: `same_asset=${event.asset}` };
  }

  // 4. PERSONAL requires asset recency
  if (event.type === 'PERSONAL') {
    if (!event.asset || !fresh.recentAssets.includes(event.asset)) {
      return { allowed: false, reason: 'not_in_recent_assets' };
    }
  }

  return { allowed: true };
}

/**
 * Global event-level sanity gates (applied BEFORE fanout).
 * Returns false if the event itself is noise and should be dropped entirely.
 * NOTE: title check removed — message text is built by pushRouter, not carried on DetectedEvent.
 */
export function isEventEligible(event: DetectedEvent): RuleResult {
  // MISSED / TENSION / PERSONAL / product-signal types don't carry alpha — they're
  // retention/broadcast or evidence-based (sentiment cluster already gated upstream).
  const exempt = new Set([
    'TENSION', 'PERSONAL', 'MISSED',
    'LISTING', 'EXPLOIT', 'ETF', 'REGULATION',
    'POLY_MISPRICING', 'POLY_REPRICING', 'POLY_OVERHEATED', 'POLY_THESIS_WEAKENED',
    'NEWS',
  ]);
  if (event.alpha < EVENT_ALPHA_MIN && !exempt.has(String(event.type))) {
    return { allowed: false, reason: `event_alpha_below_min=${event.alpha.toFixed(2)}` };
  }
  return { allowed: true };
}

export const PUSH_RULES_CONFIG = {
  cooldownMs: COOLDOWN_MS,
  dailyCap: DAILY_CAP,
  resetMs: RESET_MS,
};
