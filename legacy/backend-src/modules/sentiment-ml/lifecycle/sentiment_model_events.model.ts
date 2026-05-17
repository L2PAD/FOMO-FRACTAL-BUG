/**
 * Sentiment Model Events (Audit Trail)
 * =====================================
 * 
 * BLOCK 5: Tracks all lifecycle events for audit.
 * 
 * Events:
 * - TRAINED: New model trained
 * - SHADOW_SET: Shadow model assigned
 * - PROMOTED: Shadow promoted to active
 * - ROLLED_BACK: Active rolled back to RULE
 * - KILL_SWITCH_ON/OFF: Emergency controls
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import { SentimentWindow } from '../contracts/sentiment-ml.types.js';

export type SentimentModelEventType =
  | 'TRAINED'
  | 'SHADOW_SET'
  | 'PROMOTED'
  | 'ROLLED_BACK'
  | 'KILL_SWITCH_ON'
  | 'KILL_SWITCH_OFF'
  | 'PROMOTION_LOCK_ON'
  | 'PROMOTION_LOCK_OFF';

export interface SentimentModelEventDoc extends Document {
  type: SentimentModelEventType;
  window?: SentimentWindow;
  modelId?: string;
  prevModelId?: string;
  payload?: Record<string, any>;
  createdAt: Date;
}

const COLLECTION_NAME = 'sentiment_model_events';
const MODEL_NAME = 'SentimentModelEvent';

const SentimentModelEventSchema = new Schema({
  type: { type: String, required: true },
  window: { type: String, enum: ['24H', '7D', '30D'] },
  modelId: { type: String },
  prevModelId: { type: String },
  payload: { type: Schema.Types.Mixed },
}, { 
  collection: COLLECTION_NAME,
  timestamps: true,
});

// Indexes
SentimentModelEventSchema.index({ type: 1, createdAt: -1 });
SentimentModelEventSchema.index({ window: 1, createdAt: -1 });

// Safe model getter
function getSentimentModelEventModel(): Model<SentimentModelEventDoc> {
  if (mongoose.models[MODEL_NAME]) {
    delete mongoose.models[MODEL_NAME];
    delete mongoose.connection.models[MODEL_NAME];
  }
  return mongoose.model<SentimentModelEventDoc>(MODEL_NAME, SentimentModelEventSchema);
}

export const SentimentModelEventModel = getSentimentModelEventModel();

console.log('[Sentiment-ML] Model Events schema loaded (BLOCK 5 Lifecycle)');
