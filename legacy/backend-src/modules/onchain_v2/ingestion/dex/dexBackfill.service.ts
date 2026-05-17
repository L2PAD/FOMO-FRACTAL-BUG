/**
 * OnChain V2 — DEX Backfill Service
 * ===================================
 * 
 * PHASE 3.5.5: Backfill token0/token1 for existing swaps
 * 
 * Steps:
 * 1. Collect unique pools from swaps with missing tokens
 * 2. Resolve pool metadata via PoolMetaResolver
 * 3. Patch swaps with resolved tokens
 */

import { DexSwapModel, DexPoolModel } from './models.js';
import { poolMetaResolver } from './poolMeta.resolver.js';
import type { RpcChainId } from '../../rpc-pool/models.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface BackfillPoolsResult {
  chainId: number;
  poolsTotal: number;
  resolved: number;
  failed: number;
  alreadyHadMeta: number;
}

export interface BackfillSwapsResult {
  chainId: number;
  swapsChecked: number;
  patched: number;
  skipped: number;
  remaining: number;
}

export interface BackfillStatus {
  chainId: number;
  swapsWithoutTokens: number;
  poolsWithoutTokens: number;
  poolsTotal: number;
  swapsTotal: number;
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

class DexBackfillService {
  
  /**
   * Get current backfill status
   */
  async getStatus(chainId: RpcChainId): Promise<BackfillStatus> {
    const [swapsWithoutTokens, poolsWithoutTokens, poolsTotal, swapsTotal] = await Promise.all([
      DexSwapModel.countDocuments({
        chainId,
        $or: [
          { token0: { $in: [null, ''] } },
          { token1: { $in: [null, ''] } },
        ],
      }),
      DexPoolModel.countDocuments({
        chainId,
        $or: [
          { token0: { $in: [null, ''] } },
          { token1: { $in: [null, ''] } },
        ],
      }),
      DexPoolModel.countDocuments({ chainId }),
      DexSwapModel.countDocuments({ chainId }),
    ]);
    
    return {
      chainId,
      swapsWithoutTokens,
      poolsWithoutTokens,
      poolsTotal,
      swapsTotal,
    };
  }
  
  /**
   * Phase 1: Backfill pool metadata
   * Finds unique pools from swaps that are missing token info and resolves them
   */
  async backfillPools(chainId: RpcChainId, limit: number = 500): Promise<BackfillPoolsResult> {
    // Get unique pools from swaps that have missing tokens
    const poolsToResolve = await DexSwapModel.aggregate([
      {
        $match: {
          chainId,
          $or: [
            { token0: { $in: [null, ''] } },
            { token1: { $in: [null, ''] } },
          ],
        },
      },
      { $group: { _id: '$pool' } },
      { $limit: limit },
    ]);
    
    const poolAddresses = poolsToResolve
      .map((p: { _id: string }) => p._id)
      .filter(Boolean);
    
    if (poolAddresses.length === 0) {
      return { chainId, poolsTotal: 0, resolved: 0, failed: 0, alreadyHadMeta: 0 };
    }
    
    let resolved = 0;
    let failed = 0;
    let alreadyHadMeta = 0;
    
    console.log(`[DexBackfill] Resolving ${poolAddresses.length} pools for chain ${chainId}...`);
    
    for (const poolAddr of poolAddresses) {
      // Check if pool already has metadata in DB
      const existing = await DexPoolModel.findOne({ 
        chainId, 
        address: poolAddr.toLowerCase(),
        token0: { $nin: [null, ''] },
        token1: { $nin: [null, ''] },
      }).lean();
      
      if (existing) {
        alreadyHadMeta++;
        continue;
      }
      
      // Resolve via PoolMetaResolver
      const meta = await poolMetaResolver.get(chainId, poolAddr);
      
      if (meta && meta.token0 && meta.token1) {
        resolved++;
      } else {
        failed++;
        console.warn(`[DexBackfill] Failed to resolve pool: ${poolAddr}`);
      }
      
      // Small delay to avoid overwhelming RPC
      await new Promise(r => setTimeout(r, 50));
    }
    
    console.log(`[DexBackfill] Pools resolved: ${resolved}, failed: ${failed}, already had meta: ${alreadyHadMeta}`);
    
    return {
      chainId,
      poolsTotal: poolAddresses.length,
      resolved,
      failed,
      alreadyHadMeta,
    };
  }
  
