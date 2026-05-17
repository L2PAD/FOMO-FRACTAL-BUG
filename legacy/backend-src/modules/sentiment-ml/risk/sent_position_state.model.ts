/**
 * Sentiment Position State Model
 * ================================
 * 
 * BLOCK 6C: Tracks active positions for concurrency/exposure guards.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import type { SentWindow, SentMode } from '../contracts/sentiment.risk.types.js';

export interface SentPositionStateDoc extends Document {
  symbol: string;
  window: SentWindow;
  mode: SentMode;

  openedAt: Date;
  closesAt: Date;

  lastClosedAt?: Date;
  tradeAsOf: Date;

  status: 'ACTIVE' | 'CLOSED';
  
  createdAt: Date;
  updatedAt: Date;
}

const COLLECTION_NAME = 'sent_position_states';
const MODEL_NAME = 'SentPositionState';

const SentPositionStateSchema = new Schema<SentPositionStateDoc>({
  symbol: { type: String, required: true, index: true },
  window: { type: String, required: true, index: true, enum: ['24H', '7D', '30D'] },
  mode: { type: String, required: true, index: true, enum: ['RULE', 'ML'] },

  openedAt: { type: Date, required: true },
  closesAt: { type: Date, required: true, index: true },

  lastClosedAt: { type: Date },
  tradeAsOf: { type: Date, required: true },

  status: { type: String, required: true, index: true, enum: ['ACTIVE', 'CLOSED'] },
}, { 
  collection: COLLECTION_NAME,
  timestamps: true,
});

// Only one ACTIVE per (symbol, window, mode)
SentPositionStateSchema.index(
  { symbol: 1, window: 1, mode: 1, status: 1 },
  { unique: true, partialFilterExpression: { status: 'ACTIVE' } }
);

function getSentPositionStateModel(): Model<SentPositionStateDoc> {
  if (mongoose.models[MODEL_NAME]) {
    delete mongoose.models[MODEL_NAME];
    delete mongoose.connection.models[MODEL_NAME];
  }
  return mongoose.model<SentPositionStateDoc>(MODEL_NAME, SentPositionStateSchema);
}

export const SentPositionStateModel = getSentPositionStateModel();

console.log('[Sentiment-ML] Position State Model loaded (BLOCK 6C)');
