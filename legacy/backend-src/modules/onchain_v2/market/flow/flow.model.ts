/**
 * OnChain V2 — Token Flow Model
 * ==============================
 * 
 * PHASE 3.5: Normalized token flow events from DEX/CEX/ERC20
 * Used for AltFlow aggregation
 */

import mongoose, { Schema, Document } from 'mongoose';

// ═══════════════════════════════════════════════════════════════
// TOKEN FLOW EVENT
// ═══════════════════════════════════════════════════════════════

export type FlowSide = 'BUY' | 'SELL';
export type FlowSource = 'dex' | 'cex' | 'bridge' | 'transfer';

export interface ITokenFlow extends Document {
  chainId: number;
  tokenAddress: string;
  tokenSymbol?: string;
  
  side: FlowSide;
  usdVolume: number;
  tokenVolume?: number;
  
  source: FlowSource;
  poolAddress?: string;  // for DEX
  counterparty?: string; // CEX address for in/out
  
  // P0.7: Entity attribution for counterparty
  counterpartyEntityId?: string;
  counterpartyEntityName?: string;
  counterpartyEntityType?: string;
  counterpartyAttributionSource?: string;
  
  blockNumber: number;
  blockTime: number;
  txHash: string;
  logIndex?: number;
  
  isWhale: boolean;
  
  indexedAt: number;
}

const TokenFlowSchema = new Schema<ITokenFlow>({
  chainId: { type: Number, required: true, index: true },
  tokenAddress: { type: String, required: true, lowercase: true, index: true },
  tokenSymbol: { type: String },
  
  side: { type: String, enum: ['BUY', 'SELL'], required: true, index: true },
  usdVolume: { type: Number, required: true },
  tokenVolume: { type: Number },
  
  source: { type: String, enum: ['dex', 'cex', 'bridge', 'transfer'], required: true },
  poolAddress: { type: String, lowercase: true },
  counterparty: { type: String, lowercase: true },
  
  // P0.7: Entity attribution for counterparty
  counterpartyEntityId: { type: String, index: true },
  counterpartyEntityName: { type: String },
  counterpartyEntityType: { type: String },
  counterpartyAttributionSource: { type: String },
  
  blockNumber: { type: Number, required: true },
  blockTime: { type: Number, required: true, index: true },
  txHash: { type: String, required: true },
  logIndex: { type: Number },
  
  isWhale: { type: Boolean, default: false },
  
  indexedAt: { type: Number, required: true, default: () => Date.now() },
}, {
  collection: 'onchain_v2_token_flows',
  timestamps: false,
});

// Indexes
TokenFlowSchema.index({ chainId: 1, txHash: 1, logIndex: 1 }, { unique: true, sparse: true });
TokenFlowSchema.index({ chainId: 1, tokenAddress: 1, blockTime: -1 });
TokenFlowSchema.index({ chainId: 1, blockTime: -1 });
TokenFlowSchema.index({ chainId: 1, source: 1, blockTime: -1 });

export const TokenFlowModel = mongoose.model<ITokenFlow>('OnchainV2TokenFlow', TokenFlowSchema);

console.log('[OnChain V2] Token Flow Model loaded');
