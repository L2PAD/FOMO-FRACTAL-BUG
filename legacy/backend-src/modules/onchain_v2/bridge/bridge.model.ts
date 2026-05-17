/**
 * OnChain V2 — Bridge Event Model
 * =================================
 * 
 * Persistent storage for bridge events (L1↔L2 migrations).
 * Idempotent: unique(chainId, txHash, logIndex)
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

// ═══════════════════════════════════════════════════════════════
// INTERFACE
// ═══════════════════════════════════════════════════════════════

export interface IBridgeEvent extends Document {
  // Identity
  chainId: number;
  txHash: string;
  logIndex: number;
  blockNumber: number;
  
  // Bridge info
  bridge: string;           // ARBITRUM | OPTIMISM | BASE
  trackId: string;          // e.g. OPTIMISM_L1_TO_L2_L1
  direction: string;        // L1_TO_L2 | L2_TO_L1
  
  // Event data
  contractAddress: string;
  eventName: string;
  
  // Token info
  tokenAddress: string;
  tokenSymbol?: string;
  amountRaw: string;        // BigInt as string
  amountNorm?: number;      // Normalized amount (with decimals)
  
  // USD value (enriched later)
  usdValue?: number;
  usdSource?: string;       // COINGECKO | DEX_TWAP | STABLE
  
  // Participants
  sender: string;
  receiver?: string;
  
  // Flags
  isStable: boolean;
  isWhale: boolean;
  
  // Timestamps
  timestamp: number;        // Block timestamp or ingestion time
  createdAt: Date;
  updatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// SCHEMA
// ═══════════════════════════════════════════════════════════════

const BridgeEventSchema = new Schema<IBridgeEvent>(
  {
    // Identity
    chainId: { type: Number, required: true, index: true },
    txHash: { type: String, required: true },
    logIndex: { type: Number, required: true },
    blockNumber: { type: Number, required: true, index: true },
    
    // Bridge info
    bridge: { type: String, required: true, index: true },
    trackId: { type: String, required: true, index: true },
    direction: { 
      type: String, 
      required: true, 
      enum: ['L1_TO_L2', 'L2_TO_L1'],
      index: true,
    },
    
    // Event data
    contractAddress: { type: String, required: true },
    eventName: { type: String, required: true },
    
    // Token info
    tokenAddress: { type: String, required: true, index: true },
    tokenSymbol: { type: String },
    amountRaw: { type: String, required: true },
    amountNorm: { type: Number },
    
    // USD value
    usdValue: { type: Number, index: true },
    usdSource: { type: String },
    
    // Participants
    sender: { type: String, required: true, index: true },
    receiver: { type: String },
    
    // Flags
    isStable: { type: Boolean, default: false, index: true },
    isWhale: { type: Boolean, default: false, index: true },
    
    // Timestamps
    timestamp: { type: Number, required: true, index: true },
  },
  {
    timestamps: true,
    collection: 'onchain_v2_bridge_events',
  }
);

// ═══════════════════════════════════════════════════════════════
// INDEXES
// ═══════════════════════════════════════════════════════════════

// Idempotency: unique per chain/tx/log
BridgeEventSchema.index(
  { chainId: 1, txHash: 1, logIndex: 1 },
  { unique: true }
);

// Aggregation queries
BridgeEventSchema.index({ bridge: 1, direction: 1, timestamp: -1 });
BridgeEventSchema.index({ direction: 1, timestamp: -1 });
BridgeEventSchema.index({ isWhale: 1, timestamp: -1 });
BridgeEventSchema.index({ isStable: 1, timestamp: -1 });

// Time range queries
BridgeEventSchema.index({ timestamp: -1 });

// ═══════════════════════════════════════════════════════════════
// MODEL
// ═══════════════════════════════════════════════════════════════

export const BridgeEventModel: Model<IBridgeEvent> = mongoose.model<IBridgeEvent>(
  'OnchainV2BridgeEvent',
  BridgeEventSchema
);

console.log('[OnChain V2] Bridge Event Model loaded');
