/**
 * OnChain V2 — Stablecoin Constants & Registry
 * ==============================================
 * 
 * Well-known stablecoin addresses per chain.
 */

import type { StableToken } from './stable_mintburn.model.js';

// ═══════════════════════════════════════════════════════════════
// STABLECOIN CONFIG
// ═══════════════════════════════════════════════════════════════

export interface StablecoinConfig {
  symbol: StableToken;
  address: string;
  decimals: number;
  chainId: number;
}

// ═══════════════════════════════════════════════════════════════
// STABLECOIN REGISTRY
// ═══════════════════════════════════════════════════════════════

export const STABLECOIN_REGISTRY: StablecoinConfig[] = [
  // ═══════════════════════════════════════════════════════════════
  // ETHEREUM MAINNET (chainId: 1)
  // ═══════════════════════════════════════════════════════════════
  {
    symbol: 'USDT',
    address: '0xdac17f958d2ee523a2206206994597c13d831ec7',
    decimals: 6,
    chainId: 1,
  },
  {
    symbol: 'USDC',
    address: '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
    decimals: 6,
    chainId: 1,
  },
  {
    symbol: 'DAI',
    address: '0x6b175474e89094c44da98b954eedeac495271d0f',
    decimals: 18,
    chainId: 1,
  },
  
  // ═══════════════════════════════════════════════════════════════
  // ARBITRUM (chainId: 42161)
  // ═══════════════════════════════════════════════════════════════
  {
    symbol: 'USDT',
    address: '0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9',
    decimals: 6,
    chainId: 42161,
  },
  {
    symbol: 'USDC',
    address: '0xaf88d065e77c8cc2239327c5edb3a432268e5831',
    decimals: 6,
    chainId: 42161,
  },
  
  // ═══════════════════════════════════════════════════════════════
  // OPTIMISM (chainId: 10)
  // ═══════════════════════════════════════════════════════════════
  {
    symbol: 'USDT',
    address: '0x94b008aa00579c1307b0ef2c499ad98a8ce58e58',
    decimals: 6,
    chainId: 10,
  },
  {
    symbol: 'USDC',
    address: '0x0b2c639c533813f4aa9d7837caf62653d097ff85',
    decimals: 6,
    chainId: 10,
  },
  
  // ═══════════════════════════════════════════════════════════════
  // BASE (chainId: 8453)
  // ═══════════════════════════════════════════════════════════════
  {
    symbol: 'USDC',
    address: '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913',
    decimals: 6,
    chainId: 8453,
  },
];

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Get stablecoins for a specific chain
 */
export function getStablecoinsForChain(chainId: number): StablecoinConfig[] {
  return STABLECOIN_REGISTRY.filter(s => s.chainId === chainId);
}

/**
 * Get stablecoin by address
 */
export function getStablecoinByAddress(address: string, chainId: number): StablecoinConfig | undefined {
  return STABLECOIN_REGISTRY.find(
    s => s.address.toLowerCase() === address.toLowerCase() && s.chainId === chainId
  );
}

/**
 * Check if address is a known stablecoin
 */
export function isStablecoin(address: string, chainId: number): boolean {
  return getStablecoinByAddress(address, chainId) !== undefined;
}

/**
 * Get all supported chain IDs for stablecoins
 */
export function getStablecoinChainIds(): number[] {
  const chains = new Set(STABLECOIN_REGISTRY.map(s => s.chainId));
  return Array.from(chains);
}

// Feature flag
export const STABLE_MINTBURN_ENABLED = process.env.ONCHAIN_V2_STABLE_MINTBURN_ENABLED !== 'false';

console.log('[OnChain V2] Stablecoin Registry loaded');
