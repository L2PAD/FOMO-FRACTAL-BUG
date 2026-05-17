/**
 * OnChain V2 — DeFiLlama Liquidity Provider (Fallback)
 * ======================================================
 * 
 * STEP 4.1: TVL/Liquidity Scoring Integration
 * Fallback provider using DeFiLlama pools API.
 */

import type { 
  PoolLiquidityProvider, 
  PoolLiquidityInput, 
  PoolLiquidityOutput,
  TvlSource,
} from './liquidity.types';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const DEFILLAMA_POOLS_URL = 'https://yields.llama.fi/pools';
const REQUEST_TIMEOUT_MS = 20000;
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

// Chain name mapping for DeFiLlama
const CHAIN_NAMES: Record<number, string> = {
  1: 'Ethereum',
  42161: 'Arbitrum',
  10: 'Optimism',
  8453: 'Base',
  137: 'Polygon',
  43114: 'Avalanche',
};

// ═══════════════════════════════════════════════════════════════
// DEFILLAMA RESPONSE TYPES
// ═══════════════════════════════════════════════════════════════

interface DefiLlamaPool {
  pool: string;        // pool ID (UUID)
  chain: string;
  project: string;
  symbol: string;
  tvlUsd: number;
  apyBase?: number;
  apyReward?: number;
  apy?: number;
  volumeUsd1d?: number;
  volumeUsd7d?: number;
  poolMeta?: string;           // fee tier, e.g. "0.05%"
  underlyingTokens?: string[]; // token addresses!
}

interface DefiLlamaResponse {
  status: string;
  data: DefiLlamaPool[];
}

// ═══════════════════════════════════════════════════════════════
// PROVIDER IMPLEMENTATION
// ═══════════════════════════════════════════════════════════════

export class DefiLlamaProvider implements PoolLiquidityProvider {
  name: TvlSource = 'DEFILLAMA';
  
  // Cache all pools data
  private cache: {
    data: Map<string, DefiLlamaPool>;
    fetchedAt: number;
  } | null = null;
  
  supportsChain(chainId: number): boolean {
    return chainId in CHAIN_NAMES;
  }
  
  async fetchBatch(input: PoolLiquidityInput[]): Promise<PoolLiquidityOutput[]> {
    if (input.length === 0) return [];
    
    const now = Date.now();
    
    // Refresh cache if needed
    await this.refreshCache();
    
    if (!this.cache) {
      return input.map(p => this.emptyResult(p, now));
    }
    
    // Load pool details from DB to get token addresses
    const poolDetails = await this.loadPoolDetails(input);
    
    const results: PoolLiquidityOutput[] = [];
    
    for (const p of input) {
      const chainName = CHAIN_NAMES[p.chainId];
      if (!chainName) {
        results.push(this.emptyResult(p, now));
        continue;
      }
      
      const detail = poolDetails.get(`${p.chainId}:${p.poolAddress.toLowerCase()}`);
      
      // Try to find pool in cache using token pair
      const poolData = this.findPool(p.poolAddress, chainName, detail);
      
      if (poolData) {
        results.push(this.parsePoolData(p, poolData, now));
      } else {
        results.push(this.emptyResult(p, now));
      }
    }
    
    return results;
  }
  
  /**
   * Load pool details from DB
   */
  private async loadPoolDetails(input: PoolLiquidityInput[]): Promise<Map<string, { token0: string; token1: string; fee?: number }>> {
    const map = new Map<string, { token0: string; token1: string; fee?: number }>();
    
    try {
      // Dynamic import to avoid circular dependency
      const { DexPoolModel } = await import('../../../../ingestion/dex/models');
      
      const addresses = input.map(p => p.poolAddress.toLowerCase());
      const pools = await DexPoolModel.find({
        address: { $in: addresses },
      })
        .select({ chainId: 1, address: 1, token0: 1, token1: 1, fee: 1 })
        .lean();
      
      for (const pool of pools) {
        const key = `${pool.chainId}:${pool.address}`;
        map.set(key, { 
          token0: pool.token0, 
          token1: pool.token1,
          fee: pool.fee,
        });
      }
    } catch (err) {
      console.error('[DeFiLlama] Failed to load pool details:', err);
    }
    
    return map;
  }
  
