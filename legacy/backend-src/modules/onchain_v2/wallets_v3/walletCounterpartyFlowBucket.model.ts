/**
 * Wallet Counterparty Flow Bucket Model — Phase C3.2
 * =====================================================
 * Per-wallet, per-counterparty daily flow aggregates.
 * Enables fast counterparty drilldown queries without scanning raw ERC20 logs.
 */

import mongoose, { Schema } from 'mongoose';

const WalletCounterpartyFlowBucketSchema = new Schema(
  {
    chainId:            { type: Number, required: true },
    walletAddress:      { type: String, required: true },   // lowercase
    counterpartyAddress:{ type: String, required: true },   // lowercase
    entityId:           { type: String, default: null },
    entityName:         { type: String, default: null },
    entityType:         { type: String, default: null },
    bucketDate:         { type: String, required: true },   // YYYY-MM-DD
    bucketTs:           { type: Date,   required: true },   // start of day UTC

    inUsd:              { type: Number, default: 0 },
    outUsd:             { type: Number, default: 0 },
    netUsd:             { type: Number, default: 0 },
    transfers:          { type: Number, default: 0 },

    updatedAt:          { type: Date, default: () => new Date() },
  },
  { timestamps: false }
);

// Unique: one bucket per (chain, wallet, counterparty, day)
WalletCounterpartyFlowBucketSchema.index(
  { chainId: 1, walletAddress: 1, counterpartyAddress: 1, bucketDate: 1 },
  { unique: true, name: 'uniq_wallet_cp_day' }
);

// Query: all counterparty buckets for a wallet in a time range
WalletCounterpartyFlowBucketSchema.index(
  { chainId: 1, walletAddress: 1, bucketTs: -1 },
  { name: 'idx_wallet_cp_time' }
);

export const WalletCounterpartyFlowBucketModel =
  mongoose.models.WalletCounterpartyFlowBucket ||
  mongoose.model('WalletCounterpartyFlowBucket', WalletCounterpartyFlowBucketSchema, 'wallet_counterparty_flow_buckets');
