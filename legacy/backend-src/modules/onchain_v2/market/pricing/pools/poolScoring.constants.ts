/**
 * OnChain V2 — Pool Scoring Constants
 * =====================================
 * 
 * STEP 2: Pool Scoring & Auto-Activation
 * STEP 4: Expanded coverage with Token Universe
 */

import { 
  getStableAddresses, 
  getBaseAddresses, 
  getAltTokenAddresses,
} from '../../../market/flow/tokenUniverse';

export const SCORING = {
  VERSION: 'v2.1.1', // STEP 4.1 TVL-based scoring (adjusted thresholds)
  
  // Score thresholds for auto-activation (STEP 4.1 hardened but realistic)
  ACTIVE_SCORE_MIN: 55,           // Lowered from 70 - good TVL pools should qualify
  ACTIVE_CONFIDENCE_MIN: 0.40,    // Lowered from 0.45
  ACTIVE_DEV_MAX_BPS: 150,
  ACTIVE_LIQUIDITY_MIN_USD: 1_000_000,   // Min $1M TVL for ACTIVE
  ACTIVE_VOLUME_MIN_USD: 100_000,        // Min $100k 24h volume for ACTIVE
  
  DEGRADED_SCORE_MIN: 35,         // Lowered from 45
  DEGRADED_CONFIDENCE_MIN: 0.20,  // Lowered from 0.25
  
  // Score pivots (log scale) - adjusted for realistic range
  LIQUIDITY_PIVOT_USD: 1_000_000,   // $1M TVL = mid score
  VOLUME_PIVOT_USD: 100_000,        // $100k volume = mid score
  TRADES_PIVOT: 100,                // 100 trades/day = mid score
  
  // Score weights (STEP 4.1 TVL-focused)
  WEIGHTS: {
    liquidity: 0.45,    // TVL is primary signal (increased)
    volume: 0.25,       // Volume confirms activity (increased)
    activity: 0.10,     // Trade count (reduced - often missing)
    freshness: 0.05,    // Recent data bonus (reduced)
    feeTier: 0.05,      // Fee tier preference
    deviation: 0.05,    // Price accuracy
    reliability: 0.05,  // TVL data reliability
  },
};

// Helper to get stables from Token Universe
function getStablesForChain(chainId: number): string[] {
  const stables = getStableAddresses(chainId);
  if (stables.length > 0) return stables;
  // Fallback to hardcoded if universe empty
  return FALLBACK_STABLES[chainId] || [];
}

// Helper to get bases from Token Universe  
function getBasesForChain(chainId: number): string[] {
  const bases = getBaseAddresses(chainId);
  if (bases.length > 0) return bases;
  return FALLBACK_BASES[chainId] || [];
}

// Fallback stables (if universe not loaded)
const FALLBACK_STABLES: Record<number, string[]> = {
  1: [
    '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', // USDC
    '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT
    '0x6b175474e89094c44da98b954eedeac495271d0f', // DAI
  ],
  42161: [
    '0xaf88d065e77c8cc2239327c5edb3a432268e5831', // USDC native
    '0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9', // USDT
  ],
  10: [
    '0x0b2c639c533813f4aa9d7837caf62653d097ff85', // USDC native
    '0x94b008aa00579c1307b0ef2c499ad98a8ce58e58', // USDT
  ],
  8453: [
    '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913', // USDC native
  ],
};

// Fallback bases
const FALLBACK_BASES: Record<number, string[]> = {
  1: [
    '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', // WETH
    '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599', // WBTC
  ],
  42161: [
    '0x82af49447d8a07e3bd95bd0d56f35241523fbab1', // WETH
    '0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f', // WBTC
  ],
  10: [
    '0x4200000000000000000000000000000000000006', // WETH
  ],
  8453: [
    '0x4200000000000000000000000000000000000006', // WETH
  ],
};

export const DISCOVERY = {
  VERSION: 'v2.1.0',
  
  // Dynamic getters for stables/bases from Token Universe
  getStables: getStablesForChain,
  getBases: getBasesForChain,
  getAlts: getAltTokenAddresses,
  
  // Static fallbacks for backward compatibility
  STABLES: FALLBACK_STABLES,
  BASES: FALLBACK_BASES,
  
  // Uniswap V3 fee tiers
  FEES: [100, 500, 3000, 10000],
  
  // Uniswap V3 Factory addresses
  UNIV3_FACTORY: {
    1: '0x1F98431c8aD98523631AE4a59f267346ea31F984',
    42161: '0x1F98431c8aD98523631AE4a59f267346ea31F984',
    10: '0x1F98431c8aD98523631AE4a59f267346ea31F984',
    8453: '0x33128a8fC17869897dcE68Ed026d694621f6FDfD',
  } as Record<number, string>,
  
  // Discovery limits
  TOP_TOKENS_LIMIT: 100,      // Increased from 50
  MIN_TRADES_24H: 10,         // Lowered from 20
  MIN_VOLUME_USD_24H: 50_000, // Lowered from 100K
  MAX_NEW_POOLS_PER_TICK: 60, // Increased from 40
};

console.log('[OnChain V2] Pool Scoring Constants v2 loaded');