  private async refreshCache(): Promise<void> {
    const now = Date.now();
    
    // Check if cache is still valid
    if (this.cache && (now - this.cache.fetchedAt) < CACHE_TTL_MS) {
      return;
    }
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      
      const response = await fetch(DEFILLAMA_POOLS_URL, {
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const json = await response.json() as DefiLlamaResponse;
      
      if (json.status !== 'success' || !json.data) {
        throw new Error('Invalid response');
      }
      
      // Filter to Uniswap V3 pools and build lookup maps
      const uniswapV3Pools = json.data.filter(p => 
        p.project === 'uniswap-v3' || 
        p.project === 'uniswap'
      );
      
      const poolMap = new Map<string, DefiLlamaPool>();
      
      for (const pool of uniswapV3Pools) {
        const chainName = pool.chain.toLowerCase();
        
        // Build lookup key from underlying tokens (sorted)
        // This allows matching by token pair
        if (pool.underlyingTokens && pool.underlyingTokens.length === 2) {
          const tokens = pool.underlyingTokens.map(t => t.toLowerCase()).sort();
          const tokenPairKey = `${chainName}-${tokens[0]}-${tokens[1]}`;
          
          // Store with fee tier suffix if available
          const feeTier = pool.poolMeta?.replace('%', '') || '';
          const keyWithFee = `${tokenPairKey}-${feeTier}`;
          poolMap.set(keyWithFee, pool);
          
          // Also store without fee tier for fallback matching
          if (!poolMap.has(tokenPairKey)) {
            poolMap.set(tokenPairKey, pool);
          }
        }
        
        // Also store by symbol for additional matching
        const symbolKey = `${chainName}-${pool.symbol.toLowerCase()}`;
        if (!poolMap.has(symbolKey)) {
          poolMap.set(symbolKey, pool);
        }
      }
      
      this.cache = {
        data: poolMap,
        fetchedAt: now,
      };
      
      console.log(`[DeFiLlama] Cache refreshed: ${poolMap.size} Uniswap V3 pools indexed`);
      
    } catch (err) {
      console.error('[DeFiLlama] Cache refresh error:', err);
      // Keep old cache if refresh fails
    }
  }
  
  private findPool(
    poolAddress: string, 
    chainName: string,
    detail?: { token0: string; token1: string; fee?: number }
  ): DefiLlamaPool | null {
    if (!this.cache) return null;
    
    const chainKey = chainName.toLowerCase();
    
    // Primary: Match by sorted token pair + fee tier
    if (detail?.token0 && detail?.token1) {
      const tokens = [detail.token0.toLowerCase(), detail.token1.toLowerCase()].sort();
      const tokenPairKey = `${chainKey}-${tokens[0]}-${tokens[1]}`;
      
      // Try with fee tier first
      if (detail.fee) {
        const feePct = (detail.fee / 10000).toFixed(2);  // 500 -> "0.05"
        const keyWithFee = `${tokenPairKey}-${feePct}`;
        const poolWithFee = this.cache.data.get(keyWithFee);
        if (poolWithFee) return poolWithFee;
      }
      
      // Fallback to token pair without fee
      const pool = this.cache.data.get(tokenPairKey);
      if (pool) return pool;
    }
    
    return null;
  }
  
  private parsePoolData(
    input: PoolLiquidityInput, 
    data: DefiLlamaPool, 
    now: number
  ): PoolLiquidityOutput {
    const liquidityUsd = data.tvlUsd || null;
    const volumeUsd24h = data.volumeUsd1d || null;
    
    // DeFiLlama doesn't provide fees directly, estimate from APY
    let feesUsd24h: number | null = null;
    if (liquidityUsd && data.apyBase) {
      // APY base is the fee APY, convert to daily fees
      feesUsd24h = (liquidityUsd * data.apyBase / 100) / 365;
    }
    
    // Lower reliability than subgraph (aggregated data)
    let reliability = 0.7;
    if (!liquidityUsd || liquidityUsd < 1000) reliability *= 0.5;
    if (!volumeUsd24h) reliability *= 0.8;
    
    return {
      chainId: input.chainId,
      poolAddress: input.poolAddress.toLowerCase(),
      liquidityUsd,
      volumeUsd24h,
      feesUsd24h,
      source: 'DEFILLAMA',
      reliability,
      fetchedAt: now,
    };
  }
  
  private emptyResult(input: PoolLiquidityInput, now: number): PoolLiquidityOutput {
    return {
      chainId: input.chainId,
      poolAddress: input.poolAddress.toLowerCase(),
      liquidityUsd: null,
      volumeUsd24h: null,
      feesUsd24h: null,
      source: 'NONE',
      reliability: 0,
      fetchedAt: now,
    };
  }
}

export const defiLlamaProvider = new DefiLlamaProvider();

console.log('[OnChain V2] DeFiLlama Provider loaded');
