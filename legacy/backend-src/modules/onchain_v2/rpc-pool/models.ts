/**
 * OnChain V2 — RPC Pool Models
 * =============================
 * 
 * MongoDB models for RPC configuration managed via Admin UI.
 */

import mongoose, { Schema, Document } from 'mongoose';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type RpcProvider = 'infura' | 'ankr' | 'alchemy' | 'quicknode' | 'llama' | 'custom';
// All supported chain IDs (mainnets + testnets)
export type RpcChainId = number;

export interface RpcEndpoint {
  id: string;
  url: string;
  provider: RpcProvider;
  chainId: number;
  chainName: string;
  enabled: boolean;
  weight: number;       // 1-10, higher = preferred
  rpmLimit?: number;    // requests per minute cap
  notes?: string;
}

export interface RpcEndpointHealth {
  id: string;
  healthy: boolean;
  latencyMs: number;
  lastSuccess: number;
  lastError?: string;
  lastErrorAt?: number;
  successCount: number;
  failureCount: number;
  disabledUntil?: number;  // circuit breaker
}

// ═══════════════════════════════════════════════════════════════
// RPC CONFIG DOCUMENT (single active document)
// ═══════════════════════════════════════════════════════════════

export interface IRpcConfigDoc extends Document {
  _id: string;  // always "active"
  version: number;
  updatedAt: number;
  updatedBy: string;
  endpoints: RpcEndpoint[];
  settings: {
    maxRetries: number;
    retryDelayMs: number;
    circuitBreakerThreshold: number;  // failures before disable
    circuitBreakerCooldownMs: number;
    healthCheckIntervalMs: number;
    configCacheTtlMs: number;
  };
}

const RpcEndpointSchema = new Schema<RpcEndpoint>({
  id: { type: String, required: true },
  url: { type: String, required: true },
  provider: { 
    type: String, 
    required: true, 
    enum: ['infura', 'ankr', 'alchemy', 'quicknode', 'llama', 'custom'] 
  },
  chainId: { type: Number, required: true },  // Any chain ID supported
  chainName: { type: String, required: true },
  enabled: { type: Boolean, default: true },
  weight: { type: Number, default: 5, min: 1, max: 10 },
  rpmLimit: { type: Number },
  notes: { type: String },
}, { _id: false });

const RpcConfigSchema = new Schema<IRpcConfigDoc>({
  _id: { type: String, default: 'active' },
  version: { type: Number, default: 1 },
  updatedAt: { type: Number, required: true },
  updatedBy: { type: String, required: true },
  endpoints: [RpcEndpointSchema],
  settings: {
    maxRetries: { type: Number, default: 3 },
    retryDelayMs: { type: Number, default: 500 },
    circuitBreakerThreshold: { type: Number, default: 5 },
    circuitBreakerCooldownMs: { type: Number, default: 60000 },
    healthCheckIntervalMs: { type: Number, default: 30000 },
    configCacheTtlMs: { type: Number, default: 30000 },
  },
}, {
  collection: 'onchain_v2_rpc_config',
  timestamps: false,
});

export const RpcConfigModel = mongoose.model<IRpcConfigDoc>('OnchainV2RpcConfig', RpcConfigSchema);

// ═══════════════════════════════════════════════════════════════
// RPC HEALTH SNAPSHOT (for monitoring)
// ═══════════════════════════════════════════════════════════════

export interface IRpcHealthSnapshotDoc extends Document {
  timestamp: number;
  endpoints: RpcEndpointHealth[];
  overallHealthy: boolean;
  healthyCount: number;
  totalCount: number;
  avgLatencyMs: number;
}

const RpcEndpointHealthSchema = new Schema<RpcEndpointHealth>({
  id: { type: String, required: true },
  healthy: { type: Boolean, default: false },
  latencyMs: { type: Number, default: 0 },
  lastSuccess: { type: Number, default: 0 },
  lastError: { type: String },
  lastErrorAt: { type: Number },
  successCount: { type: Number, default: 0 },
  failureCount: { type: Number, default: 0 },
  disabledUntil: { type: Number },
}, { _id: false });

const RpcHealthSnapshotSchema = new Schema<IRpcHealthSnapshotDoc>({
  timestamp: { type: Number, required: true, index: true },
  endpoints: [RpcEndpointHealthSchema],
  overallHealthy: { type: Boolean, default: false },
  healthyCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  avgLatencyMs: { type: Number, default: 0 },
}, {
  collection: 'onchain_v2_rpc_health',
  timestamps: false,
});

RpcHealthSnapshotSchema.index({ timestamp: -1 });

export const RpcHealthSnapshotModel = mongoose.model<IRpcHealthSnapshotDoc>('OnchainV2RpcHealth', RpcHealthSnapshotSchema);

console.log('[OnChain V2] RPC Pool Models loaded');
