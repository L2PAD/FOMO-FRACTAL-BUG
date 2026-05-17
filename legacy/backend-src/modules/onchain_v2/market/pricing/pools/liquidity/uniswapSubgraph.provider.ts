/**
 * OnChain V2 — Uniswap V3 Subgraph Liquidity Provider
 * =====================================================
 * 
 * STEP 4.1: TVL/Liquidity Scoring Integration
 * Fetches pool liquidity data from Uniswap V3 Subgraph.
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

// TheGraph decentralized network endpoints (require API key but have free tier)
// These are the deployment IDs for Uniswap V3 subgraphs
const SUBGRAPH_IDS: Record<number, string> = {
  // Ethereum mainnet - Uniswap V3
  1: '5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV',
  // Arbitrum
  42161: 'FbCGRftH4a3yZugY7TnbYgPJVEv2LvMT6oF1fxPe9aJM',
  // Optimism  
  10: 'Cghf4LfVqPiFw6fp6Y5X5Ubc8UpmUhSfJL82zwiBFLaj',
  // Base
  8453: '43Hwfi3dJSoGpyas9VwXe6bYPFBwmmK3MNT64zKLs7X9',
};

// TheGraph gateway URL
const THEGRAPH_GATEWAY = 'https://gateway.thegraph.com/api';

const BATCH_SIZE = 100;
const REQUEST_TIMEOUT_MS = 15000;

// ═══════════════════════════════════════════════════════════════
// SUBGRAPH RESPONSE TYPES
// ═══════════════════════════════════════════════════════════════

interface SubgraphPool {
  id: string;
  totalValueLockedUSD: string;
  volumeUSD: string;
  feesUSD: string;
  liquidity: string;
}

interface SubgraphResponse {
  data?: {
    pools: SubgraphPool[];
  };
  errors?: Array<{ message: string }>;
}

// ═══════════════════════════════════════════════════════════════
// PROVIDER IMPLEMENTATION
// ═══════════════════════════════════════════════════════════════

export class UniswapSubgraphProvider implements PoolLiquidityProvider {
  name: TvlSource = 'UNISWAP_SUBGRAPH';
  
  private apiKey: string | null;
  
  constructor(apiKey?: string) {
    // TheGraph API key (required for decentralized network)
    this.apiKey = apiKey || process.env.THEGRAPH_API_KEY || null;
    if (!this.apiKey) {
      console.warn('[UniswapSubgraph] No THEGRAPH_API_KEY - will use fallback provider');
    }
  }
  
  supportsChain(chainId: number): boolean {
    return chainId in SUBGRAPH_IDS;
  }
  
  async fetchBatch(input: PoolLiquidityInput[]): Promise<PoolLiquidityOutput[]> {
    if (input.length === 0) return [];
    
    const now = Date.now();
    const results: PoolLiquidityOutput[] = [];
    
    // Group by chainId
    const byChain = new Map<number, PoolLiquidityInput[]>();
    for (const p of input) {
      const list = byChain.get(p.chainId) || [];
      list.push(p);
      byChain.set(p.chainId, list);
    }
    
    // Process each chain
    for (const [chainId, pools] of byChain) {
      const chainResults = await this.fetchChainBatch(chainId, pools, now);
      results.push(...chainResults);
    }
    
    return results;
  }
  
  private async fetchChainBatch(
    chainId: number, 
    pools: PoolLiquidityInput[],
    now: number
  ): Promise<PoolLiquidityOutput[]> {
    const url = this.getSubgraphUrl(chainId);
    if (!url) {
      return pools.map(p => this.emptyResult(p, now));
    }
    
    const results: PoolLiquidityOutput[] = [];
    
    // Process in batches
    for (let i = 0; i < pools.length; i += BATCH_SIZE) {
      const batch = pools.slice(i, i + BATCH_SIZE);
      const addresses = batch.map(p => p.poolAddress.toLowerCase());
      
      try {
        const query = this.buildQuery(addresses);
        const response = await this.executeQuery(url, query);
        
        if (!response.data?.pools) {
          // Fallback to empty results
          results.push(...batch.map(p => this.emptyResult(p, now)));
          continue;
        }
        
        // Map response to results
        const poolMap = new Map<string, SubgraphPool>();
        for (const pool of response.data.pools) {
          poolMap.set(pool.id.toLowerCase(), pool);
        }
        
        for (const p of batch) {
          const data = poolMap.get(p.poolAddress.toLowerCase());
          if (data) {
            results.push(this.parsePoolData(p, data, now));
          } else {
            results.push(this.emptyResult(p, now));
          }
        }
      } catch (err) {
        console.error(`[UniswapSubgraph] Batch error for chain ${chainId}:`, err);
        results.push(...batch.map(p => this.emptyResult(p, now)));
      }
    }
    
    return results;
  }
  
  private getSubgraphUrl(chainId: number): string | null {
    const subgraphId = SUBGRAPH_IDS[chainId];
    if (!subgraphId) return null;
    
    // TheGraph decentralized network requires API key
    if (!this.apiKey) {
      console.log(`[UniswapSubgraph] No API key, skipping chain ${chainId}`);
      return null;
    }
    
    return `${THEGRAPH_GATEWAY}/${this.apiKey}/subgraphs/id/${subgraphId}`;
  }
  
  private buildQuery(poolAddresses: string[]): string {
    const addressList = poolAddresses.map(a => `"${a}"`).join(',');
    return `{
      pools(where: { id_in: [${addressList}] }, first: ${BATCH_SIZE}) {
        id
        totalValueLockedUSD
        volumeUSD
        feesUSD
        liquidity
      }
    }`;
  }
  
  private async executeQuery(url: string, query: string): Promise<SubgraphResponse> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      return await response.json() as SubgraphResponse;
    } catch (err) {
      clearTimeout(timeoutId);
      throw err;
    }
  }
  
  private parsePoolData(
    input: PoolLiquidityInput, 
    data: SubgraphPool, 
    now: number
  ): PoolLiquidityOutput {
    const liquidityUsd = parseFloat(data.totalValueLockedUSD) || null;
    const volumeUsd24h = parseFloat(data.volumeUSD) || null;
    const feesUsd24h = parseFloat(data.feesUSD) || null;
    
    // Calculate reliability based on data quality
    let reliability = 0.9; // Base reliability for subgraph
    if (!liquidityUsd || liquidityUsd < 1000) reliability *= 0.5;
    if (!volumeUsd24h) reliability *= 0.8;
    
    return {
      chainId: input.chainId,
      poolAddress: input.poolAddress.toLowerCase(),
      liquidityUsd,
      volumeUsd24h,
      feesUsd24h,
      source: 'UNISWAP_SUBGRAPH',
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

export const uniswapSubgraphProvider = new UniswapSubgraphProvider();

console.log('[OnChain V2] Uniswap Subgraph Provider loaded');
