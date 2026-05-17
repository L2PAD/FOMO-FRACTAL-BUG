/**
 * OnChain V2 — Bridge Types
 * ==========================
 * 
 * Type definitions for Bridge Intelligence layer.
 * Bi-directional L1↔L2 migration tracking.
 */

// ═══════════════════════════════════════════════════════════════
// ENUMS
// ═══════════════════════════════════════════════════════════════

export type BridgeFamily = 'ARBITRUM' | 'OPTIMISM' | 'BASE';
export type BridgeDirection = 'L1_TO_L2' | 'L2_TO_L1';
export type WatchSide = 'L1' | 'L2';

// ═══════════════════════════════════════════════════════════════
// CONTRACT ROLES
// ═══════════════════════════════════════════════════════════════

export type ContractRole =
  // OP Stack (Optimism)
  | 'OP_L1_STANDARD_BRIDGE'
  | 'OP_L2_STANDARD_BRIDGE'
  // OP Stack (Base)
  | 'BASE_L1_STANDARD_BRIDGE'
  | 'BASE_L2_STANDARD_BRIDGE'
  // Arbitrum (canonical)
  | 'ARB_L1_INBOX'
  | 'ARB_L2_GATEWAY_ROUTER';

// ═══════════════════════════════════════════════════════════════
// BRIDGE TRACK
// ═══════════════════════════════════════════════════════════════

export type BridgeTrackId = string;

export interface BridgeTrack {
  id: BridgeTrackId;           // stable id: e.g. "OP_L1_TO_L2_L1"
  bridge: BridgeFamily;
  direction: BridgeDirection;
  watchSide: WatchSide;
  watchChainId: number;        // 1 / 10 / 8453 / 42161
  contractRoles: ContractRole[];
  eventHints: string[];        // not ABI yet, just hints
  enabledByDefault: boolean;
}

// ═══════════════════════════════════════════════════════════════
// RESOLVED CONTRACT
// ═══════════════════════════════════════════════════════════════

export interface ResolvedContract {
  role: ContractRole;
  address: string | null;      // null => missing
  source: 'DB' | 'ENV' | 'STATIC' | 'NONE';
}

// ═══════════════════════════════════════════════════════════════
// TRACK HEALTH
// ═══════════════════════════════════════════════════════════════

export interface TrackHealth {
  trackId: BridgeTrackId;
  bridge: BridgeFamily;
  direction: BridgeDirection;
  watchSide: WatchSide;
  watchChainId: number;
  isActive: boolean;
  blockedReason?: string;      // MULTICHAIN_DISABLED, CHAIN_NOT_ACTIVE, etc.
  contracts: ResolvedContract[];
  contractsResolved: boolean;  // at least 1 contract resolved
  misconfigured: boolean;      // any required contract missing
}

// ═══════════════════════════════════════════════════════════════
// BRIDGE STATUS & HEALTH
// ═══════════════════════════════════════════════════════════════

export type BridgeStatus = 'READY' | 'PARTIAL' | 'DISABLED' | 'MISCONFIGURED';

export interface BridgeHealthSummary {
  bridge: BridgeFamily;
  status: BridgeStatus;
  directionCompleteness: boolean;
  reasons: string[];
  tracks: TrackHealth[];
}

export interface BridgeHealthResponse {
  ok: boolean;
  enabled: boolean;
  multiChainEnabled: boolean;
  activeChains: number[];
  summary: {
    ready: number;
    partial: number;
    disabled: number;
    misconfigured: number;
  };
  bridges: BridgeHealthSummary[];
  timestamp: number;
}

// ═══════════════════════════════════════════════════════════════
// BRIDGE EVENT (for future ingestion)
// ═══════════════════════════════════════════════════════════════

export interface BridgeEvent {
  chainId: number;
  srcChainId: number;
  dstChainId: number;
  direction: BridgeDirection;
  bridge: BridgeFamily;
  txHash: string;
  logIndex: number;
  blockNumber: number;
  timestamp: number;
  tokenAddress: string;
  amountRaw: string;
  amountNorm?: number;
  usdValue?: number;
  sender: string;
  receiver?: string;
  isStable: boolean;
  isWhale: boolean;
}

// ═══════════════════════════════════════════════════════════════
// AGGREGATION TYPES (for future use)
// ═══════════════════════════════════════════════════════════════

export interface BridgeNetMigration {
  window: '24h' | '7d' | '30d';
  l1ToL2Usd: number;
  l2ToL1Usd: number;
  netUsd: number;
  netStableUsd: number;
  netNonStableUsd: number;
  whaleNetUsd: number;
  perChain: {
    arbitrum: number;
    optimism: number;
    base: number;
  };
  sampleCount: number;
  computedAt: number;
}

console.log('[OnChain V2] Bridge Types loaded');
