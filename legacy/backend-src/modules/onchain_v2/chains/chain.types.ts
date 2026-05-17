/**
 * OnChain V2 — Chain Types
 * =========================
 * 
 * Type definitions for multi-chain operations.
 */

// ═══════════════════════════════════════════════════════════════
// CHAIN METADATA
// ═══════════════════════════════════════════════════════════════

export interface ChainMeta {
  chainId: number;
  name: string;
  short: string;
  explorer: string;
  nativeSymbol: string;
  avgBlockTime: number;  // seconds
  rpcEnvKey: string;
}

// ═══════════════════════════════════════════════════════════════
// CHAIN HEALTH
// ═══════════════════════════════════════════════════════════════

export interface ChainRpcHealth {
  id: string;
  url: string;
  healthy: boolean;
  latencyMs: number;
  lastSuccess: number;
  failureCount: number;
  cooling: boolean;
}

export interface ChainHealth {
  chainId: number;
  chain: string;
  name: string;
  ok: boolean;
  
  // Block info
  latestBlock: number;
  syncedBlock: number;
  blocksBehind: number;
  
  // RPC health
  rpcHealthy: boolean;
  rpcEndpointsActive: number;
  rpcEndpointsTotal: number;
  rpcAvgLatencyMs: number;
  
  // Ingestion status
  erc20Status: IngestionStatus;
  dexStatus: IngestionStatus;
  
  // Timestamps
  lastHealthCheck: number;
  error?: string;
}

export interface IngestionStatus {
  enabled: boolean;
  lastBlock: number;
  blocksBehind: number;
  status: 'idle' | 'syncing' | 'backfilling' | 'error';
  lastSyncAt: number;
  totalIndexed: number;
  lastError?: string;
}

// ═══════════════════════════════════════════════════════════════
// CHAIN STATUS SUMMARY
// ═══════════════════════════════════════════════════════════════

export interface ChainsSummary {
  ok: boolean;
  multiChainEnabled: boolean;
  activeChains: number;
  healthyChains: number;
  totalBlocksBehind: number;
  avgRpcLatency: number;
  chains: ChainHealth[];
  lastUpdated: number;
}
