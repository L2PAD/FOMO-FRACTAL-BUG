/**
 * OnChain V2 — Bridge Health Service
 * ====================================
 * 
 * Computes bridge readiness and direction completeness.
 * Key rule: Bridge is READY only when BOTH directions are active.
 */

import { getBridgeTracks, getSupportedBridges } from './bridge.registry.js';
import { resolveContracts, getMissingRoles, BridgeResolverDeps } from './bridge.resolver.js';
import type {
  BridgeHealthResponse,
  BridgeHealthSummary,
  BridgeStatus,
  TrackHealth,
  BridgeFamily,
} from './bridge.types.js';

// ═══════════════════════════════════════════════════════════════
// FEATURE FLAGS
// ═══════════════════════════════════════════════════════════════

export const BRIDGE_ENABLED = process.env.ONCHAIN_V2_BRIDGE_ENABLED === 'true';

// ═══════════════════════════════════════════════════════════════
// DEPS INTERFACE
// ═══════════════════════════════════════════════════════════════

export interface ChainRegistryLike {
  getActiveChainIds(): number[];
  isActive(chainId: number): boolean;
}

export interface BridgeHealthDeps extends BridgeResolverDeps {
  chains: ChainRegistryLike;
  flags: {
    bridgeEnabled: boolean;
    multiChainEnabled: boolean;
  };
}

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function groupByBridge(tracks: TrackHealth[]): Record<BridgeFamily, TrackHealth[]> {
  const result: Record<string, TrackHealth[]> = {};
  for (const t of tracks) {
    if (!result[t.bridge]) {
      result[t.bridge] = [];
    }
    result[t.bridge].push(t);
  }
  return result as Record<BridgeFamily, TrackHealth[]>;
}

function computeBridgeStatus(
  bridgeEnabled: boolean,
  multiChainEnabled: boolean,
  trackGroup: TrackHealth[]
): { status: BridgeStatus; reasons: string[]; directionCompleteness: boolean } {
  const reasons: string[] = [];

  // Check if bridge is globally disabled
  if (!bridgeEnabled) {
    return { 
      status: 'DISABLED', 
      reasons: ['BRIDGE_DISABLED'],
      directionCompleteness: false,
    };
  }

  // Check for misconfiguration (missing contracts)
  const anyMisconfigured = trackGroup.some(t => t.misconfigured);
  if (anyMisconfigured) {
    const missingTracks = trackGroup.filter(t => t.misconfigured).map(t => t.trackId);
    reasons.push(`MISSING_CONTRACTS: ${missingTracks.join(', ')}`);
    return { 
      status: 'MISCONFIGURED', 
      reasons,
      directionCompleteness: false,
    };
  }

  // Check direction completeness
  const hasL1ToL2 = trackGroup.some(t => t.direction === 'L1_TO_L2');
  const hasL2ToL1 = trackGroup.some(t => t.direction === 'L2_TO_L1');
  const directionCompleteness = hasL1ToL2 && hasL2ToL1;

  // Check active status
  const l1ToL2Active = trackGroup.filter(t => t.direction === 'L1_TO_L2').some(t => t.isActive);
  const l2ToL1Active = trackGroup.filter(t => t.direction === 'L2_TO_L1').some(t => t.isActive);
  const allActive = l1ToL2Active && l2ToL1Active;
  const anyActive = l1ToL2Active || l2ToL1Active;

  // If multichain is off, L2 tracks are blocked
  if (!multiChainEnabled) {
    reasons.push('MULTICHAIN_DISABLED');
  }

  if (!l1ToL2Active && hasL1ToL2) {
    reasons.push('L1_TO_L2_BLOCKED');
  }
  if (!l2ToL1Active && hasL2ToL1) {
    reasons.push('L2_TO_L1_BLOCKED');
  }

  // Determine status
  if (allActive && directionCompleteness) {
    return { status: 'READY', reasons: [], directionCompleteness: true };
  }
  
  if (anyActive) {
    return { 
      status: 'PARTIAL', 
      reasons: reasons.length ? reasons : ['PARTIAL_ACTIVE'],
      directionCompleteness,
    };
  }

  return { 
    status: 'PARTIAL', 
    reasons: reasons.length ? reasons : ['NO_ACTIVE_TRACKS'],
    directionCompleteness: false,
  };
}

