/**
 * Sentiment Drift Result Model
 * ==============================
 * 
 * BLOCK 10.1: Stores daily drift calculation results.
 * Used for monitoring and reliability scoring.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import type { SentWindow } from './sentiment_feature_snapshot.model.js';

export type DriftStatus = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';

export type DriftFeatureScore = {
  psi: number;
  weight: number;
  contribution: number;
};

export interface DriftResultDoc extends Document {
  window: SentWindow;
  modelId: string;
  asOf: Date;
  nLive: number;
  status: DriftStatus;
  driftScore: number;
  psiByFeature: Record<string, DriftFeatureScore>;
  notes: string[];
  createdAt: Date;
}

const DriftResultSchema = new Schema<DriftResultDoc>(
  {
    window: { type: String, required: true, index: true },
    modelId: { type: String, required: true, index: true },
    asOf: { type: Date, required: true, index: true },
    nLive: { type: Number, required: true },
    status: { type: String, required: true, index: true },
    driftScore: { type: Number, required: true },
    psiByFeature: { type: Schema.Types.Mixed, required: true },
    notes: { type: [String], default: [] },
  },
  { timestamps: { createdAt: true, updatedAt: false } }
);

// Prevent duplicates if job runs twice
DriftResultSchema.index({ window: 1, modelId: 1, asOf: 1 }, { unique: true });

export const SentimentDriftResultModel: Model<DriftResultDoc> =
  (mongoose.models.SentimentDriftResult as Model<DriftResultDoc>) ||
  mongoose.model<DriftResultDoc>(
    'SentimentDriftResult',
    DriftResultSchema,
    'sentiment_drift_results'
  );

console.log('[Sentiment-ML] Drift Result Model loaded (BLOCK 10.1)');
