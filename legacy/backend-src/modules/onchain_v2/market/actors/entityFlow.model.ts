/**
 * Entity Flow Model
 * ==================
 * 
 * PHASE 5: Actors - Entity flow aggregation
 */

import mongoose, { Schema, model } from 'mongoose';

const EntityFlowSchema = new Schema(
  {
    chainId: { type: Number, required: true, default: 1, index: true },
    entityId: { type: String, index: true }, // address or cluster id
    entityName: { type: String }, // Human-readable name (Binance, Coinbase, etc.)
    entityType: {
      type: String,
      enum: ['EXCHANGE', 'WHALE', 'BRIDGE', 'SMART_MONEY', 'FUND', 'PROTOCOL', 'UNKNOWN', 'exchange', 'whale', 'bridge', 'fund', 'protocol', 'dex', 'actor', 'unknown'],
      index: true,
    },

    bucketTs: { type: Date, index: true },
    window: { type: String, enum: ['24h', '7d', '30d'], index: true },

    netUsd: { type: Number, default: 0 },
    dexUsd: { type: Number, default: 0 },
    cexUsd: { type: Number, default: 0 },
    bridgeUsd: { type: Number, default: 0 },

    trades: { type: Number, default: 0 },
    pricedShare: { type: Number, default: 0 },

    // P0.6.1: Attribution fields (v2 labels + v1 inference)
    attributionSource: { 
      type: String, 
      enum: ['LABEL_V2', 'ENTITY_V1', 'ACTOR_CLUSTER_V1', 'BEHAVIORAL_FALLBACK'],
      index: true 
    },
    attributionConfidence: { type: Number, default: 0 },
    attributionEvidence: { type: Array, default: [] },

    // Token breakdown
    tokenBreakdown: {
      type: [
        {
          tokenAddress: String,
          tokenSymbol: String,
          netUsd: Number,
          trades: Number,
        },
      ],
      default: [],
    },
  },
  { timestamps: true }
);

EntityFlowSchema.index({ chainId: 1, entityId: 1, window: 1, bucketTs: 1 }, { unique: true });
EntityFlowSchema.index({ chainId: 1, window: 1, netUsd: -1 });

export const EntityFlowModel =
  mongoose.models.EntityFlow || model('EntityFlow', EntityFlowSchema, 'onchain_v2_entity_flows');
