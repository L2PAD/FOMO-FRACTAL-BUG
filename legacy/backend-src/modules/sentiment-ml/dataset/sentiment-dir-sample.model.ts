/**
 * Sentiment Direction Sample Model
 * =================================
 * 
 * BLOCK 2: Production Dataset Spec
 * 
 * Stores labeled samples for sentiment → price direction validation.
 * Each sample captures:
 * - Sentiment snapshot at asOf
 * - Actual price movement over horizon window
 * - Label (UP/DOWN/NEUTRAL) based on return thresholds
 * 
 * PRODUCTION RULES:
 * - NO lookahead: samples created only after window closes
 * - UNIQUE key: { symbol, window, asOf, labelVersion }
 * - VERSION: labelVersion tracks threshold changes
 * 
 * Collection: sentiment_dir_samples
 */

import mongoose, { Schema, Document, InferSchemaType } from 'mongoose';

export type SentimentWindow = '24H' | '7D' | '30D';
export type DirLabel = 'UP' | 'DOWN' | 'NEUTRAL';
export type SampleQuality = 'OK' | 'LOW_VOLUME' | 'MISSING_PRICE' | 'MISSING_AGG';

export interface ISentimentDirSample extends Document {
  // Keys
  symbol: string;
  window: SentimentWindow;
  asOf: Date;

  // INPUT (known at asOf - from aggregate snapshot)
  bias: number;              // -1..+1
  score: number;             // 0..1
  confidence: number;        // 0..1 (weighted confidence)
  volume: number;            // tweet count used
  connectionsWeight: number; // aggregated author/influence weight
  eventsCount: number;       // backwards compat
  
  // ML Features (BLOCK 3)
  authorScoreMean?: number;      // Mean author credibility score
  influenceMean?: number;        // Mean author influence  
  botProbMean?: number;          // Mean bot probability
  weightedScore?: number;        // Weighted sentiment score
  weightedConfidence?: number;   // Weighted confidence

  // Regime (optional, for future)
  regime?: 'BULL' | 'BEAR' | 'CHOP';

  // OUTCOME (future after horizon)
  priceAtAsOf: number;
  priceAtHorizonClose: number;
  forwardReturnPct: number;  // (close - open) / open
  label: DirLabel;

  // Metadata
  labelVersion: number;      // versioned labeling logic (v1 = current thresholds)
  finalizedAt: Date;
  quality: SampleQuality;

  // ML Snapshot (optional)
  ml?: {
    pUp: number;
    action: string;
    confidence: number;
    modelId: string;
  };

  createdAt: Date;
  updatedAt: Date;
}

const SentimentDirSampleSchema = new Schema<ISentimentDirSample>(
  {
    symbol: { type: String, required: true, index: true },
    window: { type: String, required: true, enum: ['24H', '7D', '30D'], index: true },
    asOf: { type: Date, required: true, index: true },

    // INPUT snapshot
    bias: { type: Number, required: true },
    score: { type: Number, required: true },
    confidence: { type: Number, required: true },
    volume: { type: Number, required: true, default: 0 },
    connectionsWeight: { type: Number, required: true, default: 0 },
    eventsCount: { type: Number, required: true, default: 0 },
    
    // ML Features (BLOCK 3)
    authorScoreMean: { type: Number },
    influenceMean: { type: Number },
    botProbMean: { type: Number },
    weightedScore: { type: Number },
    weightedConfidence: { type: Number },

    // Regime (optional)
    regime: { type: String, enum: ['BULL', 'BEAR', 'CHOP'] },

    // OUTCOME
    priceAtAsOf: { type: Number, required: true },
    priceAtHorizonClose: { type: Number, required: true },
    forwardReturnPct: { type: Number, required: true },
    label: { type: String, required: true, enum: ['UP', 'DOWN', 'NEUTRAL'], index: true },

    // Metadata
    labelVersion: { type: Number, required: true, default: 1, index: true },
    finalizedAt: { type: Date, required: true },
    quality: { 
      type: String, 
      enum: ['OK', 'LOW_VOLUME', 'MISSING_PRICE', 'MISSING_AGG'], 
      default: 'OK',
      index: true,
    },

    // ML snapshot at finalize time
    ml: {
      pUp: { type: Number },
      action: { type: String },
      confidence: { type: Number },
      modelId: { type: String },
    },
  },
  { 
    timestamps: true,
    collection: 'sentiment_dir_samples',
  }
);

// UNIQUE anti-duplicate key (versioned)
SentimentDirSampleSchema.index(
  { symbol: 1, window: 1, asOf: 1, labelVersion: 1 }, 
  { unique: true }
);

// Performance analysis queries
SentimentDirSampleSchema.index({ symbol: 1, window: 1, createdAt: -1 });

// ML training queries  
SentimentDirSampleSchema.index({ window: 1, asOf: -1 });

// Label distribution queries
SentimentDirSampleSchema.index({ window: 1, label: 1 });

// Quality queries
SentimentDirSampleSchema.index({ quality: 1, window: 1 });

// Safe model getter (prevents mongoose overwrite error during hot reload)
export function getSentimentDirSampleModel() {
  if (mongoose.models.SentimentDirSample) {
    return mongoose.models.SentimentDirSample as mongoose.Model<ISentimentDirSample>;
  }
  return mongoose.model<ISentimentDirSample>('SentimentDirSample', SentimentDirSampleSchema);
}

export const SentimentDirSampleModel = getSentimentDirSampleModel();

console.log('[Sentiment-ML] Dir Sample Model loaded (BLOCK 2 Production Spec)');
