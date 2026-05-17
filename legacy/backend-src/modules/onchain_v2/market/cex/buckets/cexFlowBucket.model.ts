/**
 * CEX Flow Bucket Model — Phase A3
 * =================================
 * Pre-computed aggregates of CEX in/out flows per (exchange, token, window).
 * Replaces the slow 26-sequential-query pattern with instant reads.
 */

import mongoose, { Schema } from 'mongoose';

export type CexWindow = '24h' | '7d' | '30d';

const CexFlowBucketSchema = new Schema(
  {
    chainId:          { type: Number, required: true },
    exchangeId:       { type: String, required: true },
    tokenAddress:     { type: String, required: true },
    window:           { type: String, required: true },
    bucketStart:      { type: Date,   required: true },

    inflowUsd:        { type: Number, default: 0 },
    outflowUsd:       { type: Number, default: 0 },
    netUsd:           { type: Number, default: 0 },

    transferCount:    { type: Number, default: 0 },
    uniqueSenders:    { type: Number, default: 0 },
    uniqueReceivers:  { type: Number, default: 0 },

    tokenSymbol:      { type: String, default: '' },

    updatedAt:        { type: Date, default: () => new Date() },
  },
  { timestamps: false }
);

// Unique compound key: one bucket per (chain, exchange, token, window, time)
CexFlowBucketSchema.index(
  { chainId: 1, exchangeId: 1, tokenAddress: 1, window: 1, bucketStart: 1 },
  { unique: true, name: 'uniq_bucket' }
);

// Query: all exchanges for a window
CexFlowBucketSchema.index(
  { chainId: 1, window: 1, bucketStart: 1 },
  { name: 'idx_chain_window_bucket' }
);

// Query: single exchange drilldown
CexFlowBucketSchema.index(
  { chainId: 1, exchangeId: 1, window: 1, bucketStart: 1 },
  { name: 'idx_exchange_window_bucket' }
);

// Query: token across exchanges
CexFlowBucketSchema.index(
  { chainId: 1, tokenAddress: 1, window: 1, bucketStart: 1 },
  { name: 'idx_token_window_bucket' }
);

export const CexFlowBucketModel =
  mongoose.models.CexFlowBucket ||
  mongoose.model('CexFlowBucket', CexFlowBucketSchema, 'cex_flow_buckets');
