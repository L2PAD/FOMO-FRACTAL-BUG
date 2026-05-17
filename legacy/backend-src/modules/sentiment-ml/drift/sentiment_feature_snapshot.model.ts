/**
 * Sentiment Feature Snapshot Model
 * ==================================
 * 
 * BLOCK 10.1: Stores feature distribution baseline from training.
 * Used for drift detection via PSI comparison.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export type SentWindow = '24H' | '7D' | '30D';

export type HistBin = { lo: number; hi: number; p: number };

export type FeatureStat = {
  mean: number;
  std: number;
  bins: HistBin[];
  n: number;
  min?: number;
  max?: number;
};

export interface FeatureSnapshotDoc extends Document {
  modelId: string;
  window: SentWindow;
  featureKeys: string[];
  stats: Record<string, FeatureStat>;
  createdAt: Date;
}

const HistBinSchema = new Schema<HistBin>(
  { lo: Number, hi: Number, p: Number },
  { _id: false }
);

const FeatureStatSchema = new Schema<FeatureStat>(
  {
    mean: { type: Number, required: true },
    std: { type: Number, required: true },
    bins: { type: [HistBinSchema], required: true },
    n: { type: Number, required: true },
    min: Number,
    max: Number,
  },
  { _id: false }
);

const FeatureSnapshotSchema = new Schema<FeatureSnapshotDoc>(
  {
    modelId: { type: String, required: true, index: true },
    window: { type: String, required: true, index: true },
    featureKeys: { type: [String], required: true },
    stats: { type: Schema.Types.Mixed, required: true },
  },
  { timestamps: { createdAt: true, updatedAt: false } }
);

// One baseline snapshot per model per window
FeatureSnapshotSchema.index({ modelId: 1, window: 1 }, { unique: true });

export const SentimentFeatureSnapshotModel: Model<FeatureSnapshotDoc> =
  (mongoose.models.SentimentFeatureSnapshot as Model<FeatureSnapshotDoc>) ||
  mongoose.model<FeatureSnapshotDoc>(
    'SentimentFeatureSnapshot',
    FeatureSnapshotSchema,
    'sentiment_feature_snapshots'
  );

console.log('[Sentiment-ML] Feature Snapshot Model loaded (BLOCK 10.1)');
