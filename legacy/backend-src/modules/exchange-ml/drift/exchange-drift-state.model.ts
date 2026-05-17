/**
 * Exchange Drift State Model
 * ===========================
 * 
 * EX-S3: Stores EMA-smoothed PSI and persistence counters.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export interface ExchangeDriftStateDoc extends Document {
  key: string;                        // "default" or horizon-specific
  baselineVersion: number | null;

  // EMA smoothed PSI per feature
  psiEmaByFeature: Record<string, number>;
  
  // Last raw PSI
  psiLastByFeature: Record<string, number>;
  psiRaw: number;
  psiEma: number;
  
  // Statuses
  lastRawStatus: string;
  lastEmaStatus: string;
  lastStabilizedStatus: string;

  // Streak counters
  warnStreak: number;
  degradedStreak: number;
  criticalStreak: number;

  // Actions
  actions: {
    trainingBlocked: boolean;
    workersBlocked: boolean;
    confidenceMultiplier: number;
    sizeMultiplier: number;
  };

  // Timestamps
  lastRunAt: Date | null;
  updatedAt: Date;
}

const ExchangeDriftStateSchema = new Schema<ExchangeDriftStateDoc>(
  {
    key: { type: String, required: true, unique: true },
    baselineVersion: { type: Number, default: null },

    psiEmaByFeature: { type: Schema.Types.Mixed, default: {} },
    psiLastByFeature: { type: Schema.Types.Mixed, default: {} },
    psiRaw: { type: Number, default: 0 },
    psiEma: { type: Number, default: 0 },

    lastRawStatus: { type: String, default: 'OK' },
    lastEmaStatus: { type: String, default: 'OK' },
    lastStabilizedStatus: { type: String, default: 'OK' },

    warnStreak: { type: Number, default: 0 },
    degradedStreak: { type: Number, default: 0 },
    criticalStreak: { type: Number, default: 0 },

    actions: {
      trainingBlocked: { type: Boolean, default: false },
      workersBlocked: { type: Boolean, default: false },
      confidenceMultiplier: { type: Number, default: 1.0 },
      sizeMultiplier: { type: Number, default: 1.0 },
    },

    lastRunAt: { type: Date, default: null },
  },
  {
    timestamps: { updatedAt: true, createdAt: false },
    collection: 'exchange_drift_state',
  }
);

ExchangeDriftStateSchema.index({ key: 1 }, { unique: true });

export const ExchangeDriftStateModel: Model<ExchangeDriftStateDoc> =
  (mongoose.models.ExchangeDriftState as Model<ExchangeDriftStateDoc>) ||
  mongoose.model<ExchangeDriftStateDoc>('ExchangeDriftState', ExchangeDriftStateSchema);

console.log('[Exchange-ML] Drift State Model loaded (EX-S3)');