  /**
   * Phase 2: Backfill swap token0/token1 from pool metadata
   */
  async backfillSwaps(chainId: RpcChainId, batchSize: number = 5000): Promise<BackfillSwapsResult> {
    // Get swaps with missing tokens
    const swaps = await DexSwapModel.find({
      chainId,
      $or: [
        { token0: { $in: [null, ''] } },
        { token1: { $in: [null, ''] } },
      ],
    })
      .select({ _id: 1, pool: 1 })
      .limit(batchSize)
      .lean();
    
    if (swaps.length === 0) {
      const remaining = await DexSwapModel.countDocuments({
        chainId,
        $or: [{ token0: { $in: [null, ''] } }, { token1: { $in: [null, ''] } }],
      });
      return { chainId, swapsChecked: 0, patched: 0, skipped: 0, remaining };
    }
    
    // Get unique pools
    const poolAddrs = [...new Set(swaps.map(s => String(s.pool).toLowerCase()))];
    
    // Load pool metadata from DB
    const pools = await DexPoolModel.find({
      chainId,
      address: { $in: poolAddrs },
      token0: { $nin: [null, ''] },
      token1: { $nin: [null, ''] },
    }).lean();
    
    // Build pool map
    const poolMap = new Map<string, { token0: string; token1: string }>();
    for (const p of pools) {
      if (p.token0 && p.token1) {
        poolMap.set(p.address.toLowerCase(), {
          token0: p.token0.toLowerCase(),
          token1: p.token1.toLowerCase(),
        });
      }
    }
    
    let patched = 0;
    let skipped = 0;
    
    // Build bulk operations
    const bulkOps: any[] = [];
    
    for (const swap of swaps) {
      const poolAddr = String(swap.pool).toLowerCase();
      const poolMeta = poolMap.get(poolAddr);
      
      if (!poolMeta) {
        skipped++;
        continue;
      }
      
      bulkOps.push({
        updateOne: {
          filter: { _id: swap._id },
          update: {
            $set: {
              token0: poolMeta.token0,
              token1: poolMeta.token1,
              updatedAt: Date.now(),
            },
          },
        },
      });
    }
    
    // Execute bulk update
    if (bulkOps.length > 0) {
      const result = await DexSwapModel.bulkWrite(bulkOps, { ordered: false });
      patched = result.modifiedCount || 0;
    }
    
    // Count remaining
    const remaining = await DexSwapModel.countDocuments({
      chainId,
      $or: [{ token0: { $in: [null, ''] } }, { token1: { $in: [null, ''] } }],
    });
    
    console.log(`[DexBackfill] Swaps patched: ${patched}, skipped: ${skipped}, remaining: ${remaining}`);
    
    return {
      chainId,
      swapsChecked: swaps.length,
      patched,
      skipped,
      remaining,
    };
  }
  
  /**
   * Run full backfill pipeline
   */
  async runFullBackfill(chainId: RpcChainId, options?: {
    maxPoolBatches?: number;
    maxSwapBatches?: number;
    poolBatchSize?: number;
    swapBatchSize?: number;
  }): Promise<{
    pools: BackfillPoolsResult[];
    swaps: BackfillSwapsResult[];
    finalStatus: BackfillStatus;
  }> {
    const {
      maxPoolBatches = 10,
      maxSwapBatches = 20,
      poolBatchSize = 500,
      swapBatchSize = 5000,
    } = options || {};
    
    const poolResults: BackfillPoolsResult[] = [];
    const swapResults: BackfillSwapsResult[] = [];
    
    console.log(`[DexBackfill] Starting full backfill for chain ${chainId}...`);
    
    // Phase 1: Resolve pools
    for (let i = 0; i < maxPoolBatches; i++) {
      const result = await this.backfillPools(chainId, poolBatchSize);
      poolResults.push(result);
      
      if (result.poolsTotal === 0 || result.resolved === 0) {
        break; // No more pools to resolve
      }
      
      console.log(`[DexBackfill] Pool batch ${i + 1}: resolved ${result.resolved}`);
    }
    
    // Phase 2: Patch swaps
    for (let i = 0; i < maxSwapBatches; i++) {
      const result = await this.backfillSwaps(chainId, swapBatchSize);
      swapResults.push(result);
      
      if (result.remaining === 0) {
        break; // All done
      }
      
      console.log(`[DexBackfill] Swap batch ${i + 1}: patched ${result.patched}, remaining ${result.remaining}`);
    }
    
    const finalStatus = await this.getStatus(chainId);
    
    console.log(`[DexBackfill] Complete. Remaining swaps without tokens: ${finalStatus.swapsWithoutTokens}`);
    
    return { pools: poolResults, swaps: swapResults, finalStatus };
  }
}

// Singleton
export const dexBackfillService = new DexBackfillService();

console.log('[OnChain V2] DEX Backfill Service loaded');
