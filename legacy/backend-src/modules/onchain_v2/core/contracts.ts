/**
 * OnChain V2 — Core Contracts
 * ============================
 * 
 * CANONICAL CONTRACTS — LOCKED v2.0
 * 
 * PURPOSE:
 * - Measure what money is doing (not what people say)
 * - Provide truth-layer for validation
 * - NO signals, NO predictions, NO trading recommendations
 * 
 * GOLDEN RULES:
 * - OnChain does NOT know about Sentiment
 * - OnChain does NOT know about Exchange Verdict
 * - OnChain does NOT know about MetaBrain
 * - OnChain measures and stores — nothing more
 * - NO_DATA is valid, not an error
 * 
 * ISOLATION BOUNDARY:
 * - This module is completely self-contained
 * - Only allowed external dependency: chain_adapters (for RPC)
 */

// ═══════════════════════════════════════════════════════════════
// ENUMS & CONSTANTS
// ═══════════════════════════════════════════════════════════════

export type OnchainSourceType = 'mock' | 'rpc' | 'api';
export type OnchainProviderStatus = 'UP' | 'DEGRADED' | 'DOWN';
export type OnchainChain = 'ethereum' | 'bitcoin' | 'solana' | 'arbitrum' | 'base' | 'optimism' | 'polygon';
export type OnchainWindow = '1h' | '4h' | '24h' | '7d';

export const SOURCE_QUALITY: Record<OnchainSourceType, number> = {
  rpc: 1.0,
  api: 0.8,
  mock: 0.3,
} as const;

export const ONCHAIN_THRESHOLDS = {
  LARGE_TRANSFER_USD: 100_000,
  WHALE_TRANSFER_USD: 1_000_000,
  MIN_USABLE_CONFIDENCE: 0.4,
  Z_SCORE_K: 2.0,
  BASELINE_WINDOW_DAYS: 30,
} as const;

// ═══════════════════════════════════════════════════════════════
// 1. ONCHAIN SNAPSHOT (Raw Data from Provider)
// ═══════════════════════════════════════════════════════════════

export interface OnchainSnapshot {
  symbol: string;
  chain: OnchainChain;
  t0: number;
  snapshotTimestamp: number;
  window: OnchainWindow;
  
  // Exchange flows
  exchangeInflowUsd: number;
  exchangeOutflowUsd: number;
  exchangeNetUsd: number;
  
  // Net flows
  netInflowUsd: number;
  netOutflowUsd: number;
  netFlowUsd: number;
  
  // Network activity
  activeAddresses: number;
  txCount: number;
  feesUsd: number;
  
  // Whale activity
  largeTransfersCount: number;
  largeTransfersVolumeUsd: number;
  topHolderDeltaUsd?: number;
  
  // Source metadata
  source: OnchainSourceType;
  sourceProvider?: string;
  sourceQuality: number;
  missingFields: string[];
  rawDataPoints?: Record<string, number | string>;
}

// ═══════════════════════════════════════════════════════════════
// 2. ONCHAIN METRICS (Normalized Measurements)
// ═══════════════════════════════════════════════════════════════

export interface OnchainMetrics {
  symbol: string;
  t0: number;
  window: OnchainWindow;
  
  // Core metrics (LOCKED v2)
  flowScore: number;           // [-1..+1] net flow direction
  exchangePressure: number;    // [-1..+1] sell vs withdraw pressure
  whaleActivity: number;       // [0..1] large holder activity
  networkHeat: number;         // [0..1] network congestion/activity
  velocity: number;            // [0..1] capital movement speed
  distributionSkew: number;    // [0..1] activity concentration
  
  // Quality metrics
  dataCompleteness: number;    // [0..1]
  confidence: number;          // [0..1]
  
  // Explainability
  drivers: string[];
  missing: string[];
  
