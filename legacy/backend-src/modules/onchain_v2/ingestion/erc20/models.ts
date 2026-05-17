/**
 * OnChain V2 — ERC20 Indexer Models
 * ===================================
 * 
 * MongoDB models for ERC20 transfer logs and sync state.
 */

import mongoose, { Schema, Document } from 'mongoose';

// Import type only
import type { RpcChainId } from '../../rpc-pool/models.js';
export type { RpcChainId } from '../../rpc-pool/models.js';

// ═══════════════════════════════════════════════════════════════
// ERC20 TRANSFER LOG
// ═══════════════════════════════════════════════════════════════

export interface IERC20Log extends Document {
  chainId: RpcChainId;
  blockNumber: number;
  blockHash: string;
  transactionHash: string;
  transactionIndex: number;
  logIndex: number;
  
  tokenAddress: string;
  from: string;
  to: string;
  value: string;  // BigInt as string
  
  // Computed fields (populated later)
  valueNormalized?: number;  // Divided by decimals
  valueUsd?: number;
  tokenSymbol?: string;
  tokenDecimals?: number;
  
  // Labels
  fromLabel?: string;  // 'exchange:binance', 'whale', etc
  toLabel?: string;
  
  // Timestamps
  blockTimestamp?: number;
  indexedAt: number;
}

const ERC20LogSchema = new Schema<IERC20Log>({
  chainId: { type: Number, required: true, index: true },
  blockNumber: { type: Number, required: true, index: true },
  blockHash: { type: String, required: true },
  transactionHash: { type: String, required: true, index: true },
  transactionIndex: { type: Number, required: true },
  logIndex: { type: Number, required: true },
  
  tokenAddress: { type: String, required: true, lowercase: true, index: true },
  from: { type: String, required: true, lowercase: true, index: true },
  to: { type: String, required: true, lowercase: true, index: true },
  value: { type: String, required: true },
  
  valueNormalized: { type: Number },
  valueUsd: { type: Number },
  tokenSymbol: { type: String },
  tokenDecimals: { type: Number },
  
  fromLabel: { type: String, index: true },
  toLabel: { type: String, index: true },
  
  blockTimestamp: { type: Number, index: true },
  indexedAt: { type: Number, required: true, default: () => Date.now() },
}, {
  collection: 'onchain_v2_erc20_logs',
  timestamps: false,
});

// Unique index for idempotency
ERC20LogSchema.index({ chainId: 1, transactionHash: 1, logIndex: 1 }, { unique: true });

// Query indexes
ERC20LogSchema.index({ chainId: 1, tokenAddress: 1, blockNumber: -1 });
ERC20LogSchema.index({ chainId: 1, blockTimestamp: -1 });

export const ERC20LogModel = mongoose.model<IERC20Log>('OnchainV2ERC20Log', ERC20LogSchema);

// ═══════════════════════════════════════════════════════════════
// SYNC STATE
// ═══════════════════════════════════════════════════════════════

export interface ISyncState extends Document {
  key: string;  // e.g., 'erc20_eth', 'erc20_arb'
  chainId: RpcChainId;
  lastBlock: number;
  lastBlockTimestamp?: number;
  lastSyncAt: number;
  totalLogsIndexed: number;
  status: 'idle' | 'syncing' | 'backfilling' | 'error';
  lastError?: string;
  lastErrorAt?: number;
}

const SyncStateSchema = new Schema<ISyncState>({
  key: { type: String, required: true, unique: true },
  chainId: { type: Number, required: true },
  lastBlock: { type: Number, required: true, default: 0 },
  lastBlockTimestamp: { type: Number },
  lastSyncAt: { type: Number, required: true, default: () => Date.now() },
  totalLogsIndexed: { type: Number, default: 0 },
  status: { 
    type: String, 
    enum: ['idle', 'syncing', 'backfilling', 'error'],
    default: 'idle',
  },
  lastError: { type: String },
  lastErrorAt: { type: Number },
}, {
  collection: 'onchain_v2_sync_states',
  timestamps: false,
});

export const SyncStateModel = mongoose.model<ISyncState>('OnchainV2SyncState', SyncStateSchema);

// ═══════════════════════════════════════════════════════════════
// TOKEN METADATA
// ═══════════════════════════════════════════════════════════════

export interface ITokenMetadata extends Document {
  chainId: RpcChainId;
  address: string;
  symbol: string;
  name: string;
  decimals: number;
  isStable?: boolean;
  priceUsd?: number;
  priceUpdatedAt?: number;
}

const TokenMetadataSchema = new Schema<ITokenMetadata>({
  chainId: { type: Number, required: true },
  address: { type: String, required: true, lowercase: true },
  symbol: { type: String, required: true },
  name: { type: String },
  decimals: { type: Number, required: true, default: 18 },
  isStable: { type: Boolean, default: false },
  priceUsd: { type: Number },
  priceUpdatedAt: { type: Number },
}, {
  collection: 'onchain_v2_tokens',
  timestamps: false,
});

TokenMetadataSchema.index({ chainId: 1, address: 1 }, { unique: true });
TokenMetadataSchema.index({ chainId: 1, symbol: 1 });

export const TokenMetadataModel = mongoose.model<ITokenMetadata>('OnchainV2Token', TokenMetadataSchema);

// ═══════════════════════════════════════════════════════════════
// ADDRESS LABELS
// ═══════════════════════════════════════════════════════════════

export type AddressLabelType = 
  | 'exchange' 
  | 'whale' 
  | 'smart_money' 
  | 'dex' 
  | 'bridge' 
  | 'contract' 
  | 'defi'
  | 'nft'
  | 'other';

export interface IAddressLabel extends Document {
  chainId: RpcChainId;
  address: string;
  type: AddressLabelType;
  name: string;  // 'binance', 'uniswap_v3', etc
  subtype?: string;  // 'hot_wallet', 'cold_wallet', etc
  source: string;  // 'manual', 'etherscan', 'arkham', etc
  confidence: number;  // 0-1
  updatedAt: number;
}

const AddressLabelSchema = new Schema<IAddressLabel>({
  chainId: { type: Number, required: true },
  address: { type: String, required: true, lowercase: true },
  type: { 
    type: String, 
    required: true,
    enum: ['exchange', 'whale', 'smart_money', 'dex', 'bridge', 'contract', 'defi', 'nft', 'other'],
  },
  name: { type: String, required: true },
  subtype: { type: String },
  source: { type: String, required: true, default: 'manual' },
  confidence: { type: Number, default: 1.0 },
  updatedAt: { type: Number, default: () => Date.now() },
}, {
  collection: 'onchain_v2_address_labels',
  timestamps: false,
});

AddressLabelSchema.index({ chainId: 1, address: 1 }, { unique: true });
AddressLabelSchema.index({ chainId: 1, type: 1 });

export const AddressLabelModel = mongoose.model<IAddressLabel>('OnchainV2AddressLabel', AddressLabelSchema);

console.log('[OnChain V2] ERC20 Indexer Models loaded');
