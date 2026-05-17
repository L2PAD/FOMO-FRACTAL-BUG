/**
 * OnChain V2 — Stablecoin Mint/Burn Model
 * =========================================
 * 
 * Tracks USDT/USDC mint and burn events.
 * Idempotent: unique(chainId, txHash, logIndex)
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type StableToken = 'USDT' | 'USDC' | 'DAI' | 'UNKNOWN';
export type MintBurnDirection = 'MINT' | 'BURN';

export interface IStableMintBurn extends Document {
  chainId: number;
  token: StableToken;
  tokenAddress: string;
  
  blockNumber: number;
  timestamp: number;
  
  txHash: string;
  logIndex: number;
  
  direction: MintBurnDirection;
  rawAmount: string;
  amount: number | null;      // Normalized (with decimals)
  usdAmount: number | null;   // USD value (~1:1 for stables)
  
  // Participant (minter/burner)
  participant: string;
  
  // Metadata
  decimals: number;
  
  createdAt: Date;
  updatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// SCHEMA
// ═══════════════════════════════════════════════════════════════

const StableMintBurnSchema = new Schema<IStableMintBurn>(
  {
    chainId: { type: Number, required: true, index: true },
    token: { type: String, required: true, index: true },
    tokenAddress: { type: String, required: true, index: true },
    
    blockNumber: { type: Number, required: true, index: true },
    timestamp: { type: Number, required: true, index: true },
    
    txHash: { type: String, required: true },
    logIndex: { type: Number, required: true },
    
    direction: { 
      type: String, 
      required: true, 
      enum: ['MINT', 'BURN'],
      index: true,
    },
    rawAmount: { type: String, required: true },
    amount: { type: Number, default: null },
    usdAmount: { type: Number, default: null, index: true },
    
    participant: { type: String, required: true, index: true },
    
    decimals: { type: Number, required: true, default: 6 },
  },
  {
    timestamps: true,
    collection: 'onchain_v2_stable_mintburn',
  }
);

// ═══════════════════════════════════════════════════════════════
// INDEXES
// ═══════════════════════════════════════════════════════════════

// Idempotency
StableMintBurnSchema.index(
  { chainId: 1, txHash: 1, logIndex: 1 },
  { unique: true }
);

// Aggregation queries
StableMintBurnSchema.index({ token: 1, direction: 1, timestamp: -1 });
StableMintBurnSchema.index({ direction: 1, timestamp: -1 });

// Time range
StableMintBurnSchema.index({ timestamp: -1 });

// ═══════════════════════════════════════════════════════════════
// MODEL
// ═══════════════════════════════════════════════════════════════

export const StableMintBurnModel: Model<IStableMintBurn> = mongoose.model<IStableMintBurn>(
  'OnchainV2StableMintBurn',
  StableMintBurnSchema
);

console.log('[OnChain V2] Stable Mint/Burn Model loaded');