  // Debug data
  rawScores?: {
    flowRaw: number;
    exchangeRaw: number;
    whaleRaw: number;
    heatRaw: number;
    velocityRaw: number;
    skewRaw: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// 3. ONCHAIN STATE (Derived, NOT a verdict)
// ═══════════════════════════════════════════════════════════════

export type OnchainState = 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL' | 'LOW_CONF' | 'NO_DATA';

/**
 * Derive state from metrics (pure function)
 * 
 * State precedence:
 * - NO_DATA: No observations at all
 * - LOW_CONF: Data exists but confidence below threshold
 * - ACCUMULATION/DISTRIBUTION/NEUTRAL: Normal states with sufficient confidence
 */
export function deriveOnchainState(metrics: OnchainMetrics, hasData = true): OnchainState {
  // NO_DATA only when there's truly no observation
  if (!hasData || metrics.dataCompleteness === 0) return 'NO_DATA';
  
  // LOW_CONF when data exists but confidence is insufficient
  if (metrics.confidence < ONCHAIN_THRESHOLDS.MIN_USABLE_CONFIDENCE) return 'LOW_CONF';
  
  const netSignal = metrics.flowScore - metrics.exchangePressure;
  
  if (netSignal > 0.2) return 'ACCUMULATION';
  if (netSignal < -0.2) return 'DISTRIBUTION';
  return 'NEUTRAL';
}

// ═══════════════════════════════════════════════════════════════
// 4. ONCHAIN OBSERVATION (Persisted Unit)
// ═══════════════════════════════════════════════════════════════

export interface OnchainObservation {
  id: string;
  symbol: string;
  t0: number;
  window: OnchainWindow;
  snapshot: OnchainSnapshot;
  metrics: OnchainMetrics;
  state: OnchainState;
  diagnostics: OnchainDiagnostics;
  createdAt: number;
  updatedAt: number;
}

export interface OnchainDiagnostics {
  calculatedAt: number;
  processingTimeMs: number;
  provider: string;
  providerMode: OnchainSourceType;
  warnings: string[];
  baseline?: {
    windowSize: number;
    medianFlowUsd: number;
    madFlowUsd: number;
    medianExchangeNetUsd: number;
    madExchangeNetUsd: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// 5. PROVIDER HEALTH
// ═══════════════════════════════════════════════════════════════

export interface OnchainProviderHealth {
  providerId: string;
  providerName: string;
  providerMode: OnchainSourceType;
  status: OnchainProviderStatus;
  chains: OnchainChain[];
  lastSuccessAt: number;
  lastError?: string;
  lastErrorAt?: number;
  successRate24h: number;
  avgLatencyMs: number;
  checkedAt: number;
}

// ═══════════════════════════════════════════════════════════════
// 6. ENGINE OUTPUT DTO (Final Signal)
// ═══════════════════════════════════════════════════════════════

export interface OnchainEngineOutput {
  symbol: string;
  t0: number;
  
  // Raw values (before any adjustments)
  rawConfidence: number;
  rawDirection: OnchainState;
  rawScore: number;  // Composite score [-1, +1]
  
  // Metrics breakdown
  metrics: OnchainMetrics;
  
  // Data quality
  dataQuality: {
    source: OnchainSourceType;
    completeness: number;
    freshness: number;
    reliability: number;
  };
  
  // Drivers for explainability
  drivers: string[];
  warnings: string[];
  
  // Processing metadata
  processedAt: number;
  processingTimeMs: number;
}

// ═══════════════════════════════════════════════════════════════
// 7. API RESPONSE TYPES
// ═══════════════════════════════════════════════════════════════

export interface OnchainHealthResponse {
  ok: boolean;
  status: OnchainProviderStatus;
  providerMode: OnchainSourceType;
  providers: OnchainProviderHealth[];
  timestamp: number;
}

export interface OnchainSnapshotResponse {
  ok: boolean;
  snapshot: OnchainSnapshot | null;
  source: OnchainSourceType;
  confidence: number;
  dataAvailable: boolean;
}

export interface OnchainObservationResponse {
  ok: boolean;
  observation: OnchainObservation | null;
  error?: string;
}

export interface OnchainHistoryResponse {
  ok: boolean;
  observations: OnchainObservation[];
  count: number;
  range: { from: number; to: number };
}

console.log('[OnChain V2] Contracts loaded');
