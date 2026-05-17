/**
 * System Lock Model
 * =================
 * 
 * Distributed lock for preventing parallel job execution.
 * Used by sentiment dataset finalize job and other background workers.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export interface ISystemLock extends Document {
  key: string;
  lockedUntil: Date;
  owner: string;
  updatedAt: Date;
}

const COLLECTION_NAME = 'system_locks';
const MODEL_NAME = 'SystemLock';

const SystemLockSchema = new Schema<ISystemLock>(
  {
    key: { type: String, required: true, unique: true, index: true },
    lockedUntil: { type: Date, required: true, index: true },
    owner: { type: String, required: true },
  },
  { 
    timestamps: { createdAt: false, updatedAt: 'updatedAt' },
    collection: COLLECTION_NAME,
  }
);

// Safe model getter to prevent overwrite error
function getSystemLockModel(): Model<ISystemLock> {
  // Delete existing model if exists (for hot reload compatibility)
  if (mongoose.models[MODEL_NAME]) {
    delete mongoose.models[MODEL_NAME];
    delete mongoose.connection.models[MODEL_NAME];
  }
  return mongoose.model<ISystemLock>(MODEL_NAME, SystemLockSchema);
}

export const SystemLockModel = getSystemLockModel();
