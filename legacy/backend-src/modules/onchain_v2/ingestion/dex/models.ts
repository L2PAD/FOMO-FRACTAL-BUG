/**
 * OnChain V2 — DEX Swap Models
 * =============================
 * 
 * MongoDB models for DEX swap events (Uniswap V3, etc.)
 */

import mongoose, { Schema, Document } from 'mongoose';
import type { RpcChainId } from '../../rpc-pool/models.js';

// ═══════════════════════════════════════════════════════════════
// DEX SWAP LOG
// ═══════════════════════════════════════════════════════════════

export type DexProtocol = 'uniswap_v3' | 'uniswap_v2' | 'sushiswap' | 'curve' | 'balancer';

export interface IDexSwap extends Document {
  chainId: RpcChainId;
  protocol: DexProtocol;
  
  // Pool / pair info
  pool: string;  // Pool/pair contract address
  token0: string;
  token1: string;
  
  // Swap amounts (as strings for BigInt precision)
  amount0: string;  // Can be negative (Uniswap V3)
  amount1: string;  // Can be negative (Uniswap V3)
  
  // Transaction info
  blockNumber: number;
  blockTimestamp?: number;
  transactionHash: string;
  transactionIndex: number;
  logIndex: number;
  
  // Participants
  sender: string;
  recipient: string;
  
  // Uniswap V3 specific
  sqrtPriceX96?: string;
  liquidity?: string;
  tick?: number;
  
  // Computed fields (populated later)
  token0Symbol?: string;
  token1Symbol?: string;
  amount0Normalized?: number;
  amount1Normalized?: number;
  volumeUsd?: number;
  
  // Direction analysis
  direction?: 'buy' | 'sell' | 'unknown';  // Relative to token0
  isWhaleSwap?: boolean;
  
  // Indexing metadata
  indexedAt: number;
}

const DexSwapSchema = new Schema<IDexSwap>({
  chainId: { type: Number, required: true, index: true },
  protocol: { 
    type: String, 
    required: true, 
    enum: ['uniswap_v3', 'uniswap_v2', 'sushiswap', 'curve', 'balancer'],
    index: true,
  },
  
  pool: { type: String, required: true, lowercase: true, index: true },
  token0: { type: String, required: true, lowercase: true, index: true },
  token1: { type: String, required: true, lowercase: true, index: true },
  
  amount0: { type: String, required: true },
  amount1: { type: String, required: true },
  
  blockNumber: { type: Number, required: true, index: true },
  blockTimestamp: { type: Number, index: true },
  transactionHash: { type: String, required: true, index: true },
  transactionIndex: { type: Number, required: true },
  logIndex: { type: Number, required: true },
  
  sender: { type: String, required: true, lowercase: true },
  recipient: { type: String, required: true, lowercase: true },
  
  // V3 specific
  sqrtPriceX96: { type: String },
  liquidity: { type: String },
  tick: { type: Number },
  
  // Computed
  token0Symbol: { type: String },
  token1Symbol: { type: String },
  amount0Normalized: { type: Number },
  amount1Normalized: { type: Number },
  volumeUsd: { type: Number },
  
  direction: { type: String, enum: ['buy', 'sell', 'unknown'] },
  isWhaleSwap: { type: Boolean, default: false },
  
  indexedAt: { type: Number, required: true, default: () => Date.now() },
}, {
  collection: 'onchain_v2_dex_swaps',
  timestamps: false,
});

// Unique index for idempotency
DexSwapSchema.index({ chainId: 1, transactionHash: 1, logIndex: 1 }, { unique: true });

// Query indexes
DexSwapSchema.index({ chainId: 1, pool: 1, blockNumber: -1 });
DexSwapSchema.index({ chainId: 1, blockTimestamp: -1 });
DexSwapSchema.index({ chainId: 1, protocol: 1, blockNumber: -1 });

export const DexSwapModel = mongoose.model<IDexSwap>('OnchainV2DexSwap', DexSwapSchema);

// ═══════════════════════════════════════════════════════════════
// DEX POOL METADATA
// ═══════════════════════════════════════════════════════════════

export interface IDexPool extends Document {
  chainId: RpcChainId;
  protocol: DexProtocol;
  address: string;
  
