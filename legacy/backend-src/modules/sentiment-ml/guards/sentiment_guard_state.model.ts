/**
 * Sentiment Guard State Model
 * =============================
 * 
 * BLOCK 10.2: Parser Health Guard state.
 * 
 * Controls system behavior based on data availability:
 * - Kill switch stops all workers
 * - Training disabled prevents auto-retrain
 * - Inference degraded lowers confidence
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export type GuardStatus = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';

export type GuardReason =
  | 'PARSER_DOWN'
  | 'COOKIES_MISSING'
  | 'ZERO_INGEST'
  | 'HIGH_ERROR_RATE'
  | 'STALE_DATA'
  | 'LOW_VOLUME'
  | 'MANUAL_KILL'
  | 'DRIFT_CRITICAL';

export interface GuardStateDoc extends Document {
  key: string;
  status: GuardStatus;
  reasons: GuardReason[];
  details: Record<string, any>;
  isKillSwitchOn: boolean;
  isTrainingDisabled: boolean;
  isInferenceDegraded: boolean;
  updatedAt: Date;
  createdAt: Date;
}

const GuardStateSchema = new Schema<GuardStateDoc>(
  {
    key: { type: String, required: true, unique: true },
    status: { type: String, required: true, index: true },
    reasons: { type: [String], required: true, default: [] },
    details: { type: Schema.Types.Mixed, required: true, default: {} },
    isKillSwitchOn: { type: Boolean, required: true, default: false },
    isTrainingDisabled: { type: Boolean, required: true, default: false },
    isInferenceDegraded: { type: Boolean, required: true, default: false },
  },
  { timestamps: true }
);

export const SentimentGuardStateModel: Model<GuardStateDoc> =
  (mongoose.models.SentimentGuardState as Model<GuardStateDoc>) ||
  mongoose.model<GuardStateDoc>(
    'SentimentGuardState',
    GuardStateSchema,
    'sentiment_guards_state'
  );

console.log('[Sentiment-ML] Guard State Model loaded (BLOCK 10.2)');
