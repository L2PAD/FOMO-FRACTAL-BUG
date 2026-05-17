/**
 * OnChain V2 — Stablecoin Aggregation Model
 * ==========================================
 * 
 * Stores computed mint/burn aggregates per time window.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type StableAggWindow = '24h' | '7d' | '30d';

export interface StableMetrics {
  mintCount: number;
  burnCount: number;
  
  mintAmount: number;      // Token units
  burnAmount: number;
  netAmount: number;
  
  mintUsd: number | null;  // USD value (~1:1)
  burnUsd: number | null;
  netUsd: number | null;
}

export interface StableScore {
  value: number;       // 0..100
  regime: string;      // SUPPLY_EXPANDING | SUPPLY_CONTRACTING | NEUTRAL
  confidence: number;  // 0..1
}

export interface IStableAggregate extends Document {
  chainId: number;
  window: StableAggWindow;
  bucketTs: number;
  computedAt: number;
  
  chainsCovered: number;
  metrics: StableMetrics;
  
  byToken: Record<string, {
    mintCount: number;
    burnCount: number;
    mintAmount: number;
    burnAmount: number;
    netAmount: number;
  }>;
  
  score: StableScore;
  drivers: string[];
  flags: string[];
}

// ═══════════════════════════════════════════════════════════════
// SCHEMA
// ═══════════════════════════════════════════════════════════════

const StableAggregateSchema = new Schema<IStableAggregate>(
  {
    chainId: { type: Number, required: true, default: 1, index: true },
    window: { type: String, required: true, enum: ['24h', '7d', '30d'] },
    bucketTs: { type: Number, required: true, index: true },
    computedAt: { type: Number, required: true },
    
    chainsCovered: { type: Number, required: true, default: 0 },
    
    metrics: {
      mintCount: { type: Number, required: true, default: 0 },
      burnCount: { type: Number, required: true, default: 0 },
      mintAmount: { type: Number, required: true, default: 0 },
      burnAmount: { type: Number, required: true, default: 0 },
      netAmount: { type: Number, required: true, default: 0 },
      mintUsd: { type: Number, default: null },
      burnUsd: { type: Number, default: null },
      netUsd: { type: Number, default: null },
    },
    
    byToken: { type: Schema.Types.Mixed, required: true, default: {} },
    
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
    collection: 'onchain_v2_stable_aggregates',
  }
);

// Idempotency (chain-aware)
StableAggregateSchema.index({ chainId: 1, window: 1, bucketTs: 1 }, { unique: true });

// Time queries
StableAggregateSchema.index({ chainId: 1, window: 1, bucketTs: -1 });

// ═══════════════════════════════════════════════════════════════
// MODEL
// ═══════════════════════════════════════════════════════════════

export const StableAggregateModel: Model<IStableAggregate> = mongoose.model<IStableAggregate>(
  'OnchainV2StableAggregate',
  StableAggregateSchema
);

console.log('[OnChain V2] Stable Aggregate Model loaded');
