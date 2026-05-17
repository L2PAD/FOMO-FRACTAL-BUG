/**
 * OnChain V2 — Bridge Registry
 * ==============================
 * 
 * Canonical bridge tracks for L1↔L2 migration tracking.
 * Source of truth for which bridges/directions we monitor.
 */

import type { BridgeTrack, BridgeFamily, ContractRole } from './bridge.types.js';

// ═══════════════════════════════════════════════════════════════
// CANONICAL BRIDGE TRACKS
// ═══════════════════════════════════════════════════════════════

export const BRIDGE_TRACKS: BridgeTrack[] = [
  // ═══════════════════════════════════════════════════════════════
  // OPTIMISM (OP Stack)
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'OPTIMISM_L1_TO_L2_L1',
    bridge: 'OPTIMISM',
    direction: 'L1_TO_L2',
    watchSide: 'L1',
    watchChainId: 1,
    contractRoles: ['OP_L1_STANDARD_BRIDGE'],
    eventHints: ['ETHDepositInitiated', 'ERC20DepositInitiated'],
    enabledByDefault: true,
  },
  {
    id: 'OPTIMISM_L2_TO_L1_L2',
    bridge: 'OPTIMISM',
    direction: 'L2_TO_L1',
    watchSide: 'L2',
    watchChainId: 10,
    contractRoles: ['OP_L2_STANDARD_BRIDGE'],
    eventHints: ['WithdrawalInitiated', 'ERC20WithdrawalInitiated'],
    enabledByDefault: true,
  },

  // ═══════════════════════════════════════════════════════════════
  // BASE (OP Stack)
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'BASE_L1_TO_L2_L1',
    bridge: 'BASE',
    direction: 'L1_TO_L2',
    watchSide: 'L1',
    watchChainId: 1,
    contractRoles: ['BASE_L1_STANDARD_BRIDGE'],
    eventHints: ['ETHDepositInitiated', 'ERC20DepositInitiated'],
    enabledByDefault: true,
  },
  {
    id: 'BASE_L2_TO_L1_L2',
    bridge: 'BASE',
    direction: 'L2_TO_L1',
    watchSide: 'L2',
    watchChainId: 8453,
    contractRoles: ['BASE_L2_STANDARD_BRIDGE'],
    eventHints: ['WithdrawalInitiated', 'ERC20WithdrawalInitiated'],
    enabledByDefault: true,
  },

  // ═══════════════════════════════════════════════════════════════
  // ARBITRUM (Canonical)
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'ARBITRUM_L1_TO_L2_L1',
    bridge: 'ARBITRUM',
    direction: 'L1_TO_L2',
    watchSide: 'L1',
    watchChainId: 1,
    contractRoles: ['ARB_L1_INBOX'],
    eventHints: ['MessageDelivered', 'InboxMessageDelivered'],
    enabledByDefault: true,
  },
  {
    id: 'ARBITRUM_L2_TO_L1_L2',
    bridge: 'ARBITRUM',
    direction: 'L2_TO_L1',
    watchSide: 'L2',
    watchChainId: 42161,
    contractRoles: ['ARB_L2_GATEWAY_ROUTER'],
    eventHints: ['WithdrawalInitiated', 'OutboundTransferInitiated'],
    enabledByDefault: true,
  },
];

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Get all bridge tracks
 */
export function getBridgeTracks(): BridgeTrack[] {
  return BRIDGE_TRACKS.slice();
}

/**
 * Get tracks for specific bridge
 */
export function getTracksForBridge(bridge: BridgeFamily): BridgeTrack[] {
  return BRIDGE_TRACKS.filter(t => t.bridge === bridge);
}

/**
 * Get tracks for specific chain
 */
export function getTracksForChain(chainId: number): BridgeTrack[] {
  return BRIDGE_TRACKS.filter(t => t.watchChainId === chainId);
}

/**
 * Get all supported bridges
 */
export function getSupportedBridges(): BridgeFamily[] {
  return ['ARBITRUM', 'OPTIMISM', 'BASE'];
}

/**
 * Get all required contract roles
 */
export function getAllContractRoles(): ContractRole[] {
  return [
    'OP_L1_STANDARD_BRIDGE',
    'OP_L2_STANDARD_BRIDGE',
    'BASE_L1_STANDARD_BRIDGE',
    'BASE_L2_STANDARD_BRIDGE',
    'ARB_L1_INBOX',
    'ARB_L2_GATEWAY_ROUTER',
  ];
}

/**
 * Get L2 chain ID for bridge family
 */
export function getL2ChainId(bridge: BridgeFamily): number {
  switch (bridge) {
    case 'ARBITRUM': return 42161;
    case 'OPTIMISM': return 10;
    case 'BASE': return 8453;
  }
}

console.log('[OnChain V2] Bridge Registry loaded');
