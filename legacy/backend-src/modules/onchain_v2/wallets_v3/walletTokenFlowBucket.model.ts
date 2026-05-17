/**
 * Wallet Token Flow Bucket Model — Phase C3.1
 * ==============================================
 * Per-wallet, per-token daily flow aggregates.
 * Enables fast token drilldown queries without scanning raw ERC20 logs.
 */

import mongoose, { Schema } from 'mongoose';

const WalletTokenFlowBucketSchema = new Schema(
  {
    chainId:      { type: Number, required: true },
    walletAddress:{ type: String, required: true },   // lowercase
    tokenAddress: { type: String, required: true },   // lowercase
    tokenSymbol:  { type: String, default: '' },
    bucketDate:   { type: String, required: true },   // YYYY-MM-DD
    bucketTs:     { type: Date,   required: true },   // start of day UTC

    inUsd:        { type: Number, default: 0 },
    outUsd:       { type: Number, default: 0 },
    netUsd:       { type: Number, default: 0 },
    transfers:    { type: Number, default: 0 },

    updatedAt:    { type: Date, default: () => new Date() },
  },
  { timestamps: false }
);

// Unique: one bucket per (chain, wallet, token, day)
WalletTokenFlowBucketSchema.index(
  { chainId: 1, walletAddress: 1, tokenAddress: 1, bucketDate: 1 },
  { unique: true, name: 'uniq_wallet_token_day' }
);

// Query: all token buckets for a wallet in a time range
WalletTokenFlowBucketSchema.index(
  { chainId: 1, walletAddress: 1, bucketTs: -1 },
  { name: 'idx_wallet_token_time' }
);

export const WalletTokenFlowBucketModel =
  mongoose.models.WalletTokenFlowBucket ||
  mongoose.model('WalletTokenFlowBucket', WalletTokenFlowBucketSchema, 'wallet_token_flow_buckets');
