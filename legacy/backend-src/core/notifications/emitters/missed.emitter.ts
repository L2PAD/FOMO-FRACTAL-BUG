/**
 * Missed Signal Emitter (Retention Loop)
 * =======================================
 * Core retention psychology: "you could have earned — but didn’t".
 *
 * Trigger logic (MVP — zero external price oracle):
 *   For each subscriber S:
 *     1. Find OLD pushes delivered to S in the [2h, 24h] window (push_logs).
 *     2. For each such push with an asset A:
 *        - If there is a NEWER push (last 60 min) for the SAME asset A in
 *          `notifications`, it means the move is continuing — this is the
 *          "second chance" window.
 *        - Compute movePct from the NEW event’s meta.movePct if present,
 *          otherwise default to 3% (base threshold).
 *     3. Emit MISSED to S pointing at the NEW signal’s deep link.
 *
 * Hard limits (spec):
 *   - PER-USER COOLDOWN: 6h between MISSED pushes.
 *   - PER-USER DAILY CAP: 2.
 *   - Dedupe: (userId, asset) once per 6h.
 *   - MISSED is PERSONAL — only to users who had prior interaction with that asset.
 *   - MISSED bypasses Circuit Breaker (it’s retention, not noise).
 */

import mongoose from 'mongoose';
import { pushRouter } from '../push-router.service.js';
import type { UnifiedEvent } from '../../../modules/push_engine/types.js';
import { buildMissedMessage } from '../builders/missed-signal.builder.js';

const COOLDOWN_MS = 6 * 60 * 60 * 1000;
const DAILY_CAP = 2;
const RECENT_WINDOW_MS = 60 * 60 * 1000;         // 1h — "new signal forming now"
const OLD_MIN_MS = 2 * 60 * 60 * 1000;           // ≥ 2h since old push (enough regret time)
const OLD_MAX_MS = 24 * 60 * 60 * 1000;          // ≤ 24h (older is stale)
const MIN_MOVE_PCT = 3;

async function alreadyMissedRecently(userId: string, asset: string): Promise<boolean> {
  const db = mongoose.connection.db;
  if (!db) return false;
  const since = new Date(Date.now() - COOLDOWN_MS);
  const doc = await db.collection('missed_state').findOne({
    userId, asset, at: { $gte: since.getTime() },
  } as any);
  return !!doc;
}

async function dailyMissedCount(userId: string): Promise<number> {
  const col = mongoose.connection.db?.collection('push_logs');
  if (!col) return 0;
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000);
  return await col.countDocuments({ userId, type: 'MISSED', ts: { $gte: since } });
}

async function markMissed(userId: string, asset: string) {
  const db = mongoose.connection.db;
  if (!db) return;
  await db.collection('missed_state').updateOne(
    { userId, asset } as any,
    { $set: { userId, asset, at: Date.now() } },
    { upsert: true },
  );
}

/**
 * Find NEW push-router signals (last 60 min) AND for each one find users who
 * received an OLD push for same asset 2-24h ago but haven’t been MISSED yet.
 */
export async function pollMissedSignals(): Promise<{ processed: number; skipped: number }> {
  const db = mongoose.connection.db;
  if (!db) return { processed: 0, skipped: 0 };
  const notifications = db.collection('notifications');
  const pushLogs = db.collection('push_logs');

  const now = Date.now();
  const recentSince = new Date(now - RECENT_WINDOW_MS);

  // New push-router signals with an asset (excluding MISSED itself).
  const newSignals = await notifications.find({
    source: 'push-router',
    createdAt: { $gte: recentSince },
    'data.asset': { $ne: null, $exists: true },
    'data.pushType': {
      $nin: ['MISSED'],
    },
  }).sort({ createdAt: -1 }).limit(50).toArray();

  let processed = 0;
  let skipped = 0;

  for (const sig of newSignals) {
    const asset = sig.data?.asset;
    if (!asset) { skipped++; continue; }

    // Candidate users: received push for SAME asset 2–24h ago.
    const oldFrom = new Date(now - OLD_MAX_MS);
    const oldTo   = new Date(now - OLD_MIN_MS);

    const candidates = await pushLogs.aggregate([
      {
        $match: {
          asset,
          type: { $in: ['CONFIRMED', 'PERSONAL', 'LISTING', 'ETF', 'ACTOR_NARRATIVE_PUSH',
                        'ACTOR_MENTION_SPIKE', 'WHALE_EXCHANGE_INFLOW', 'WHALE_EXCHANGE_OUTFLOW',
                        'METABRAIN_DECISION_SHIFT'] },
          ts: { $gte: oldFrom, $lte: oldTo },
        },
      },
      { $group: { _id: '$userId' } },
      { $limit: 500 },
    ]).toArray();

    for (const c of candidates) {
      const userId = c._id as string;
      if (!userId) { skipped++; continue; }

      if (await alreadyMissedRecently(userId, asset)) { skipped++; continue; }
      if (await dailyMissedCount(userId) >= DAILY_CAP) { skipped++; continue; }

      const movePct = Number(sig.data?.movePct || 0) || MIN_MOVE_PCT;

      const event: UnifiedEvent = {
        id: `missed_${asset}_${userId}_${now}`,
        category: 'retention',
        source: 'missed',
        type: 'MISSED',
        asset,
        stage: 'CONFIRMED',
        alpha: 0.65,
        reason: `missed_loop:${asset}`,
        timestamp: now,
        forUserId: userId,                 // PERSONAL — target exactly one user
        meta: {
          movePct,
          linkedSignalId: String(sig._id),
          deepLink: sig.data?.deepLink,    // point at NEW signal, not old
          startParam: sig.data?.startParam,
          watchersCount: sig.data?.watchersCount || 0,
        },
      };

      try {
        await pushRouter.routeEvent(event);
        await markMissed(userId, asset);
        processed++;
      } catch (err) {
        console.error('[missed-emitter] route failed:', err);
        skipped++;
      }
    }
  }

  return { processed, skipped };
}

export { buildMissedMessage };
