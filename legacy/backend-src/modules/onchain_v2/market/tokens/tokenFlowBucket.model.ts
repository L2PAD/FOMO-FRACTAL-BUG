/**
 * Token Flow Bucket Model — Phase D3
 * =====================================
 * Pre-computed flow aggregates per token per time bucket.
 * Bucket sizes: 1h (24h window), 6h (7d window), 1d (30d window).
 */

import mongoose, { Schema } from 'mongoose';

const TokenFlowBucketSchema = new Schema(
  {
    chainId:       { type: Number, required: true },
    tokenAddress:  { type: String, required: true },
    tokenSymbol:   { type: String, default: '' },
    window:        { type: String, required: true },   // '24h' | '7d' | '30d'
    bucketTs:      { type: Date,   required: true },   // start of bucket

    inflowUsd:     { type: Number, default: 0 },       // BUY side
    outflowUsd:    { type: Number, default: 0 },       // SELL side
    netUsd:        { type: Number, default: 0 },
    transfers:     { type: Number, default: 0 },
    uniqueWallets: { type: Number, default: 0 },

    computedAt:    { type: Date, default: () => new Date() },
  },
  { timestamps: false }
);

TokenFlowBucketSchema.index(
  { chainId: 1, tokenAddress: 1, window: 1, bucketTs: 1 },
  { unique: true, name: 'uniq_token_flow_bucket' }
);

TokenFlowBucketSchema.index(
  { chainId: 1, window: 1, bucketTs: 1 },
  { name: 'idx_chain_window_ts' }
);

export const TokenFlowBucketModel =
  mongoose.models.TokenFlowBucket ||
  mongoose.model('TokenFlowBucket', TokenFlowBucketSchema, 'token_flow_buckets');
