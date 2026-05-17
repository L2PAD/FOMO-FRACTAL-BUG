/**
 * Sentiment Trade Model
 * ======================
 * 
 * BLOCK 6: Paper trades for equity/risk calculation.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import type { SentWindow, SentMode } from '../contracts/sentiment.risk.types.js';

export interface SentTradeDoc extends Document {
  symbol: string;
  window: SentWindow;
  mode: SentMode;
  direction: 'LONG' | 'SHORT';
  asOf: Date;

  entryPrice: number;
  exitPrice: number;
  pnlPct: number;

  openedAt: Date;
  closedAt: Date;

  bias: number;
  confidence: number;
  
  createdAt: Date;
  updatedAt: Date;
}

const COLLECTION_NAME = 'sent_trades';
const MODEL_NAME = 'SentTrade';

const SentTradeSchema = new Schema<SentTradeDoc>({
  symbol: { type: String, required: true, index: true },
  window: { type: String, required: true, index: true, enum: ['24H', '7D', '30D'] },
  mode: { type: String, required: true, index: true, enum: ['RULE', 'ML'] },
  direction: { type: String, required: true, enum: ['LONG', 'SHORT'] },

  asOf: { type: Date, required: true, index: true },

  entryPrice: { type: Number, required: true },
  exitPrice: { type: Number, required: true },
  pnlPct: { type: Number, required: true },

  openedAt: { type: Date, required: true },
  closedAt: { type: Date, required: true, index: true },

  bias: { type: Number, required: true },
  confidence: { type: Number, default: 0 },
}, { 
  collection: COLLECTION_NAME,
  timestamps: true,
});

// Unique: one trade per (symbol, window, asOf, mode)
SentTradeSchema.index(
  { symbol: 1, window: 1, asOf: 1, mode: 1 },
  { unique: true }
);

// For equity queries
SentTradeSchema.index({ window: 1, mode: 1, closedAt: 1 });

function getSentTradeModel(): Model<SentTradeDoc> {
  if (mongoose.models[MODEL_NAME]) {
    delete mongoose.models[MODEL_NAME];
    delete mongoose.connection.models[MODEL_NAME];
  }
  return mongoose.model<SentTradeDoc>(MODEL_NAME, SentTradeSchema);
}

export const SentTradeModel = getSentTradeModel();

console.log('[Sentiment-ML] Trade Model loaded (BLOCK 6)');
