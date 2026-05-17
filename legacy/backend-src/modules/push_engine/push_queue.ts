/**
 * Push Queue
 * ==========
 * Enqueue events into Mongo push_queue. Enrich with reason/alpha/asset so we
 * can later do growth analytics (which reasons perform).
 */

import { PushQueueModel, PushSubscriberModel } from './push_state.repository.js';
import type { DetectedEvent, PushQueueItem } from './types.js';

export async function enqueuePush(
  userId: string | null,
  event: DetectedEvent,
): Promise<PushQueueItem> {
  const item: PushQueueItem = {
    userId,
    eventId: event.eventId,
    type: event.type,
    asset: event.asset,
    stage: event.stage,
    alpha: event.alpha,
    reason: event.reason,
    title: event.title,
    body: event.body,
    deepLink: event.deepLink,
    status: 'pending',
    createdAt: new Date(),
  };
  const created = await PushQueueModel.create(item);
  return created.toObject();
}

export async function enqueueSkipped(
  userId: string | null,
  event: DetectedEvent,
  skipReason: string,
): Promise<void> {
  await PushQueueModel.create({
    userId,
    eventId: event.eventId,
    type: event.type,
    asset: event.asset,
    stage: event.stage,
    alpha: event.alpha,
    reason: event.reason,
    title: event.title,
    body: event.body,
    deepLink: event.deepLink,
    status: 'skipped',
    skipReason,
    createdAt: new Date(),
  });
}

export async function markQueueItemSent(
  queueItemId: any,
  channel: 'mock' | 'telegram' | 'expo',
): Promise<void> {
  await PushQueueModel.updateOne(
    { _id: queueItemId },
    { $set: { status: 'sent', sentAt: new Date(), channel } },
  );
}

export async function fetchPendingBatch(limit = 50): Promise<PushQueueItem[]> {
  return PushQueueModel.find({ status: 'pending' })
    .sort({ createdAt: 1 })
    .limit(limit)
    .lean<PushQueueItem[]>()
    .exec();
}

export async function bumpUserCounters(userId: string, asset: string | null): Promise<void> {
  await PushSubscriberModel.updateOne(
    { userId },
    {
      $set: { lastPushAt: new Date(), lastPushedAsset: asset },
      $inc: { pushCount24h: 1 },
    },
  );
}
