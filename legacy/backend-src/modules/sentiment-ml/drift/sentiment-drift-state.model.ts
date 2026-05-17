/**
 * Sentiment Drift State Model
 * =============================
 * 
 * BLOCK S3: Stores EMA-smoothed PSI and persistence counters.
 * 
 * Used for drift stabilization - we don't react to single spikes,
 * only to persistent drift.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export interface SentimentDriftStateDoc extends Document {
  key: string;                              // "24H" | "7D" | "30D"
  baselineVersion: number | null;

  // EMA smoothed PSI per feature
  psiEmaByFeature: Record<string, number>;
  
  // Last raw PSI (for debugging)
  psiLastByFeature: Record<string, number>;
  
  // Last computed statuses
  lastRawStatus: string;
  lastEmaStatus: string;
  lastStabilizedStatus: string;

  // Streak counters (persistence)
  warnStreak: number;
  degradedStreak: number;
  criticalStreak: number;

  // Timestamps
  lastRunAt: Date | null;
  updatedAt: Date;
}

const SentimentDriftStateSchema = new Schema<SentimentDriftStateDoc>(
  {
    key: { type: String, required: true, unique: true },
    baselineVersion: { type: Number, default: null },

    psiEmaByFeature: { type: Schema.Types.Mixed, default: {} },
    psiLastByFeature: { type: Schema.Types.Mixed, default: {} },

    lastRawStatus: { type: String, default: 'OK' },
    lastEmaStatus: { type: String, default: 'OK' },
    lastStabilizedStatus: { type: String, default: 'OK' },

    warnStreak: { type: Number, default: 0 },
    degradedStreak: { type: Number, default: 0 },
    criticalStreak: { type: Number, default: 0 },

    lastRunAt: { type: Date, default: null },
  },
  { 
    timestamps: { updatedAt: true, createdAt: false },
    collection: 'sentiment_drift_state',
  }
);

SentimentDriftStateSchema.index({ key: 1 }, { unique: true });

export const SentimentDriftStateModel: Model<SentimentDriftStateDoc> =
  (mongoose.models.SentimentDriftState as Model<SentimentDriftStateDoc>) ||
  mongoose.model<SentimentDriftStateDoc>('SentimentDriftState', SentimentDriftStateSchema);

console.log('[Sentiment-ML] Drift State Model loaded (BLOCK S3)');
