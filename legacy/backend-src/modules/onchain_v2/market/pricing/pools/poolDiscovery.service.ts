/**
 * OnChain V2 — Pool Discovery Service
 * =====================================
 * 
 * STEP 4: Discovers pools for Token Universe tokens
 * Uses both swap-based candidates AND known universe tokens.
 */

import { DexPoolModel } from '../../../ingestion/dex/models';
import { poolMetaResolver } from '../../../ingestion/dex/poolMeta.resolver';
import { tokenCandidatesService } from './tokenCandidates.service';
import { poolFinderService } from './poolFinder.service';
import { DISCOVERY } from './poolScoring.constants';
import { getAltTokenAddresses } from '../../../market/flow/tokenUniverse';
import type { RpcChainId } from '../../../rpc-pool/models';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface DiscoveryResult {
  ok: boolean;
  chainId: number;
  mode: 'swaps' | 'universe' | 'both';
  tokensScanned: number;
  poolsFound: number;
  poolsUpserted: number;
  errors: string[];
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class PoolDiscoveryService {
  
  /**
   * Discover new pools from Token Universe (known alts)
   */
  async discoverFromUniverse(args: { chainId: number }): Promise<DiscoveryResult> {
    const { chainId } = args;
    const errors: string[] = [];
    
    // Get stables and bases
    const stables = DISCOVERY.getStables(chainId);
    const bases = DISCOVERY.getBases(chainId);
    
    if (!stables.length) {
      return { 
        ok: false, chainId, mode: 'universe',
        tokensScanned: 0, poolsFound: 0, poolsUpserted: 0,
        errors: ['NO_STABLES_CONFIG'],
      };
    }
    
    if (!poolFinderService.hasFactory(chainId)) {
      return { 
        ok: false, chainId, mode: 'universe',
        tokensScanned: 0, poolsFound: 0, poolsUpserted: 0,
        errors: ['NO_FACTORY_CONFIG'],
      };
    }
    
    // Get all alt tokens from universe
    const altTokens = getAltTokenAddresses(chainId);
    
    if (!altTokens.length) {
      return { 
        ok: true, chainId, mode: 'universe',
        tokensScanned: 0, poolsFound: 0, poolsUpserted: 0,
        errors: [],
      };
    }
    
    const bulk: any[] = [];
    let poolsFound = 0;
    const now = Date.now();
    
    // For each alt token, find pools with stables and bases
    for (const token of altTokens) {
      if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) break;
      
      // Find stable pools
      for (const stable of stables) {
        if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) break;
        if (token.toLowerCase() === stable.toLowerCase()) continue;
        
        try {
          const pools = await poolFinderService.findUniV3Pools({ 
            chainId, tokenA: token, tokenB: stable,
          });
          
          for (const p of pools) {
            if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) break;
            
            const meta = await poolMetaResolver.get(chainId as RpcChainId, p.pool);
            if (!meta?.token0 || !meta?.token1) continue;
            
            poolsFound++;
            
            bulk.push({
              updateOne: {
                filter: { chainId, address: p.pool },
                update: {
                  $setOnInsert: {
                    chainId,
                    protocol: 'uniswap_v3',
                    address: p.pool,
                    fee: p.fee,
                    token0: meta.token0,
                    token1: meta.token1,
                    isStablePair: true,
                    stableToken: stable,
                    status: 'CANDIDATE',
                    statusReason: 'DISCOVERED_UNIVERSE',
                    enabled: true,
                    priority: 1, // Higher priority for universe tokens
                    totalSwapsIndexed: 0,
                    addedAt: now,
                    updatedAt: now,
                  },
                },
                upsert: true,
              },
            });
          }
        } catch (e) {
          errors.push(`stable:${token.slice(0,10)}:${e}`);
        }
      }
      
      // Find base pools (WETH/WBTC)
      for (const base of bases) {
        if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) break;
        if (token.toLowerCase() === base.toLowerCase()) continue;
        
        try {
          const pools = await poolFinderService.findUniV3Pools({ 
            chainId, tokenA: token, tokenB: base,
          });
          
          for (const p of pools) {
            if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) break;
            
            const meta = await poolMetaResolver.get(chainId as RpcChainId, p.pool);
            if (!meta?.token0 || !meta?.token1) continue;
            
            poolsFound++;
            
            bulk.push({
              updateOne: {
                filter: { chainId, address: p.pool },
                update: {
                  $setOnInsert: {
                    chainId,
                    protocol: 'uniswap_v3',
                    address: p.pool,
                    fee: p.fee,
                    token0: meta.token0,
                    token1: meta.token1,
                    isStablePair: false,
                    stableToken: '',
                    status: 'CANDIDATE',
                    statusReason: 'DISCOVERED_UNIVERSE',
                    enabled: true,
                    priority: 1,
                    totalSwapsIndexed: 0,
                    addedAt: now,
                    updatedAt: now,
                  },
                },
                upsert: true,
              },
            });
          }
        } catch (e) {
          errors.push(`base:${token.slice(0,10)}:${e}`);
        }
      }
    }
    
    // Execute bulk upsert
    let poolsUpserted = 0;
    if (bulk.length > 0) {
      try {
        const result = await DexPoolModel.bulkWrite(bulk, { ordered: false });
        poolsUpserted = result.upsertedCount || 0;
      } catch (e: any) {
        if (e.code !== 11000) {
          errors.push(`bulkWrite:${e.message}`);
        }
        poolsUpserted = e.result?.nUpserted || 0;
      }
    }
    
    return {
      ok: errors.length === 0,
      chainId,
      mode: 'universe',
      tokensScanned: altTokens.length,
      poolsFound,
      poolsUpserted,
      errors,
    };
  }
  
  /**
   * Discover new pools from top traded tokens (swap-based)
   */
  async discover(args: { 
    chainId: number; 
    window: '24h' | '7d';
  }): Promise<DiscoveryResult> {
    const { chainId, window } = args;
    const errors: string[] = [];
    
    // Get stables and bases for chain (use dynamic getters)
    const stables = DISCOVERY.getStables(chainId);
    const bases = DISCOVERY.getBases(chainId);
    
    if (!stables.length) {
      return { 
        ok: false, chainId, mode: 'swaps',
        tokensScanned: 0, poolsFound: 0, poolsUpserted: 0,
        errors: ['NO_STABLES_CONFIG'],
      };
    }
    
    if (!poolFinderService.hasFactory(chainId)) {
      return { 
        ok: false, 
        chainId, 
        window, 
        tokensScanned: 0, 
        poolsFound: 0, 
        poolsUpserted: 0,
        errors: ['NO_FACTORY_CONFIG'],
      };
    }
    
    // Get top traded tokens
    const topTokens = await tokenCandidatesService.getTopTokensFromDex({ chainId, window });
    
    if (!topTokens.length) {
      return { 
        ok: true, 
        chainId, 
        window, 
        tokensScanned: 0, 
        poolsFound: 0, 
        poolsUpserted: 0,
        errors: [],
      };
    }
    
    const bulk: any[] = [];
    let poolsFound = 0;
    const now = Date.now();
    
    // For each top token, find pools with stables and bases
    for (const t of topTokens) {
      const token = t.token;
      
      // Skip if token is itself a stable or base
      if (stables.includes(token) || bases.includes(token)) {
        continue;
      }
      
      // Limit total new pools per tick
      if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) {
        break;
      }
      
      // Find stable pools
      for (const stable of stables) {
        if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) break;
        
        try {
          const pools = await poolFinderService.findUniV3Pools({ 
            chainId, 
            tokenA: token, 
            tokenB: stable,
          });
          
          for (const p of pools) {
            if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) break;
            
            // Get pool metadata (token0/token1)
            const meta = await poolMetaResolver.get(chainId as RpcChainId, p.pool);
            if (!meta?.token0 || !meta?.token1) continue;
            
            poolsFound++;
            
            bulk.push({
              updateOne: {
                filter: { chainId, address: p.pool },
                update: {
                  $setOnInsert: {
                    chainId,
                    protocol: 'uniswap_v3',
                    address: p.pool,
                    fee: p.fee,
                    token0: meta.token0,
                    token1: meta.token1,
                    isStablePair: true,
                    stableToken: stable,
                    status: 'CANDIDATE',
                    statusReason: `DISCOVERED_${window}`,
                    enabled: true,
                    priority: 0,
                    totalSwapsIndexed: 0,
                    addedAt: now,
                    updatedAt: now,
                  },
                },
                upsert: true,
              },
            });
          }
        } catch (e) {
          errors.push(`stable:${token}:${stable}:${e}`);
        }
      }
      
      // Find base pools (WETH/WBTC)
      for (const base of bases) {
        if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) break;
        
        try {
          const pools = await poolFinderService.findUniV3Pools({ 
            chainId, 
            tokenA: token, 
            tokenB: base,
          });
          
          for (const p of pools) {
            if (bulk.length >= DISCOVERY.MAX_NEW_POOLS_PER_TICK) break;
            
            const meta = await poolMetaResolver.get(chainId as RpcChainId, p.pool);
            if (!meta?.token0 || !meta?.token1) continue;
            
            poolsFound++;
            
            bulk.push({
              updateOne: {
                filter: { chainId, address: p.pool },
                update: {
                  $setOnInsert: {
                    chainId,
                    protocol: 'uniswap_v3',
                    address: p.pool,
                    fee: p.fee,
                    token0: meta.token0,
                    token1: meta.token1,
                    isStablePair: false,
                    stableToken: '',
                    status: 'CANDIDATE',
                    statusReason: `DISCOVERED_${window}`,
                    enabled: true,
                    priority: 0,
                    totalSwapsIndexed: 0,
                    addedAt: now,
                    updatedAt: now,
                  },
                },
                upsert: true,
              },
            });
          }
        } catch (e) {
          errors.push(`base:${token}:${base}:${e}`);
        }
      }
    }
    
    // Execute bulk upsert
    let poolsUpserted = 0;
    if (bulk.length > 0) {
      try {
        const result = await DexPoolModel.bulkWrite(bulk, { ordered: false });
        poolsUpserted = result.upsertedCount || 0;
      } catch (e: any) {
        if (e.code !== 11000) {
          errors.push(`bulkWrite:${e.message}`);
        }
        poolsUpserted = e.result?.nUpserted || 0;
      }
    }
    
    return {
      ok: errors.length === 0,
      chainId,
      window,
      tokensScanned: topTokens.length,
      poolsFound,
      poolsUpserted,
      errors,
    };
  }
  
  /**
   * Get discovery stats
   */
  async getStats(chainId: number): Promise<{
    totalPools: number;
    byStatus: Record<string, number>;
    stablePairs: number;
    basePairs: number;
  }> {
    const stats = await DexPoolModel.aggregate([
      { $match: { chainId } },
      {
        $group: {
          _id: null,
          total: { $sum: 1 },
          stablePairs: { $sum: { $cond: ['$isStablePair', 1, 0] } },
          basePairs: { $sum: { $cond: [{ $eq: ['$isStablePair', false] }, 1, 0] } },
        },
      },
    ]);
    
    const statusStats = await DexPoolModel.aggregate([
      { $match: { chainId } },
      { $group: { _id: '$status', count: { $sum: 1 } } },
    ]);
    
    const byStatus: Record<string, number> = {};
    for (const s of statusStats) {
      byStatus[s._id || 'CANDIDATE'] = s.count;
    }
    
    const s = stats[0] || { total: 0, stablePairs: 0, basePairs: 0 };
    
    return {
      totalPools: s.total,
      byStatus,
      stablePairs: s.stablePairs,
      basePairs: s.basePairs,
    };
  }
}

export const poolDiscoveryService = new PoolDiscoveryService();

console.log('[OnChain V2] Pool Discovery Service loaded');
