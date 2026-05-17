/**
 * Sentiment Binary Model Schema
 * ==============================
 * 
 * BLOCK 8: MongoDB schema for trained binary models.
 * 
 * Stores:
 * - modelId: unique identifier
 * - window: 24H/7D/30D
 * - weights: logistic regression coefficients
 * - bias: intercept term
 * - meta: training metrics
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import { BinaryModelMeta, SentimentWindow } from '../../contracts/sentiment-ml.types.js';

export interface SentimentBinModelDoc extends Document {
  modelId: string;
  window: SentimentWindow;
  algo: 'logreg';
  weights: number[];
  bias: number;
  meta: BinaryModelMeta;
}

const COLLECTION_NAME = 'sentiment_bin_models';
const MODEL_NAME = 'SentimentBinModel';

const SentimentBinModelSchema = new Schema({
  modelId: { type: String, index: true, unique: true, required: true },
  window: { type: String, enum: ['24H', '7D', '30D'], index: true, required: true },
  algo: { type: String, default: 'logreg' },

  // Logistic regression parameters
  weights: { type: [Number], required: true },
  bias: { type: Number, required: true },

  // Training metadata
  meta: {
    modelId: String,
    window: String,
    algo: String,
    createdAt: { type: Date, default: Date.now },
    trainSamples: Number,
    testSamples: Number,
    auc: Number,
    acc: Number,
    brier: Number,
    posRatio: Number,
  },
}, { 
  collection: COLLECTION_NAME,
  timestamps: true,
});

// Safe model getter to prevent overwrite error
function getSentimentBinModel(): Model<SentimentBinModelDoc> {
  if (mongoose.models[MODEL_NAME]) {
    delete mongoose.models[MODEL_NAME];
    delete mongoose.connection.models[MODEL_NAME];
  }
  return mongoose.model<SentimentBinModelDoc>(MODEL_NAME, SentimentBinModelSchema);
}

export const SentimentBinModel = getSentimentBinModel();

console.log('[Sentiment-ML] Binary Model schema loaded (BLOCK 8)');
