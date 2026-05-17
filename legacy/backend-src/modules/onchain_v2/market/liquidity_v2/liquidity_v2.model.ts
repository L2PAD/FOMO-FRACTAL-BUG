/**
 * OnChain V2 — LiquidityScore v2 Model
 * ======================================
 * 
 * BLOCK 7: MongoDB schema for LARE v2 time series.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import type { LareV2Regime, LareV2Window } from './liquidity_v2.contracts.js';
import type { NormalizedSignal } from '../../normalization/normalizer.types.js';

// ═══════════════════════════════════════════════════════════════
// DOCUMENT INTERFACE
// ═══════════════════════════════════════════════════════════════

export interface ILareV2 extends Document {
  chainId: number;
  window: LareV2Window;
  bucketTs: number;
  version: string;
  
  score: number;
  confidence: number;
  regime: LareV2Regime;
  
  gate: {
    riskCap: number;
    allowAggressiveRisk: boolean;
    blockNewPositions: boolean;
    reason: string;
  };
  
  components: NormalizedSignal[];
  drivers: string[];
  flags: string[];
  
  createdAt: Date;
  updatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// SCHEMA
// ═══════════════════════════════════════════════════════════════

const LareV2Schema = new Schema<ILareV2>(
  {
    chainId: {
      type: Number,
      required: true,
      default: 1,
      index: true,
    },
    window: { 
      type: String, 
      required: true, 
      enum: ['24h', '7d'],
      index: true,
    },
    bucketTs: { 
      type: Number, 
      required: true, 
      index: true,
    },
    version: { 
      type: String, 
      required: true,
    },
    
    score: { 
      type: Number, 
      required: true,
      index: true,
    },
    confidence: { 
      type: Number, 
      required: true,
    },
    regime: { 
      type: String, 
      required: true,
      enum: ['RISK_ON_ALTS', 'MODERATE_RISK_ON', 'NEUTRAL', 'MODERATE_RISK_OFF', 'RISK_OFF'],
      index: true,
    },
    
    gate: {
      riskCap: { type: Number, required: true },
      allowAggressiveRisk: { type: Boolean, required: true },
      blockNewPositions: { type: Boolean, required: true },
      reason: { type: String, required: true },
    },
    
    components: { 
      type: Schema.Types.Mixed, 
      required: true, 
      default: [],
    },
    drivers: { 
      type: [String], 
      default: [],
    },
    flags: { 
      type: [String], 
      default: [],
    },
  },
  {
    timestamps: true,
    collection: 'onchain_v2_liquidity_v2',
  }
);

// ═══════════════════════════════════════════════════════════════
// INDEXES
// ═══════════════════════════════════════════════════════════════

// Idempotency: one record per chain+window+bucket
LareV2Schema.index({ chainId: 1, window: 1, bucketTs: 1 }, { unique: true });

// Time series queries
LareV2Schema.index({ chainId: 1, window: 1, bucketTs: -1 });

// Regime analysis
LareV2Schema.index({ chainId: 1, regime: 1, bucketTs: -1 });

// ═══════════════════════════════════════════════════════════════
// MODEL
// ═══════════════════════════════════════════════════════════════

export const LareV2Model: Model<ILareV2> = mongoose.model<ILareV2>(
  'OnchainV2LareV2',
  LareV2Schema
);

console.log('[OnChain V2] LiquidityScore v2 model loaded');
