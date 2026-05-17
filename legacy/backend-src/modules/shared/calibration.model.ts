/**
 * Calibration Bucket Model
 * ==========================
 * 
 * F4: Stores confidence bucket statistics for calibration monitoring.
 * Uses Beta(2,2) prior for Bayesian posterior estimation.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export interface CalibrationBucketDoc extends Document {
  moduleKey: string;        // "sentiment" | "exchange"
  channel: string;          // "RULE" | "ML"
  window: string;           // "24H" | "7D" | "30D"
  bucketMin: number;        // e.g., 0.50
  bucketMax: number;        // e.g., 0.60
  n: number;                // total predictions
  wins: number;             // correct predictions
  losses: number;           // incorrect predictions
  alpha: number;            // prior alpha (default 2)
  beta: number;             // prior beta (default 2)
  posteriorMean: number;    // (wins + alpha) / (n + alpha + beta)
  empiricalWinRate: number; // wins / n
  calibrationError: number; // |midBucket - posteriorMean|
  updatedAt: Date;
}

const CalibrationBucketSchema = new Schema<CalibrationBucketDoc>(
  {
    moduleKey: { type: String, required: true, index: true },
    channel: { type: String, required: true },
    window: { type: String, required: true },
    bucketMin: { type: Number, required: true },
    bucketMax: { type: Number, required: true },
    n: { type: Number, default: 0 },
    wins: { type: Number, default: 0 },
    losses: { type: Number, default: 0 },
    alpha: { type: Number, default: 2 },
    beta: { type: Number, default: 2 },
    posteriorMean: { type: Number, default: 0.5 },
    empiricalWinRate: { type: Number, default: 0 },
    calibrationError: { type: Number, default: 0 },
  },
  {
    timestamps: { updatedAt: true, createdAt: false },
    collection: 'ml_calibration_buckets',
  }
);

CalibrationBucketSchema.index(
  { moduleKey: 1, channel: 1, window: 1, bucketMin: 1, bucketMax: 1 },
  { unique: true }
);

export const CalibrationBucketModel: Model<CalibrationBucketDoc> =
  (mongoose.models.CalibrationBucket as Model<CalibrationBucketDoc>) ||
  mongoose.model<CalibrationBucketDoc>('CalibrationBucket', CalibrationBucketSchema);

/**
 * Calibration Snapshot Model
 * Stores point-in-time calibration status
 */
export interface CalibrationSnapshotDoc extends Document {
  moduleKey: string;
  window: string;
  total: number;
  ece: number;              // Expected Calibration Error
  status: string;           // OK | WARN | DEGRADED | CRITICAL | UNKNOWN
  buckets: Array<{
    range: string;
    n: number;
    wins: number;
    posteriorMean: number;
    midpoint: number;
    error: number;
  }>;
  createdAt: Date;
}

const CalibrationSnapshotSchema = new Schema<CalibrationSnapshotDoc>(
  {
    moduleKey: { type: String, required: true, index: true },
    window: { type: String, required: true },
    total: { type: Number, required: true },
    ece: { type: Number, required: true },
    status: { type: String, required: true },
    buckets: { type: Schema.Types.Mixed },
    createdAt: { type: Date, default: () => new Date(), index: true },
  },
  {
    timestamps: false,
    collection: 'ml_calibration_snapshots',
  }
);

CalibrationSnapshotSchema.index({ moduleKey: 1, window: 1, createdAt: -1 });

export const CalibrationSnapshotModel: Model<CalibrationSnapshotDoc> =
  (mongoose.models.CalibrationSnapshot as Model<CalibrationSnapshotDoc>) ||
  mongoose.model<CalibrationSnapshotDoc>('CalibrationSnapshot', CalibrationSnapshotSchema);

console.log('[Shared] Calibration Models loaded (F4)');
