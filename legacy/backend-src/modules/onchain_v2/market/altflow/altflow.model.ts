/**
 * Alt Flow Model
 * ===============
 * 
 * BLOCK 3.6: Alt Flow Ranking persistence
 */

import mongoose from 'mongoose';

const AltFlowPointSchema = new mongoose.Schema(
  {
    chainId: { type: Number, required: true, default: 1, index: true },
    t: { type: Number, index: true, required: true },
    window: { type: String, index: true, required: true }, // "24h" | "7d"
    symbol: { type: String, index: true, required: true },

    // Core flow metrics (USD)
    cexNetUsd: { type: Number, default: 0 },   // inflow - outflow to exchanges
    dexNetUsd: { type: Number, default: 0 },   // buy - sell on DEX
    whaleUsd: { type: Number, default: 0 },    // total whale volume

    // Derived signals
    score: { type: Number, default: 0 },       // [-1..+1] composite
    confidence: { type: Number, default: 0 },  // [0..1]
    drivers: { type: [String], default: [] },
    flags: { type: [mongoose.Schema.Types.Mixed], default: [] },

    // PHASE 2.2: Quality metadata
    quality: {
      priceSource: { type: String, default: 'NONE' },       // CHAINLINK | TWAP | DEX_VWAP | NONE
      priceConfidence: { type: Number, default: null },
      poolStatus: { type: String, default: 'UNKNOWN' },      // ACTIVE | DEGRADED | DISABLED | UNKNOWN
      poolScore: { type: Number, default: 0 },
    },

    // PHASE 2.2: Evidence metadata
    evidence: {
      trades: { type: Number, default: 0 },
      uniquePools: { type: Number, default: 0 },
      spanHours: { type: Number, default: 0 },
      pricedShare: { type: Number, default: 0 },              // 0..1
      pricedCount: { type: Number, default: 0 },
    },

    // PHASE 2.2: Model features (for explainability, calibration, ML)
    modelFeatures: {
      poolScore: { type: Number, default: null },
      poolStatus: { type: String, default: null },
      tvlUsd: { type: Number, default: null },
      priceReliability: { type: Number, default: null },      // 0..1
      usdSource: { type: String, default: null },
      pricedShare: { type: Number, default: null },           // 0..1
      evidenceCount: { type: Number, default: null },
    },
  },
  { 
    collection: 'onchain_v2_altflow_points',
    timestamps: true,
  }
);

// Compound index for efficient queries (chain-aware)
AltFlowPointSchema.index({ chainId: 1, window: 1, t: -1, symbol: 1 }, { unique: true });
AltFlowPointSchema.index({ chainId: 1, window: 1, score: -1 });

export const AltFlowPointModel = mongoose.model('AltFlowPoint', AltFlowPointSchema);

console.log('[AltFlow] Model loaded');
