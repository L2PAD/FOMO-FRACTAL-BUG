/**
 * Entity Buckets Model
 * =====================
 * 
 * P2.1: Aggregated entity flows by type (CEX/BRIDGE/WHALE/etc)
 */

import mongoose, { Schema, model } from 'mongoose';

const TypeBucketSchema = new Schema({
  netUsd: { type: Number, default: 0 },
  trades: { type: Number, default: 0 },
}, { _id: false });

const EntityBucketsSchema = new Schema(
  {
    chainId: { type: Number, index: true, required: true },
    window: { type: String, index: true, required: true },
    bucketTs: { type: Date, index: true, required: true },

    // Totals
    totalNetUsd: { type: Number, default: 0 },
    totalTrades: { type: Number, default: 0 },
    pricedShareAvg: { type: Number, default: 0 },

    // By entity type
    byType: {
      EXCHANGE: TypeBucketSchema,
      BRIDGE: TypeBucketSchema,
      PROTOCOL: TypeBucketSchema,
      FUND: TypeBucketSchema,
      WHALE: TypeBucketSchema,
      SMART_MONEY: TypeBucketSchema,
      OTHER: TypeBucketSchema,
    },

    // Top movers
    topAccumulating: {
      type: [
        {
          entityId: String,
          entityLabel: String,
          entityType: String,
          netUsd: Number,
          trades: Number,
        },
      ],
      default: [],
    },
    topDistributing: {
      type: [
        {
          entityId: String,
          entityLabel: String,
          entityType: String,
          netUsd: Number,
          trades: Number,
        },
      ],
      default: [],
    },
  },
  { timestamps: true, collection: 'onchain_v2_entity_buckets' }
);

EntityBucketsSchema.index({ chainId: 1, window: 1, bucketTs: 1 }, { unique: true });

export const EntityBucketsModel =
  mongoose.models.EntityBuckets || model('EntityBuckets', EntityBucketsSchema);

console.log('[EntityBuckets] Model loaded');
