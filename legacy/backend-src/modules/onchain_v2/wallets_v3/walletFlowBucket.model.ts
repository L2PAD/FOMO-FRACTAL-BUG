/**
 * Wallet Flow Bucket Model — Phase C2
 * =====================================
 * Pre-computed daily aggregates per wallet address.
 * Enables fast time-series queries without scanning raw ERC20 logs.
 */

import mongoose, { Schema } from 'mongoose';

const WalletFlowBucketSchema = new Schema(
  {
    chainId:      { type: Number, required: true },
    address:      { type: String, required: true },      // wallet address (lowercase)
    bucketDate:   { type: String, required: true },       // YYYY-MM-DD
    bucketStart:  { type: Date,   required: true },       // start of day UTC

    inflowUsd:    { type: Number, default: 0 },
    outflowUsd:   { type: Number, default: 0 },
    netUsd:       { type: Number, default: 0 },

    transfers:    { type: Number, default: 0 },
    uniqueCounterparties: { type: Number, default: 0 },
    stableUsd:    { type: Number, default: 0 },

    topToken:     { type: String, default: '' },          // symbol of largest flow token
    updatedAt:    { type: Date, default: () => new Date() },
  },
  { timestamps: false }
);

// One bucket per (chain, address, day)
WalletFlowBucketSchema.index(
  { chainId: 1, address: 1, bucketDate: 1 },
  { unique: true, name: 'uniq_wallet_day' }
);

// Query: all days for a wallet in a window
WalletFlowBucketSchema.index(
  { chainId: 1, address: 1, bucketStart: 1 },
  { name: 'idx_wallet_time' }
);

export const WalletFlowBucketModel =
  mongoose.models.WalletFlowBucket ||
  mongoose.model('WalletFlowBucket', WalletFlowBucketSchema, 'wallet_flow_buckets');
