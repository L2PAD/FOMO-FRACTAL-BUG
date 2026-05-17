/**
 * OnChain V2 — Chain Constants
 * =============================
 * 
 * Supported chains configuration.
 * Single source of truth for all multi-chain operations.
 */

// ═══════════════════════════════════════════════════════════════
// SUPPORTED CHAINS
// ═══════════════════════════════════════════════════════════════

export const SUPPORTED_CHAINS = [
  { 
    chainId: 1, 
    name: 'Ethereum', 
    short: 'ETH', 
    explorer: 'https://etherscan.io',
    nativeSymbol: 'ETH',
    avgBlockTime: 12,
    rpcEnvKey: 'ETH_RPC_URL',
  },
  { 
    chainId: 42161, 
    name: 'Arbitrum', 
    short: 'ARB', 
    explorer: 'https://arbiscan.io',
    nativeSymbol: 'ETH',
    avgBlockTime: 0.25,
    rpcEnvKey: 'ARB_RPC_URL',
  },
  { 
    chainId: 10, 
    name: 'Optimism', 
    short: 'OP', 
    explorer: 'https://optimistic.etherscan.io',
    nativeSymbol: 'ETH',
    avgBlockTime: 2,
    rpcEnvKey: 'OP_RPC_URL',
  },
  { 
    chainId: 8453, 
    name: 'Base', 
    short: 'BASE', 
    explorer: 'https://basescan.org',
    nativeSymbol: 'ETH',
    avgBlockTime: 2,
    rpcEnvKey: 'BASE_RPC_URL',
  },
] as const;

export type SupportedChainId = (typeof SUPPORTED_CHAINS)[number]['chainId'];

// Chain ID lookup
export const CHAIN_IDS = {
  ETHEREUM: 1,
  ARBITRUM: 42161,
  OPTIMISM: 10,
  BASE: 8453,
} as const;

// ═══════════════════════════════════════════════════════════════
// MULTI-CHAIN FEATURE FLAG
// ═══════════════════════════════════════════════════════════════

/**
 * Feature flag for multi-chain operations.
 * Phase 5.3: Unified with core/featureFlags.ts
 * Set to false to use ETH-only (backward compatible with v1.0.0)
 */
export const MULTICHAIN_ENABLED = process.env.ONCHAIN_V2_MULTICHAIN_ENABLED === 'true' || process.env.MULTICHAIN_ENABLED === 'true';

/**
 * Get active chains based on feature flag
 */
export function getActiveChains(): typeof SUPPORTED_CHAINS[number][] {
  if (!MULTICHAIN_ENABLED) {
    return SUPPORTED_CHAINS.filter(c => c.chainId === CHAIN_IDS.ETHEREUM);
  }
  return [...SUPPORTED_CHAINS];
}

/**
 * Get active chain IDs based on feature flag
 */
export function getActiveChainIds(): SupportedChainId[] {
  return getActiveChains().map(c => c.chainId);
}

console.log(`[OnChain V2] Chain Constants loaded (multichain=${MULTICHAIN_ENABLED})`);
