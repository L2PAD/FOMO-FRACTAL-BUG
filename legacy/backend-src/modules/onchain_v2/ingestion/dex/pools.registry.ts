/**
 * OnChain V2 — DEX Pool Registry (Multi-Chain)
 * ==============================================
 * 
 * Registry of DEX pools to index per chain.
 * Uniswap V3 pools on ETH/ARB/OP/BASE.
 */

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface DexPoolConfig {
  chainId: number;
  pool: string;       // Pool address (lowercase)
  name: string;       // Human readable name
  token0: string;     // Token0 symbol
  token1: string;     // Token1 symbol
  fee: number;        // Fee tier (500, 3000, 10000)
  enabled: boolean;
}

// ═══════════════════════════════════════════════════════════════
// POOL REGISTRY
// ═══════════════════════════════════════════════════════════════

/**
 * Well-known Uniswap V3 pools across chains
 */
export const UNISWAP_V3_POOLS: DexPoolConfig[] = [
  // ═══════════════════════════════════════════════════════════════
  // ETHEREUM MAINNET (chainId: 1)
  // ═══════════════════════════════════════════════════════════════
  {
    chainId: 1,
    pool: '0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640',
    name: 'ETH: WETH/USDC 0.05%',
    token0: 'WETH',
    token1: 'USDC',
    fee: 500,
    enabled: true,
  },
  {
    chainId: 1,
    pool: '0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8',
    name: 'ETH: WETH/USDC 0.3%',
    token0: 'WETH',
    token1: 'USDC',
    fee: 3000,
    enabled: true,
  },
  {
    chainId: 1,
    pool: '0x4e68ccd3e89f51c3074ca5072bbac773960dfa36',
    name: 'ETH: WETH/USDT 0.3%',
    token0: 'WETH',
    token1: 'USDT',
    fee: 3000,
    enabled: true,
  },
  {
    chainId: 1,
    pool: '0xcbcdf9626bc03e24f779434178a73a0b4bad62ed',
    name: 'ETH: WBTC/WETH 0.3%',
    token0: 'WBTC',
    token1: 'WETH',
    fee: 3000,
    enabled: true,
  },

  // ═══════════════════════════════════════════════════════════════
  // ARBITRUM (chainId: 42161)
  // ═══════════════════════════════════════════════════════════════
  {
    chainId: 42161,
    pool: '0xc6962004f452be9203591991d15f6b388e09e8d0',
    name: 'ARB: WETH/USDC 0.05%',
    token0: 'WETH',
    token1: 'USDC',
    fee: 500,
    enabled: true,
  },
  {
    chainId: 42161,
    pool: '0xc31e54c7a869b9fcbecc14363cf510d1c41fa443',
    name: 'ARB: WETH/USDC 0.3%',
    token0: 'WETH',
    token1: 'USDC',
    fee: 3000,
    enabled: true,
  },
  {
    chainId: 42161,
    pool: '0x641c00a822e8b671738d32a431a4fb6074e5c79d',
    name: 'ARB: WETH/USDT 0.05%',
    token0: 'WETH',
    token1: 'USDT',
    fee: 500,
    enabled: true,
  },

  // ═══════════════════════════════════════════════════════════════
  // OPTIMISM (chainId: 10)
  // ═══════════════════════════════════════════════════════════════
  {
    chainId: 10,
    pool: '0x85149247691df622eaf1a8bd0cafd40bc45154a9',
    name: 'OP: WETH/USDC 0.05%',
    token0: 'WETH',
    token1: 'USDC',
    fee: 500,
    enabled: true,
  },
  {
    chainId: 10,
    pool: '0x68f5c0a2de713a54991e01858fd27a3832401849',
    name: 'OP: WETH/OP 0.3%',
    token0: 'WETH',
    token1: 'OP',
    fee: 3000,
    enabled: true,
  },

  // ═══════════════════════════════════════════════════════════════
  // BASE (chainId: 8453)
  // ═══════════════════════════════════════════════════════════════
  {
    chainId: 8453,
    pool: '0xd0b53d9277642d899df5c87a3966a349a798f224',
    name: 'BASE: WETH/USDC 0.05%',
    token0: 'WETH',
    token1: 'USDC',
    fee: 500,
    enabled: true,
  },
  {
    chainId: 8453,
    pool: '0x4c36388be6f416a29c8d8eee81c771ce6be14b18',
    name: 'BASE: WETH/USDbC 0.05%',
    token0: 'WETH',
    token1: 'USDbC',
    fee: 500,
    enabled: true,
  },
];

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Get pools for specific chain
 */
export function getPoolsForChain(chainId: number): DexPoolConfig[] {
  return UNISWAP_V3_POOLS
    .filter(p => p.chainId === chainId && p.enabled)
    .map(p => ({ ...p, pool: p.pool.toLowerCase() }));
}

/**
 * Get pool addresses for specific chain
 */
export function getPoolAddressesForChain(chainId: number): string[] {
  return getPoolsForChain(chainId).map(p => p.pool);
}

/**
 * Check if chain has configured pools
 */
export function chainHasPools(chainId: number): boolean {
  return getPoolsForChain(chainId).length > 0;
}

/**
 * Get all supported chains with pools
 */
export function getChainsWithPools(): number[] {
  const chains = new Set<number>();
  for (const pool of UNISWAP_V3_POOLS) {
    if (pool.enabled) {
      chains.add(pool.chainId);
    }
  }
  return Array.from(chains);
}

console.log('[OnChain V2] DEX Pool Registry loaded');
