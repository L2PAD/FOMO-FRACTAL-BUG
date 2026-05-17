/**
 * OnChain V2 — Baseline Model
 * =============================
 * 
 * Stores baseline score distributions for PSI drift calculation.
 */

import mongoose, { Schema, Document } from 'mongoose';

export interface IBaseline extends Document {
  // Identity
  chainId: number;
  symbol: string;
  metric: 'score' | 'confidence' | 'dexActivity';
  version: number;
  
  // Metadata
  createdAt: number;
  sampleCount: number;
  sourceWindow: '7d' | '30d' | '90d';
  
  // Distribution
  distribution: {
    buckets: number[];      // Normalized ratios (sum = 1)
    bucketSize: number;     // 0.1 for 10 buckets
    rawBuckets: number[];   // Original counts
  };
  
  // Stats at baseline creation
  stats: {
    avgScore: number;
    stdScore: number;
    medianScore: number;
  };
  
  // Active flag
  active: boolean;
}

const BaselineSchema = new Schema<IBaseline>({
  chainId: { type: Number, required: true, default: 1, index: true },
  symbol: { type: String, required: true, index: true },
  metric: { type: String, required: true, enum: ['score', 'confidence', 'dexActivity'] },
  version: { type: Number, required: true, default: 1 },
  
  createdAt: { type: Number, required: true },
  sampleCount: { type: Number, required: true },
  sourceWindow: { type: String, required: true },
  
  distribution: {
    buckets: { type: [Number], required: true },
    bucketSize: { type: Number, required: true },
    rawBuckets: { type: [Number], required: true },
  },
  
  stats: {
    avgScore: { type: Number, default: 0 },
    stdScore: { type: Number, default: 0 },
    medianScore: { type: Number, default: 0 },
  },
  
  active: { type: Boolean, default: true },
}, {
  collection: 'onchain_v2_baselines',
  timestamps: false,
});

// Unique per chain/symbol/metric, only one active version
BaselineSchema.index({ chainId: 1, symbol: 1, metric: 1, active: 1 });
BaselineSchema.index({ chainId: 1, symbol: 1, metric: 1, version: 1 }, { unique: true });

export const BaselineModel = mongoose.model<IBaseline>('OnchainV2Baseline', BaselineSchema, 'onchain_v2_baselines');

console.log('[OnChain V2] Baseline Model loaded');
