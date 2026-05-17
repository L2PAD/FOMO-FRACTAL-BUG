/**
 * OnChain V2 — MongoDB Models
 * ============================
 * 
 * Isolated persistence layer for OnChain V2 module.
 */

import mongoose, { Schema, Document, Types } from 'mongoose';
import {
  OnchainSnapshot,
  OnchainMetrics,
  OnchainObservation,
  OnchainProviderHealth,
  OnchainWindow,
  OnchainState,
} from '../contracts.js';

// ═══════════════════════════════════════════════════════════════
// 1. SNAPSHOT MODEL
// ═══════════════════════════════════════════════════════════════

export interface IOnchainSnapshotDoc extends Document, OnchainSnapshot {
  _id: Types.ObjectId;
  createdAt: Date;
}

const OnchainSnapshotSchema = new Schema<IOnchainSnapshotDoc>({
  symbol: { type: String, required: true, index: true },
  chain: { 
    type: String, 
    required: true, 
    enum: ['bitcoin', 'ethereum', 'solana', 'arbitrum', 'base', 'optimism', 'polygon'] 
  },
  t0: { type: Number, required: true, index: true },
  snapshotTimestamp: { type: Number, required: true },
  window: { type: String, required: true, enum: ['1h', '4h', '24h', '7d'], default: '1h' },
  
  exchangeInflowUsd: { type: Number, default: 0 },
  exchangeOutflowUsd: { type: Number, default: 0 },
  exchangeNetUsd: { type: Number, default: 0 },
  
  netInflowUsd: { type: Number, default: 0 },
  netOutflowUsd: { type: Number, default: 0 },
  netFlowUsd: { type: Number, default: 0 },
  
  activeAddresses: { type: Number, default: 0 },
  txCount: { type: Number, default: 0 },
  feesUsd: { type: Number, default: 0 },
  
  largeTransfersCount: { type: Number, default: 0 },
  largeTransfersVolumeUsd: { type: Number, default: 0 },
  topHolderDeltaUsd: { type: Number },
  
  source: { type: String, enum: ['mock', 'rpc', 'api'], default: 'mock' },
  sourceProvider: { type: String },
  sourceQuality: { type: Number, default: 0.3 },
  missingFields: [{ type: String }],
  rawDataPoints: { type: Map, of: Schema.Types.Mixed },
}, {
  timestamps: { createdAt: 'createdAt', updatedAt: false },
  collection: 'onchain_v2_snapshots',
});

OnchainSnapshotSchema.index({ symbol: 1, t0: 1, window: 1 }, { unique: true });
OnchainSnapshotSchema.index({ t0: -1 });

export const OnchainSnapshotModel = mongoose.models.OnchainV2Snapshot ||
  mongoose.model<IOnchainSnapshotDoc>('OnchainV2Snapshot', OnchainSnapshotSchema, 'onchain_v2_snapshots');

// ═══════════════════════════════════════════════════════════════
// 2. OBSERVATION MODEL
// ═══════════════════════════════════════════════════════════════

export interface IOnchainObservationDoc extends Document {
  _id: Types.ObjectId;
  id: string;
  symbol: string;
  t0: number;
  window: OnchainWindow;
  snapshot: OnchainSnapshot;
  metrics: OnchainMetrics;
  state: OnchainState;
  diagnostics: OnchainObservation['diagnostics'];
  createdAt: number;
  updatedAt: number;
}

const OnchainMetricsSubSchema = new Schema({
  symbol: String,
  t0: Number,
  window: String,
  flowScore: { type: Number, default: 0 },
  exchangePressure: { type: Number, default: 0 },
  whaleActivity: { type: Number, default: 0 },
  networkHeat: { type: Number, default: 0 },
  velocity: { type: Number, default: 0 },
  distributionSkew: { type: Number, default: 0 },
  dataCompleteness: { type: Number, default: 0 },
  confidence: { type: Number, default: 0 },
  drivers: [String],
  missing: [String],
  rawScores: {
    flowRaw: Number,
    exchangeRaw: Number,
    whaleRaw: Number,
    heatRaw: Number,
    velocityRaw: Number,
    skewRaw: Number,
  },
}, { _id: false });

const OnchainObservationSchema = new Schema<IOnchainObservationDoc>({
  id: { type: String, required: true, unique: true },
  symbol: { type: String, required: true, index: true },
  t0: { type: Number, required: true, index: true },
  window: { type: String, required: true, enum: ['1h', '4h', '24h', '7d'], default: '1h' },
  
  snapshot: { type: Schema.Types.Mixed, required: true },
  metrics: { type: OnchainMetricsSubSchema, required: true },
  state: { type: String, enum: ['ACCUMULATION', 'DISTRIBUTION', 'NEUTRAL', 'NO_DATA'], required: true },
  diagnostics: { type: Schema.Types.Mixed, required: true },
  
  createdAt: { type: Number, required: true },
  updatedAt: { type: Number, required: true },
}, {
  collection: 'onchain_v2_observations',
});

OnchainObservationSchema.index({ symbol: 1, t0: -1 });
OnchainObservationSchema.index({ symbol: 1, t0: 1, window: 1 }, { unique: true });

export const OnchainObservationModel = mongoose.models.OnchainV2Observation ||
  mongoose.model<IOnchainObservationDoc>('OnchainV2Observation', OnchainObservationSchema, 'onchain_v2_observations');

// ═══════════════════════════════════════════════════════════════
// 3. PROVIDER HEALTH MODEL
// ═══════════════════════════════════════════════════════════════

export interface IOnchainProviderHealthDoc extends Document, OnchainProviderHealth {
  _id: Types.ObjectId;
}

const OnchainProviderHealthSchema = new Schema<IOnchainProviderHealthDoc>({
  providerId: { type: String, required: true, unique: true },
  providerName: { type: String, required: true },
  providerMode: { type: String, enum: ['mock', 'rpc', 'api'], default: 'mock' },
  status: { type: String, enum: ['UP', 'DEGRADED', 'DOWN'], default: 'DOWN' },
  chains: [{ type: String }],
  lastSuccessAt: { type: Number, default: 0 },
  lastError: String,
  lastErrorAt: Number,
  successRate24h: { type: Number, default: 0 },
  avgLatencyMs: { type: Number, default: 0 },
  checkedAt: { type: Number, required: true },
}, {
  collection: 'onchain_v2_provider_health',
});

export const OnchainProviderHealthModel = mongoose.models.OnchainV2ProviderHealth ||
  mongoose.model<IOnchainProviderHealthDoc>('OnchainV2ProviderHealth', OnchainProviderHealthSchema);

console.log('[OnChain V2] Models loaded');
