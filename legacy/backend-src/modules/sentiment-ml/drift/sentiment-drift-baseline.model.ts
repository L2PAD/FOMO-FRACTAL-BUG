/**
 * Sentiment Drift Baseline Model
 * ================================
 * 
 * BLOCK S2: MongoDB model for versioned baselines.
 * 
 * Each baseline stores feature distributions at a point in time.
 * Used for PSI drift comparison.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import type { 
  SentWindow, 
  BaselineCreateReason, 
  FeatureDistribution, 
  UriSnapshot,
  SentimentDriftBaselineDoc 
} from './sentiment-drift-baseline.types.js';

interface BaselineDocument extends Document, SentimentDriftBaselineDoc {}

const FeatureHistogramSchema = new Schema(
  {
    bins: { type: [Number], required: true },
    min: { type: Number, required: true },
    max: { type: Number, required: true },
    binCount: { type: Number, required: true },
  },
  { _id: false }
);

const FeatureQuantilesSchema = new Schema(
  {
    p05: { type: Number, required: true },
    p25: { type: Number, required: true },
    p50: { type: Number, required: true },
    p75: { type: Number, required: true },
    p95: { type: Number, required: true },
  },
  { _id: false }
);

const FeatureDistributionSchema = new Schema(
  {
    feature: { type: String, required: true },
    hist: { type: FeatureHistogramSchema, required: true },
    q: { type: FeatureQuantilesSchema, required: true },
    n: { type: Number, required: true },
  },
  { _id: false }
);

const UriSnapshotSchema = new Schema(
  {
    score: { type: Number, required: true },
    status: { type: String, required: true },
    dataHealth: { type: Number, required: true },
    driftHealth: { type: Number, required: true },
    capitalHealth: { type: Number, required: true },
    calibrationHealth: { type: Number, required: true },
    reasons: { type: [String], default: [] },
  },
  { _id: false }
);

const SentimentDriftBaselineSchema = new Schema<BaselineDocument>(
  {
    module: { type: String, required: true, enum: ['sentiment'], index: true },
    window: { type: String, required: true, enum: ['24H', '7D', '30D'], index: true },
    version: { type: Number, required: true, index: true },
    reason: { type: String, required: true, enum: ['AUTO', 'MANUAL'] },
    notes: { type: String },
    sampleCount: { type: Number, required: true },
    source: { type: String, required: true, enum: ['aggregates', 'samples'] },
    featureDistributions: { type: Schema.Types.Mixed, required: true },
    uriAtCreation: { type: UriSnapshotSchema, required: true },
  },
  { 
    timestamps: { createdAt: true, updatedAt: false },
    collection: 'sentiment_drift_baselines',
  }
);

// Unique version per window
SentimentDriftBaselineSchema.index({ module: 1, window: 1, version: 1 }, { unique: true });
// Fast latest lookup
SentimentDriftBaselineSchema.index({ module: 1, window: 1, createdAt: -1 });

export const SentimentDriftBaselineModel: Model<BaselineDocument> =
  (mongoose.models.SentimentDriftBaseline as Model<BaselineDocument>) ||
  mongoose.model<BaselineDocument>('SentimentDriftBaseline', SentimentDriftBaselineSchema);

console.log('[Sentiment-ML] Drift Baseline Model loaded (BLOCK S2)');
