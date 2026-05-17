/**
 * Push Digest — time-based systemic pushes (morning kickstart + evening recap).
 * =============================================================================
 * Fires once per calendar day for each slot, independent of detector cycle.
 * All digests go through pushRouter.routeEvent() (unified flow).
 *
 * Env config:
 *   PUSH_DIGEST_ENABLED=1         (0 to disable)
 *   PUSH_DIGEST_MORNING_HOUR=9    (UTC hour)
 *   PUSH_DIGEST_EVENING_HOUR=19   (UTC hour)
 *   PUSH_DIGEST_TZ_OFFSET_H=0     (shift hours if you want local-time feel)
 *
 * Allowed types must include DIGEST_MORNING / DIGEST_EVENING in
 * PUSH_ENGINE_ALLOWED_TYPES for delivery to fire.
 */

import { newsIntelligencePipeline } from '../news-intelligence/pipeline.service.js';
import { pushRouter } from '../../core/notifications/push-router.service.js';
import { PushStateModel } from './push_state.repository.js';
import type { UnifiedEvent } from './types.js';

const ENABLED = process.env.PUSH_DIGEST_ENABLED !== '0';
const MORNING_HOUR = Number(process.env.PUSH_DIGEST_MORNING_HOUR || 9);
const EVENING_HOUR = Number(process.env.PUSH_DIGEST_EVENING_HOUR || 19);
const TZ_OFFSET_H = Number(process.env.PUSH_DIGEST_TZ_OFFSET_H || 0);

function ymd(d: Date): string {
  // UTC calendar date — stable key for "fired once today"
  return d.toISOString().slice(0, 10);
}

function currentHour(): number {
  const d = new Date(Date.now() + TZ_OFFSET_H * 3600 * 1000);
  return d.getUTCHours();
}

async function alreadyFiredToday(slot: 'morning' | 'evening'): Promise<boolean> {
  const eventId = `digest:${slot}:${ymd(new Date())}`;
  const state = await PushStateModel.findOne({ eventId }).lean();
  return !!(state && state.pushedAt);
}

async function fireMorning(): Promise<void> {
  const eventId = `digest:morning:${ymd(new Date())}`;
  // Pull fresh news, count forming signals (importance >= 50, last 2h)
  const feed = await newsIntelligencePipeline.buildFeed({ limit: 40, hoursBack: 2 });
  const clusters = feed.clusters || [];
  const now = Date.now();
  const forming = clusters.filter((c: any) => {
    const age = (now - new Date(c.lastSeenAt).getTime()) / 60_000;
    return c.importance >= 50 && age < 120;
  });
  const count = forming.length;
  const topAssets = Array.from(new Set(forming.map((c: any) => c.primaryAsset).filter(Boolean))).slice(0, 3);
  const reason = count > 0
    ? `${count} signals forming · ${topAssets.join(' · ') || 'cross-market'}`
    : 'Quiet start — watching for catalysts';

  const event: UnifiedEvent = {
    id: eventId,
    category: 'retention',
    source: 'push_engine',
    type: 'DIGEST_MORNING',
    asset: null,
    stage: 'FORMING',
    alpha: 0.5,
    reason,
    timestamp: Date.now(),
    meta: { slot: 'morning', count, assets: topAssets },
  };
  await pushRouter.routeEvent(event);
}

async function fireEvening(): Promise<void> {
  const eventId = `digest:evening:${ymd(new Date())}`;
  // Recap: confirmed events that happened today
  const feed = await newsIntelligencePipeline.buildFeed({ limit: 60, hoursBack: 12 });
  const clusters = feed.clusters || [];
  const confirmed = clusters.filter((c: any) => c.isBreaking || c.importance >= 75);
  const count = confirmed.length;
  const topAssets = Array.from(new Set(confirmed.map((c: any) => c.primaryAsset).filter(Boolean))).slice(0, 3);
  const reason = count > 0
    ? `${count} signals played out · ${topAssets.join(' · ') || 'cross-market'}`
    : 'Market stayed quiet today — setups brewing for tomorrow';

  const event: UnifiedEvent = {
    id: eventId,
    category: 'retention',
    source: 'push_engine',
    type: 'DIGEST_EVENING',
    asset: null,
    stage: 'CONFIRMED',
    alpha: 0.5,
    reason,
    timestamp: Date.now(),
    meta: { slot: 'evening', count, assets: topAssets },
  };
  await pushRouter.routeEvent(event);
}

/**
 * Called from the main scheduler tick. Cheap — short-circuits early if
 * we're outside the slot window or already fired.
 */
export async function maybeFireDigests(): Promise<void> {
  if (!ENABLED) return;
  const h = currentHour();
  try {
    if (h === MORNING_HOUR && !(await alreadyFiredToday('morning'))) {
      await fireMorning();
      console.log('[PushDigest] morning fired');
    }
    if (h === EVENING_HOUR && !(await alreadyFiredToday('evening'))) {
      await fireEvening();
      console.log('[PushDigest] evening fired');
    }
  } catch (e) {
    console.error('[PushDigest] error:', e);
  }
}

/** Admin force-fire (for self-test) */
export async function forceFireDigest(slot: 'morning' | 'evening'): Promise<UnifiedEvent | null> {
  if (slot === 'morning') { await fireMorning(); return null; }
  if (slot === 'evening') { await fireEvening(); return null; }
  return null;
}
