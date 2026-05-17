/**
 * OnChain V2 — Bridge Aggregation Model
 * =======================================
 * 
 * Stores computed bridge migration metrics per time window.
 * Idempotent: unique(window, bucketTs)
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type BridgeAggWindow = '24h' | '7d';

export interface BridgeMetrics {
  // Counts
  inCount: number;
  outCount: number;
  netCount: number;
  
  // USD values (null if enrichment missing)
  inUsd: number | null;
  outUsd: number | null;
  netUsd: number | null;
  
  // Stable breakdown
  stableInUsd: number | null;
  stableOutUsd: number | null;
  stableNetUsd: number | null;
  
  // Whale breakdown
  whaleInUsd: number | null;
  whaleOutUsd: number | null;
  whaleNetUsd: number | null;
}

export interface BridgeByBridge {
  inCount: number;
  outCount: number;
  netCount: number;
  inUsd: number | null;
  outUsd: number | null;
  netUsd: number | null;
}

export interface BridgeScore {
  value: number;      // 0..100
  regime: string;
  confidence: number; // 0..1
}

export interface IBridgeAggregate extends Document {
  chainId: number;
  window: BridgeAggWindow;
  bucketTs: number;
  computedAt: number;
  
  metrics: BridgeMetrics;
  byBridge: Record<string, BridgeByBridge>;
  
  score: BridgeScore;
  drivers: string[];
  flags: string[];
}

// ═══════════════════════════════════════════════════════════════
// SCHEMA
// ═══════════════════════════════════════════════════════════════

const ByBridgeSchema = new Schema(
  {
    inCount: { type: Number, required: true, default: 0 },
    outCount: { type: Number, required: true, default: 0 },
    netCount: { type: Number, required: true, default: 0 },
    inUsd: { type: Number, default: null },
    outUsd: { type: Number, default: null },
    netUsd: { type: Number, default: null },
  },
  { _id: false }
);

const BridgeAggregateSchema = new Schema<IBridgeAggregate>(
  {
    chainId: { type: Number, required: true, default: 1, index: true },
    window: { type: String, required: true, enum: ['24h', '7d'] },
    bucketTs: { type: Number, required: true, index: true },
    computedAt: { type: Number, required: true },
    
    metrics: {
      inCount: { type: Number, required: true, default: 0 },
      outCount: { type: Number, required: true, default: 0 },
      netCount: { type: Number, required: true, default: 0 },
      
      inUsd: { type: Number, default: null },
      outUsd: { type: Number, default: null },
      netUsd: { type: Number, default: null },
      
      stableInUsd: { type: Number, default: null },
      stableOutUsd: { type: Number, default: null },
      stableNetUsd: { type: Number, default: null },
      
      whaleInUsd: { type: Number, default: null },
      whaleOutUsd: { type: Number, default: null },
      whaleNetUsd: { type: Number, default: null },
    },
    
    byBridge: { type: Schema.Types.Mixed, required: true, default: {} },
    
    score: {
      value: { type: Number, required: true, default: 50 },
      regime: { type: String, required: true, default: 'NEUTRAL' },
      confidence: { type: Number, required: true, default: 0 },
    },
    
    drivers: { type: [String], required: true, default: [] },
    flags: { type: [String], required: true, default: [] },
  },
  {
    timestamps: true,
    collection: 'onchain_v2_bridge_aggregates',
  }
);

// Idempotency: unique per chain+window+bucket
BridgeAggregateSchema.index({ chainId: 1, window: 1, bucketTs: 1 }, { unique: true });

// Time queries
BridgeAggregateSchema.index({ chainId: 1, window: 1, bucketTs: -1 });

// ═══════════════════════════════════════════════════════════════
// MODEL
// ═══════════════════════════════════════════════════════════════

export const BridgeAggregateModel: Model<IBridgeAggregate> = mongoose.model<IBridgeAggregate>(
  'OnchainV2BridgeAggregate',
  BridgeAggregateSchema
);

console.log('[OnChain V2] Bridge Aggregate Model loaded');
