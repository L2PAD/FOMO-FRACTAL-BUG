/**
 * Exchange Drift Baseline Model
 * ==============================
 * 
 * EX-S2: Versioned baselines for drift comparison.
 * Stores feature distributions from stable periods.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export interface ExchangeDriftBaselineDoc extends Document {
  version: number;
  createdAt: Date;
  mode: 'AUTO' | 'MANUAL';

  uriScore: number;
  capitalHealth: number;
  driftHealth: number;

  snapshot: {
    featureStats: Record<string, { mean: number; std: number; bins?: number[] }>;
    capital: {
      expectancy: number;
      sharpeLike: number;
      maxDD: number;
      winRate: number;
      tradesCount: number;
    };
    regime?: {
      dominantRegime: 'BULL' | 'BEAR' | 'CHOP' | 'UNKNOWN';
      volatilityState: 'LOW' | 'MID' | 'HIGH';
    };
  };

  lockedUntil?: Date;
  notes?: string;
}

const ExchangeDriftBaselineSchema = new Schema<ExchangeDriftBaselineDoc>(
  {
    version: { type: Number, required: true, index: true },
    createdAt: { type: Date, default: Date.now },
    mode: { type: String, enum: ['AUTO', 'MANUAL'], required: true },

    uriScore: { type: Number, required: true },
    capitalHealth: { type: Number, required: true },
    driftHealth: { type: Number, required: true },

    snapshot: {
      featureStats: { type: Schema.Types.Mixed, default: {} },
      capital: {
        expectancy: Number,
        sharpeLike: Number,
        maxDD: Number,
        winRate: Number,
        tradesCount: Number,
      },
      regime: {
        dominantRegime: String,
        volatilityState: String,
      },
    },

    lockedUntil: { type: Date },
    notes: { type: String },
  },
  {
    timestamps: false,
    collection: 'exchange_drift_baselines',
  }
);

ExchangeDriftBaselineSchema.index({ version: -1 });
ExchangeDriftBaselineSchema.index({ createdAt: -1 });

export const ExchangeDriftBaselineModel: Model<ExchangeDriftBaselineDoc> =
  (mongoose.models.ExchangeDriftBaseline as Model<ExchangeDriftBaselineDoc>) ||
  mongoose.model<ExchangeDriftBaselineDoc>('ExchangeDriftBaseline', ExchangeDriftBaselineSchema);

console.log('[Exchange-ML] Drift Baseline Model loaded (EX-S2)');