  token0: string;
  token1: string;
  token0Symbol?: string;
  token1Symbol?: string;
  token0Decimals?: number;
  token1Decimals?: number;
  
  // Uniswap V3 specific
  fee?: number;  // 500, 3000, 10000 (0.05%, 0.3%, 1%)
  
  // Tracking
  enabled: boolean;
  priority: number;  // Higher = index first
  lastSwapBlock?: number;
  lastSwapAt?: number;  // STEP 2: timestamp of last swap
  totalSwapsIndexed: number;
  
  // STEP 2: Status lifecycle
  status?: 'CANDIDATE' | 'ACTIVE' | 'DEGRADED' | 'DISABLED';
  statusReason?: string;
  
  // STEP 2: Scoring
  score?: number;           // 0..100
  confidence?: number;      // 0..1
  scoreBreakdown?: Record<string, number>;
  
  // STEP 2: Liquidity & activity metrics
  liquidityUsd?: number;
  volume24hUsd?: number;
  trades24h?: number;
  twapDeviationBps?: number;  // bps vs pricing reference
  
  // STEP 4.1: TVL/Liquidity data
  tvlSource?: 'UNISWAP_SUBGRAPH' | 'DEFILLAMA' | 'NONE';
  tvlReliability?: number;    // 0..1
  tvlUpdatedAt?: number;
  feesUsd24h?: number;
  
  // STEP 2: Stable pair info
  isStablePair?: boolean;
  stableToken?: string;
  
  addedAt: number;
  updatedAt: number;
}

const DexPoolSchema = new Schema<IDexPool>({
  chainId: { type: Number, required: true },
  protocol: { type: String, required: true },
  address: { type: String, required: true, lowercase: true },
  
  token0: { type: String, required: true, lowercase: true },
  token1: { type: String, required: true, lowercase: true },
  token0Symbol: { type: String },
  token1Symbol: { type: String },
  token0Decimals: { type: Number },
  token1Decimals: { type: Number },
  
  fee: { type: Number },
  
  enabled: { type: Boolean, default: true },
  priority: { type: Number, default: 0 },
  lastSwapBlock: { type: Number },
  lastSwapAt: { type: Number },
  totalSwapsIndexed: { type: Number, default: 0 },
  
  // STEP 2: Status lifecycle
  status: { 
    type: String, 
    default: 'CANDIDATE',
    enum: ['CANDIDATE', 'ACTIVE', 'DEGRADED', 'DISABLED'],
    index: true,
  },
  statusReason: { type: String, default: '' },
  
  // STEP 2: Scoring
  score: { type: Number, default: 0, index: true },
  confidence: { type: Number, default: 0 },
  scoreBreakdown: { type: Schema.Types.Mixed },
  
  // STEP 2: Liquidity & activity metrics
  liquidityUsd: { type: Number, default: 0, index: true },
  volume24hUsd: { type: Number, default: 0 },
  trades24h: { type: Number, default: 0 },
  twapDeviationBps: { type: Number, default: 0 },
  
  // STEP 4.1: TVL/Liquidity data
  tvlSource: { type: String, enum: ['UNISWAP_SUBGRAPH', 'DEFILLAMA', 'NONE'], default: 'NONE' },
  tvlReliability: { type: Number, default: 0 },
  tvlUpdatedAt: { type: Number },
  feesUsd24h: { type: Number, default: 0 },
  
  // STEP 2: Stable pair info
  isStablePair: { type: Boolean, default: false, index: true },
  stableToken: { type: String, default: '' },
  
  addedAt: { type: Number, default: () => Date.now() },
  updatedAt: { type: Number, default: () => Date.now() },
}, {
  collection: 'onchain_v2_dex_pools',
  timestamps: false,
});

DexPoolSchema.index({ chainId: 1, address: 1 }, { unique: true });
DexPoolSchema.index({ chainId: 1, enabled: 1, priority: -1 });
DexPoolSchema.index({ chainId: 1, token0: 1, token1: 1, fee: 1 });

export const DexPoolModel = mongoose.model<IDexPool>('OnchainV2DexPool', DexPoolSchema);

console.log('[OnChain V2] DEX Models loaded');
