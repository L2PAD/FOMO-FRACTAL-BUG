/**
 * Chain Model — Phase G0.1
 * ==========================
 * MongoDB schema for chain registry.
 */

import mongoose, { Schema } from 'mongoose';

const ChainSchema = new Schema(
  {
    chainId:       { type: Number, required: true, unique: true },
    key:           { type: String, required: true, unique: true },
    name:          { type: String, required: true },
    rpcUrl:        { type: String, default: '' },
    explorerUrl:   { type: String, default: '' },
    nativeSymbol:  { type: String, required: true },
    enabled:       { type: Boolean, default: false },
    priority:      { type: Number, default: 100 },
  },
  { timestamps: true }
);

ChainSchema.index({ enabled: 1, priority: 1 }, { name: 'idx_enabled_priority' });

export const ChainModel =
  mongoose.models.Chain ||
  mongoose.model('Chain', ChainSchema, 'chains');
