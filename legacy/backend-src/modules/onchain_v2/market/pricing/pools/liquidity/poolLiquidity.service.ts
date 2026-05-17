/**
 * OnChain V2 — Pool Liquidity Service
 * =====================================
 * 
 * STEP 4.1: TVL/Liquidity Scoring Integration
 * Aggregates liquidity data from multiple providers with fallback.
 */

import type { 
  PoolLiquidityProvider, 
  PoolLiquidityInput, 
  PoolLiquidityOutput,
  LiquidityRefreshResult,
  LiquidityHealthStatus,
  TvlSource,
} from './liquidity.types';
import { uniswapSubgraphProvider } from './uniswapSubgraph.provider';
import { defiLlamaProvider } from './defillama.provider';
import { DexPoolModel } from '../../../../ingestion/dex/models';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const ENABLED = process.env.ONCHAIN_V2_LIQUIDITY_ENABLED !== 'false';
const BATCH_SIZE = 50;
const RELIABILITY_THRESHOLD = 0.5;

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class PoolLiquidityService {
  private primary: PoolLiquidityProvider;
  private fallback: PoolLiquidityProvider;
  private lastRefreshResult: LiquidityRefreshResult | null = null;
  private lastRefreshAt: number | null = null;
  
  constructor(
    primary?: PoolLiquidityProvider,
    fallback?: PoolLiquidityProvider
  ) {
    // STEP 4.1: Use DeFiLlama as primary (no API key needed), Subgraph as fallback
    this.primary = primary || defiLlamaProvider;
    this.fallback = fallback || uniswapSubgraphProvider;
  }
  
  /**
   * Fetch liquidity for a batch of pools with fallback
   */
  async fetchLiquidity(input: PoolLiquidityInput[]): Promise<PoolLiquidityOutput[]> {
    if (!ENABLED || input.length === 0) {
      return input.map(p => ({
        chainId: p.chainId,
        poolAddress: p.poolAddress.toLowerCase(),
        liquidityUsd: null,
        volumeUsd24h: null,
        feesUsd24h: null,
        source: 'NONE' as TvlSource,
        reliability: 0,
        fetchedAt: Date.now(),
      }));
    }
    
    // Try primary provider first
    let results = await this.primary.fetchBatch(input);
    
    // Find pools that need fallback
    const needFallback = results
      .filter(r => !r.liquidityUsd || r.reliability < RELIABILITY_THRESHOLD)
      .map(r => ({ chainId: r.chainId, poolAddress: r.poolAddress }));
    
    if (needFallback.length > 0) {
      console.log(`[PoolLiquidity] ${needFallback.length} pools need fallback`);
      
      const fallbackResults = await this.fallback.fetchBatch(needFallback);
      const fallbackMap = new Map(
        fallbackResults.map(r => [`${r.chainId}:${r.poolAddress}`, r])
      );
      
      // Merge fallback results
      results = results.map(r => {
        const key = `${r.chainId}:${r.poolAddress}`;
        const fb = fallbackMap.get(key);
        
        // Use fallback if primary failed or has low reliability
        if (fb && (!r.liquidityUsd || r.reliability < RELIABILITY_THRESHOLD)) {
          return fb;
        }
        return r;
      });
    }
    
    return results;
  }
  
  /**
   * Refresh liquidity for all active pools on a chain
   */
  async refreshChain(chainId: number): Promise<LiquidityRefreshResult> {
    const startTime = Date.now();
    const errors: string[] = [];
    
    if (!ENABLED) {
      return {
        ok: false,
        chainId,
        poolsProcessed: 0,
        poolsUpdated: 0,
        avgLiquidityUsd: 0,
        source: 'NONE',
        errors: ['LIQUIDITY_DISABLED'],
        durationMs: Date.now() - startTime,
      };
    }
    
    // Get pools to update (ACTIVE + DEGRADED)
    const pools = await DexPoolModel.find({
      chainId,
      status: { $in: ['ACTIVE', 'DEGRADED', 'CANDIDATE'] },
    })
      .limit(500)
      .select({ address: 1, chainId: 1 })
      .lean();
    
    if (pools.length === 0) {
      return {
        ok: true,
        chainId,
        poolsProcessed: 0,
        poolsUpdated: 0,
        avgLiquidityUsd: 0,
        source: 'NONE',
        errors: [],
        durationMs: Date.now() - startTime,
      };
    }
    
    const input: PoolLiquidityInput[] = pools.map(p => ({
      chainId: p.chainId,
      poolAddress: p.address,
    }));
    
    // Fetch liquidity in batches
    let allResults: PoolLiquidityOutput[] = [];
    
    for (let i = 0; i < input.length; i += BATCH_SIZE) {
      const batch = input.slice(i, i + BATCH_SIZE);
      try {
        const batchResults = await this.fetchLiquidity(batch);
        allResults.push(...batchResults);
      } catch (err) {
        errors.push(`batch_${i}:${err instanceof Error ? err.message : 'unknown'}`);
      }
    }
    
    // Build lookup map
    const resultMap = new Map(
      allResults.map(r => [r.poolAddress.toLowerCase(), r])
    );
    
    // Update pools in database
    const now = Date.now();
    const bulkOps: any[] = [];
    let totalLiquidity = 0;
    let liquidityCount = 0;
    let primarySource: TvlSource = 'NONE';
    
    for (const pool of pools) {
      const result = resultMap.get(pool.address.toLowerCase());
      if (!result) continue;
      
      if (result.liquidityUsd !== null) {
        totalLiquidity += result.liquidityUsd;
        liquidityCount++;
        if (result.source !== 'NONE') {
          primarySource = result.source;
        }
      }
      
      bulkOps.push({
        updateOne: {
          filter: { _id: pool._id },
          update: {
            $set: {
              liquidityUsd: result.liquidityUsd || 0,
              volume24hUsd: result.volumeUsd24h || 0,
              tvlSource: result.source,
              tvlReliability: result.reliability,
              tvlUpdatedAt: now,
              updatedAt: now,
            },
          },
        },
      });
    }
    
    let poolsUpdated = 0;
    if (bulkOps.length > 0) {
      try {
        const writeResult = await DexPoolModel.bulkWrite(bulkOps, { ordered: false });
        poolsUpdated = writeResult.modifiedCount || 0;
      } catch (err) {
        errors.push(`bulkWrite:${err instanceof Error ? err.message : 'unknown'}`);
      }
    }
    
    const avgLiquidityUsd = liquidityCount > 0 ? totalLiquidity / liquidityCount : 0;
    
    const result: LiquidityRefreshResult = {
      ok: errors.length === 0,
      chainId,
      poolsProcessed: pools.length,
      poolsUpdated,
      avgLiquidityUsd: Math.round(avgLiquidityUsd),
      source: primarySource,
      errors,
      durationMs: Date.now() - startTime,
    };
    
    this.lastRefreshResult = result;
    this.lastRefreshAt = now;
    
    console.log(
      `[PoolLiquidity] Chain ${chainId}: ${poolsUpdated}/${pools.length} updated, ` +
      `avg TVL: $${(avgLiquidityUsd / 1000).toFixed(0)}K, ` +
      `source: ${primarySource}, ${result.durationMs}ms`
    );
    
    return result;
  }
  
  /**
   * Get health status
   */
  getHealth(): LiquidityHealthStatus {
    return {
      enabled: ENABLED,
      lastRefreshAt: this.lastRefreshAt,
      lastRefreshResult: this.lastRefreshResult,
      providers: [
        {
          name: this.primary.name,
          available: true,
          supportedChains: [1, 42161, 10, 8453],
        },
        {
          name: this.fallback.name,
          available: true,
          supportedChains: [1, 42161, 10, 8453, 137],
        },
      ],
    };
  }
  
  /**
   * Get stats for a chain
   */
  async getStats(chainId: number): Promise<{
    totalPools: number;
    poolsWithTvl: number;
    poolsWithVolume: number;
    avgLiquidityUsd: number;
    avgReliability: number;
    tvlCoverage: number;
  }> {
    const stats = await DexPoolModel.aggregate([
      { $match: { chainId } },
      {
        $group: {
          _id: null,
          totalPools: { $sum: 1 },
          poolsWithTvl: { $sum: { $cond: [{ $gt: ['$liquidityUsd', 0] }, 1, 0] } },
          poolsWithVolume: { $sum: { $cond: [{ $gt: ['$volume24hUsd', 0] }, 1, 0] } },
          totalLiquidity: { $sum: { $ifNull: ['$liquidityUsd', 0] } },
          totalReliability: { $sum: { $ifNull: ['$tvlReliability', 0] } },
        },
      },
    ]);
    
    const s = stats[0] || { totalPools: 0, poolsWithTvl: 0, poolsWithVolume: 0, totalLiquidity: 0, totalReliability: 0 };
    
    return {
      totalPools: s.totalPools,
      poolsWithTvl: s.poolsWithTvl,
      poolsWithVolume: s.poolsWithVolume,
      avgLiquidityUsd: s.poolsWithTvl > 0 ? Math.round(s.totalLiquidity / s.poolsWithTvl) : 0,
      avgReliability: s.totalPools > 0 ? +(s.totalReliability / s.totalPools).toFixed(3) : 0,
      tvlCoverage: s.totalPools > 0 ? +(s.poolsWithTvl / s.totalPools).toFixed(3) : 0,
    };
  }
}

export const poolLiquidityService = new PoolLiquidityService();

console.log('[OnChain V2] Pool Liquidity Service loaded');
