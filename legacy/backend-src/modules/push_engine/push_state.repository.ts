/**
 * Push State Repository
 * =====================
 * Mongoose models for push engine: state tracking, queue, logs, subscribers.
 */

import mongoose, { Schema, type Model } from 'mongoose';
import type { PushQueueItem, PushLog, PushStateDoc, PushSubscriber } from './types.js';

// ─── push_state ────────────────────────────────────────────────────
const PushStateSchema = new Schema<PushStateDoc>({
  eventId: { type: String, required: true, unique: true, index: true },
  lastStage: { type: String, default: null },
  lastAlpha: { type: Number, default: 0 },
  pushedAt: { type: Date, default: null },
  pushTypesSent: { type: [String], default: [] },
  updatedAt: { type: Date, default: () => new Date() },
}, { collection: 'push_state' });

export const PushStateModel: Model<PushStateDoc> =
  (mongoose.models.PushState as Model<PushStateDoc>) ||
  mongoose.model<PushStateDoc>('PushState', PushStateSchema);

// ─── push_queue ────────────────────────────────────────────────────
const PushQueueSchema = new Schema<PushQueueItem>({
  userId: { type: String, default: null, index: true },
  eventId: { type: String, required: true, index: true },
  type: { type: String, required: true, index: true },
  asset: { type: String, default: null, index: true },
  stage: { type: String, required: true },
  alpha: { type: Number, default: 0 },
  reason: { type: String, default: '' },
  title: { type: String, default: '' },
  body: { type: String, default: '' },
  deepLink: { type: String, default: '' },
  status: { type: String, default: 'pending', index: true },
  skipReason: { type: String, default: null },
  createdAt: { type: Date, default: () => new Date(), index: true },
  sentAt: { type: Date, default: null },
  channel: { type: String, default: null },
}, { collection: 'push_queue' });

export const PushQueueModel: Model<PushQueueItem> =
  (mongoose.models.PushQueue as Model<PushQueueItem>) ||
  mongoose.model<PushQueueItem>('PushQueue', PushQueueSchema);

// ─── push_logs ─────────────────────────────────────────────────────
const PushLogSchema = new Schema<PushLog>({
  userId: { type: String, default: null, index: true },
  eventId: { type: String, required: true, index: true },
  type: { type: String, required: true, index: true },
  asset: { type: String, default: null, index: true },
  title: { type: String, default: '' },
  body: { type: String, default: '' },
  channel: { type: String, default: 'mock' },
  ts: { type: Date, default: () => new Date(), index: true },
}, { collection: 'push_logs' });

export const PushLogModel: Model<PushLog> =
  (mongoose.models.PushLog as Model<PushLog>) ||
  mongoose.model<PushLog>('PushLog', PushLogSchema);

// ─── push_subscribers ──────────────────────────────────────────────
const PushSubscriberSchema = new Schema<PushSubscriber>({
  userId: { type: String, required: true, unique: true, index: true },
  role: { type: String, default: 'user', index: true },
  telegramChatId: { type: String, default: null },
  expoToken: { type: String, default: null },
  recentAssets: { type: [String], default: [] },
  lastPushAt: { type: Date, default: null },
  lastPushedAsset: { type: String, default: null },
  pushCount24h: { type: Number, default: 0 },
  pushCount24hResetAt: { type: Date, default: () => new Date() },
  muted: { type: Boolean, default: false },
  createdAt: { type: Date, default: () => new Date() },
}, { collection: 'push_subscribers' });

export const PushSubscriberModel: Model<PushSubscriber> =
  (mongoose.models.PushSubscriber as Model<PushSubscriber>) ||
  mongoose.model<PushSubscriber>('PushSubscriber', PushSubscriberSchema);

// ─── Repository helpers ────────────────────────────────────────────
export async function ensurePushIndexes(): Promise<void> {
  try {
    await Promise.all([
      PushStateModel.createIndexes(),
      PushQueueModel.createIndexes(),
      PushLogModel.createIndexes(),
      PushSubscriberModel.createIndexes(),
    ]);
  } catch (e) {
    console.error('[PushEngine] ensureIndexes failed', e);
  }
}

export async function getState(eventId: string): Promise<PushStateDoc | null> {
  return PushStateModel.findOne({ eventId }).lean<PushStateDoc>().exec();
}

export async function upsertState(eventId: string, patch: Partial<PushStateDoc>): Promise<void> {
  await PushStateModel.updateOne(
    { eventId },
    { $set: { ...patch, updatedAt: new Date() }, $setOnInsert: { eventId } },
    { upsert: true },
  );
}

export async function markPushTypeSent(eventId: string, type: string, stage: string, alpha: number): Promise<void> {
  await PushStateModel.updateOne(
    { eventId },
    {
      $addToSet: { pushTypesSent: type },
      $set: { lastStage: stage, lastAlpha: alpha, pushedAt: new Date(), updatedAt: new Date() },
      $setOnInsert: { eventId },
    },
    { upsert: true },
  );
}
