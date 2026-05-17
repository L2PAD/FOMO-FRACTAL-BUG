/**
 * Feature Flag Lock Model
 * =========================
 * 
 * F6: Prevents admin mutations during freeze/maintenance periods.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export interface FeatureFlagLockDoc extends Document {
  moduleKey: string;        // "sentiment" | "exchange"
  scope: string;            // "admin-write" | "training" | "promotion"
  reason: string;
  lockedBy: string;         // "system" | "admin" | "deploy"
  lockedAt: Date;
  unlockAt: Date;           // TTL moment
  isActive: boolean;
  metadata?: Record<string, any>;
}

const FeatureFlagLockSchema = new Schema<FeatureFlagLockDoc>(
  {
    moduleKey: { type: String, required: true, index: true },
    scope: { type: String, required: true, default: 'admin-write' },
    reason: { type: String, required: true },
    lockedBy: { type: String, required: true },
    lockedAt: { type: Date, required: true, default: () => new Date() },
    unlockAt: { type: Date, required: true, index: true },
    isActive: { type: Boolean, required: true, default: true, index: true },
    metadata: { type: Schema.Types.Mixed },
  },
  {
    timestamps: true,
    collection: 'ml_feature_flag_locks',
  }
);

FeatureFlagLockSchema.index({ moduleKey: 1, scope: 1, isActive: 1 }, { unique: true });

export const FeatureFlagLockModel: Model<FeatureFlagLockDoc> =
  (mongoose.models.FeatureFlagLock as Model<FeatureFlagLockDoc>) ||
  mongoose.model<FeatureFlagLockDoc>('FeatureFlagLock', FeatureFlagLockSchema);

console.log('[Shared] Feature Flag Lock Model loaded (F6)');
