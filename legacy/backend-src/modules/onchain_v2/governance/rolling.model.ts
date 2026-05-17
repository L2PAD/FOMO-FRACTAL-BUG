/**
 * OnChain V2 — Rolling Stats Model
 * ==================================
 * 
 * 30-day rolling statistics for institutional governance.
 * Used for guardrails, drift detection, and confidence smoothing.
 */

import mongoose, { Schema, Document } from 'mongoose';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type RollingWindow = '7d' | '30d' | '90d';

export interface ScoreDistribution {
  buckets: number[];      // Count per bucket (10 buckets)
  bucketSize: number;     // 0.1 for 10 buckets
  totalSamples: number;
}

export interface RollingHealth {
  sufficientSamples: boolean;   // sampleCount >= minSamples
  stableVariance: boolean;      // stdScore within acceptable range
  recentActivity: boolean;      // has samples in last 24h
}

export interface IRollingStats extends Document {
  // Identity
  symbol: string;
  window: RollingWindow;
  chainId: number;
  
  // Computation metadata
  computedAt: number;
  computedFromTs: number;
  computedToTs: number;
  
  // Sample stats
  sampleCount: number;
  
  // Score statistics
  avgScore: number;
  stdScore: number;
  minScore: number;
  maxScore: number;
  medianScore: number;
  
  // Confidence statistics
  avgConfidence: number;
  stdConfidence: number;
  minConfidence: number;
  maxConfidence: number;
  
  // DEX statistics
  dexActivityAvg: number;
  dexImbalanceAvg: number;
  dexSwapCountAvg: number;
  
  // State distribution
  stateDistribution: {
    ACCUMULATION: number;
    DISTRIBUTION: number;
    NEUTRAL: number;
    LOW_CONF: number;
    NO_DATA: number;
  };
  
  // Score distribution (for PSI drift)
  scoreDistribution: ScoreDistribution;
  
  // Derived health indicators
  health: RollingHealth;
  
  // Thresholds (configurable per symbol)
  thresholds: {
    minSamples: number;
    maxStdScore: number;
    minAvgConfidence: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// SCHEMA
// ═══════════════════════════════════════════════════════════════

const RollingStatsSchema = new Schema<IRollingStats>({
  symbol: { type: String, required: true, index: true },
  window: { type: String, required: true, enum: ['7d', '30d', '90d'] },
  chainId: { type: Number, required: true, default: 1 },
  
  computedAt: { type: Number, required: true },
  computedFromTs: { type: Number, required: true },
  computedToTs: { type: Number, required: true },
  
  sampleCount: { type: Number, required: true, default: 0 },
  
  avgScore: { type: Number, default: 0 },
  stdScore: { type: Number, default: 0 },
  minScore: { type: Number, default: 0 },
  maxScore: { type: Number, default: 0 },
  medianScore: { type: Number, default: 0 },
  
  avgConfidence: { type: Number, default: 0 },
  stdConfidence: { type: Number, default: 0 },
  minConfidence: { type: Number, default: 0 },
  maxConfidence: { type: Number, default: 0 },
  
  dexActivityAvg: { type: Number, default: 0 },
  dexImbalanceAvg: { type: Number, default: 0 },
  dexSwapCountAvg: { type: Number, default: 0 },
  
  stateDistribution: {
    ACCUMULATION: { type: Number, default: 0 },
    DISTRIBUTION: { type: Number, default: 0 },
    NEUTRAL: { type: Number, default: 0 },
    LOW_CONF: { type: Number, default: 0 },
    NO_DATA: { type: Number, default: 0 },
  },
  
  scoreDistribution: {
    buckets: { type: [Number], default: () => new Array(10).fill(0) },
    bucketSize: { type: Number, default: 0.1 },  // 0-0.1, 0.1-0.2, etc for score 0-1
    totalSamples: { type: Number, default: 0 },
  },
  
  health: {
    sufficientSamples: { type: Boolean, default: false },
    stableVariance: { type: Boolean, default: false },
    recentActivity: { type: Boolean, default: false },
  },
  
  thresholds: {
    minSamples: { type: Number, default: 200 },
    maxStdScore: { type: Number, default: 25 },
    minAvgConfidence: { type: Number, default: 0.35 },
  },
}, {
  collection: 'onchain_v2_rolling_stats',
  timestamps: false,
});

// Unique index
RollingStatsSchema.index({ symbol: 1, window: 1, chainId: 1 }, { unique: true });

export const RollingStatsModel = mongoose.model<IRollingStats>('OnchainV2RollingStats', RollingStatsSchema, 'onchain_v2_rolling_stats');

console.log('[OnChain V2] Rolling Stats Model loaded');
