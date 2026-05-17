/**
 * Sentiment Binary Registry Schema
 * ==================================
 * 
 * BLOCK 8 + BLOCK 5: Tracks active model per window with lifecycle support.
 * 
 * Supports:
 * - activeType: RULE | ML
 * - shadowModelId: candidate for promotion
 * - Promotion/rollback tracking
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import { SentimentWindow } from '../../contracts/sentiment-ml.types.js';

export type SentimentActiveType = 'RULE' | 'ML';

export interface SentimentBinRegistryDoc extends Document {
  window: SentimentWindow;
  
  // Active decision source
  activeType: SentimentActiveType;
  activeModelId?: string;
  
  // Shadow (candidate for promotion)
  shadowType: 'ML';
  shadowModelId?: string;
  
  // Lifecycle tracking
  meta: {
    activeReason: string;
    shadowReason?: string;
    lastPromotionAt?: Date;
    lastRollbackAt?: Date;
    lastTrainAt?: Date;
    lastShadowSetAt?: Date;
  };
  
  updatedAt: Date;
  createdAt: Date;
}

const COLLECTION_NAME = 'sentiment_bin_registry';
const MODEL_NAME = 'SentimentBinRegistry';

const SentimentBinRegistrySchema = new Schema({
  window: { 
    type: String, 
    enum: ['24H', '7D', '30D'], 
    unique: true, 
    index: true,
    required: true,
  },
  
  // Active decision source (BLOCK 5 - Lifecycle)
  activeType: { 
    type: String, 
    enum: ['RULE', 'ML'], 
    default: 'RULE',
    required: true,
  },
  activeModelId: { type: String },
  
  // Shadow (candidate)
  shadowType: { 
    type: String, 
    enum: ['ML'], 
    default: 'ML',
  },
  shadowModelId: { type: String },
  
  // Lifecycle meta
  meta: {
    activeReason: { type: String, default: 'init' },
    shadowReason: { type: String },
    lastPromotionAt: { type: Date },
    lastRollbackAt: { type: Date },
    lastTrainAt: { type: Date },
    lastShadowSetAt: { type: Date },
  },
}, { 
  collection: COLLECTION_NAME,
  timestamps: true,
});

// Safe model getter
function getSentimentBinRegistry(): Model<SentimentBinRegistryDoc> {
  if (mongoose.models[MODEL_NAME]) {
    delete mongoose.models[MODEL_NAME];
    delete mongoose.connection.models[MODEL_NAME];
  }
  return mongoose.model<SentimentBinRegistryDoc>(MODEL_NAME, SentimentBinRegistrySchema);
}

export const SentimentBinRegistry = getSentimentBinRegistry();

console.log('[Sentiment-ML] Binary Registry schema loaded (BLOCK 8 + BLOCK 5 Lifecycle)');