// ═══════════════════════════════════════════════════════════════
// MAIN HEALTH FUNCTION
// ═══════════════════════════════════════════════════════════════

export async function getBridgeHealth(deps: BridgeHealthDeps): Promise<BridgeHealthResponse> {
  const tracks = getBridgeTracks();
  const activeChainIds = deps.chains.getActiveChainIds();
  const bridgeEnabled = deps.flags.bridgeEnabled;
  const multiChainEnabled = deps.flags.multiChainEnabled;

  const trackHealths: TrackHealth[] = [];

  for (const t of tracks) {
    const contracts = await resolveContracts(t.contractRoles, deps);
    const missing = getMissingRoles(contracts);

    const chainActive = activeChainIds.includes(t.watchChainId);

    // Determine activation logic
    let isActive = true;
    let blockedReason: string | undefined;

    if (!bridgeEnabled) {
      isActive = false;
      blockedReason = 'BRIDGE_DISABLED';
    } else if (!chainActive) {
      isActive = false;
      blockedReason = 'CHAIN_NOT_ACTIVE';
    } else if (t.watchSide === 'L2' && !multiChainEnabled) {
      isActive = false;
      blockedReason = 'MULTICHAIN_DISABLED';
    } else if (missing.length > 0) {
      isActive = false;
      blockedReason = `MISSING_CONTRACTS: ${missing.join(', ')}`;
    }

    trackHealths.push({
      trackId: t.id,
      bridge: t.bridge,
      direction: t.direction,
      watchSide: t.watchSide,
      watchChainId: t.watchChainId,
      isActive,
      blockedReason,
      contracts,
      contractsResolved: contracts.some(c => !!c.address),
      misconfigured: missing.length > 0 && contracts.every(c => !c.address),
    });
  }

  // Group by bridge and compute status
  const grouped = groupByBridge(trackHealths);
  const bridges: BridgeHealthSummary[] = [];
  
  let ready = 0;
  let partial = 0;
  let disabled = 0;
  let misconfigured = 0;

  for (const bridge of getSupportedBridges()) {
    const group = grouped[bridge] || [];
    const { status, reasons, directionCompleteness } = computeBridgeStatus(
      bridgeEnabled,
      multiChainEnabled,
      group
    );

    bridges.push({
      bridge,
      status,
      directionCompleteness,
      reasons,
      tracks: group,
    });

    switch (status) {
      case 'READY': ready++; break;
      case 'PARTIAL': partial++; break;
      case 'DISABLED': disabled++; break;
      case 'MISCONFIGURED': misconfigured++; break;
    }
  }

  return {
    ok: true,
    enabled: bridgeEnabled,
    multiChainEnabled,
    activeChains: activeChainIds,
    summary: { ready, partial, disabled, misconfigured },
    bridges,
    timestamp: Date.now(),
  };
}

// ═══════════════════════════════════════════════════════════════
// SINGLETON SERVICE
// ═══════════════════════════════════════════════════════════════

class BridgeHealthService {
  private cachedHealth: BridgeHealthResponse | null = null;
  private cacheTime = 0;
  private readonly cacheTtlMs = 30000; // 30 seconds

  async getHealth(deps: BridgeHealthDeps): Promise<BridgeHealthResponse> {
    const now = Date.now();
    if (this.cachedHealth && (now - this.cacheTime) < this.cacheTtlMs) {
      return this.cachedHealth;
    }

    const health = await getBridgeHealth(deps);
    this.cachedHealth = health;
    this.cacheTime = now;
    return health;
  }

  clearCache(): void {
    this.cachedHealth = null;
    this.cacheTime = 0;
  }

  /**
   * Check if bridge module is ready for ingestion
   */
  async isReadyForIngestion(deps: BridgeHealthDeps): Promise<{
    ready: boolean;
    reason?: string;
  }> {
    const health = await this.getHealth(deps);
    
    if (!health.enabled) {
      return { ready: false, reason: 'BRIDGE_DISABLED' };
    }

    const readyBridges = health.bridges.filter(b => b.status === 'READY');
    if (readyBridges.length === 0) {
      return { ready: false, reason: 'NO_BRIDGES_READY' };
    }

    return { ready: true };
  }
}

export const bridgeHealthService = new BridgeHealthService();

console.log('[OnChain V2] Bridge Health Service loaded');
