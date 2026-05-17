/**
 * OnChain V2 — Flow Normalizer Service
 * ======================================
 * 
 * PHASE 3.5.2: Converts raw DEX swaps into normalized token flows
 * STEP 1: Now uses PricingService for USD valuation
 */

import { DexSwapModel, DexPoolModel } from '../../ingestion/dex/models';
import { TokenFlowModel, FlowSide, FlowSource } from './flow.model';
import { tokenMetaService } from './tokenMeta.service';
import { pricingService } from '../pricing';
import type { PriceSource } from '../pricing';
import { LabelsService } from '../../labels/labels.service';
import { EntityResolverService } from '../actors/entityResolver.service';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const WHALE_THRESHOLD_USD = 100_000; // $100K = whale

// Fallback prices (used only if PricingService fails)
const FALLBACK_PRICES: Record<string, number> = {
  'WETH': 3500,
  'ETH': 3500,
  'WBTC': 95000,
};

// Price cache for batch processing (cleared each processDexSwaps call)
let priceCache: Map<string, { priceUsd: number; source: PriceSource; confidence: number }> = new Map();

// ═══════════════════════════════════════════════════════════════
// NORMALIZER SERVICE
// ═══════════════════════════════════════════════════════════════

export class FlowNormalizerService {
  private readonly resolver: EntityResolverService;

  constructor() {
    const labels = new LabelsService();
    this.resolver = new EntityResolverService(labels, { enableV1: true });
  }

  /**
   * Process recent DEX swaps and create normalized flows
   */
  async processDexSwaps(chainId: number, sinceMs: number): Promise<{ processed: number; flows: number; usdCoverage: number }> {
    const since = Date.now() - sinceMs;
    
    // Clear price cache for fresh batch
    priceCache = new Map();
    
    console.log(`[FlowNormalizer] Query: chainId=${chainId}, since=${since}, sinceMs=${sinceMs}`);
    
    // Get swaps from the time window
    // Use indexedAt as fallback when blockTimestamp is not available
    const swaps = await DexSwapModel.find({
      chainId,
      token0: { $nin: [null, ''] },
      token1: { $nin: [null, ''] },
      $or: [
        { blockTimestamp: { $gte: since } },
        { blockTimestamp: { $exists: false }, indexedAt: { $gte: since } },
        { blockTimestamp: null, indexedAt: { $gte: since } },
      ],
    })
      .sort({ blockNumber: -1 })
      .limit(5000)
      .lean();
    
    console.log(`[FlowNormalizer] Found ${swaps.length} swaps`);
    
    if (swaps.length === 0) {
      return { processed: 0, flows: 0 };
    }
    
    console.log(`[FlowNormalizer] Processing ${swaps.length} swaps for chain ${chainId}`);
    
    const flows: Array<{
      chainId: number;
      tokenAddress: string;
      tokenSymbol?: string;
      side: FlowSide;
      usdVolume: number;
      tokenVolume?: number;
      source: FlowSource;
      poolAddress: string;
      blockNumber: number;
      blockTime: number;
      txHash: string;
      logIndex: number;
      isWhale: boolean;
      usdSource?: string;
      usdConfidence?: number;
      counterparty?: string;
    }> = [];
    
    let flowsWithUsd = 0;
    
    for (const swap of swaps) {
      const token0 = swap.token0;
      const token1 = swap.token1;
      
      // Skip if tokens not populated
      if (!token0 || !token1) {
        continue;
      }
      
      // Get token metadata
      const [meta0, meta1] = await Promise.all([
        tokenMetaService.get(chainId, token0),
        tokenMetaService.get(chainId, token1),
      ]);
      
      // Determine alt token
      // Priority: Stables (USDC/USDT/DAI) > WETH/WBTC > Everything else
      // For pairs like USDC/WETH: WETH is the "alt" (tradeable asset)
      // For pairs like WETH/ARB: ARB is the "alt"
      
      let altToken: string;
      let altMeta: typeof meta0;
      let baseMeta: typeof meta0;
      
      // If one is stable and one is not → non-stable is alt
      if (meta0.isStable && !meta1.isStable) {
        altToken = token1;
        altMeta = meta1;
        baseMeta = meta0;
      } else if (meta1.isStable && !meta0.isStable) {
        altToken = token0;
        altMeta = meta0;
        baseMeta = meta1;
      } 
      // Both stable → skip (USDC/USDT pair, not meaningful for alt flow)
      else if (meta0.isStable && meta1.isStable) {
        continue;
      }
      // Neither stable → use isBase to determine
      // If one is WETH/WBTC (base but not stable) and other is true alt
      else if (meta0.isBase && !meta1.isBase) {
        altToken = token1;
        altMeta = meta1;
        baseMeta = meta0;
      } else if (meta1.isBase && !meta0.isBase) {
        altToken = token0;
        altMeta = meta0;
        baseMeta = meta1;
      }
      // Both are base (WETH/WBTC pair) - treat WBTC as alt vs WETH
      else if (meta0.symbol === 'WETH' || meta0.symbol === 'ETH') {
        altToken = token1;
        altMeta = meta1;
        baseMeta = meta0;
      } else if (meta1.symbol === 'WETH' || meta1.symbol === 'ETH') {
        altToken = token0;
        altMeta = meta0;
        baseMeta = meta1;
      }
      // Both non-base → take first as alt
      else {
        altToken = token0;
        altMeta = meta0;
        baseMeta = meta1;
      }
      
      // Parse amounts
      const amount0 = parseFloat(swap.amount0 || '0');
      const amount1 = parseFloat(swap.amount1 || '0');
      
      // Uniswap V3: negative amount = token went out from pool (was bought)
      // amount0 < 0 means token0 was bought, token1 was sold
      
      // Determine side for ALT token based on which token it is
      let side: FlowSide;
      let usdVolume: number;
      
      const altIsToken0 = altToken === token0;
      
      if (altIsToken0) {
        // Alt token is token0
        if (amount0 < 0) {
          // token0 went out = ALT was bought
          side = 'BUY';
        } else {
          // token0 came in = ALT was sold  
          side = 'SELL';
        }
        usdVolume = await this.estimateUsd(chainId, Math.abs(amount0), altMeta, Math.abs(amount1), baseMeta);
      } else {
        // Alt token is token1
        if (amount1 < 0) {
          // token1 went out = ALT was bought
          side = 'BUY';
        } else {
          // token1 came in = ALT was sold
          side = 'SELL';
        }
        usdVolume = await this.estimateUsd(chainId, Math.abs(amount1), altMeta, Math.abs(amount0), baseMeta);
      }
      
      // Skip tiny volumes
      if (usdVolume < 100) continue;
      
      // Get USD source info from cache
      const baseKey = `${chainId}:${baseMeta.address || ''}`;
      const usdInfo = priceCache.get(baseKey);
      
      if (usdVolume > 0) flowsWithUsd++;
      
      flows.push({
        chainId,
        tokenAddress: altToken,
        tokenSymbol: altMeta.symbol,
        side,
        usdVolume,
        source: 'dex',
        poolAddress: swap.pool,
        blockNumber: swap.blockNumber,
        blockTime: swap.blockTimestamp || swap.indexedAt,
        txHash: swap.transactionHash,
        logIndex: swap.logIndex,
        isWhale: usdVolume >= WHALE_THRESHOLD_USD,
        usdSource: usdInfo?.source || (baseMeta.isStable ? 'STABLE' : 'FALLBACK'),
        usdConfidence: usdInfo?.confidence ?? (baseMeta.isStable ? 0.99 : 0.5),
        counterparty: swap.sender,
      });
    }
    
    // P0.7: Batch resolve entity attribution for counterparties
    let entityMap = new Map<string, { entityId: string; entityName: string; entityType: string; source: string }>();
    if (flows.length > 0) {
      try {
        const uniqueSenders = [...new Set(flows.map(f => f.counterparty).filter(Boolean))] as string[];
        if (uniqueSenders.length > 0) {
          const resolved = await this.resolver.batchResolve({ chainId, counterparties: uniqueSenders });
          for (const [addr, entity] of resolved.entries()) {
            if (entity && entity.entityId) {
              entityMap.set(addr, {
                entityId: entity.entityId,
                entityName: entity.entityName,
                entityType: entity.entityType,
                source: entity.source,
              });
            }
          }
          console.log(`[FlowNormalizer] Entity resolution: ${entityMap.size}/${uniqueSenders.length} resolved`);
        }
      } catch (err) {
        console.warn('[FlowNormalizer] Entity batch resolution failed, proceeding without:', err);
      }
    }

    // Bulk insert flows with entity attribution
    if (flows.length > 0) {
      try {
        await TokenFlowModel.bulkWrite(
          flows.map(f => {
            const entity = f.counterparty ? entityMap.get(f.counterparty.toLowerCase()) : undefined;
            const doc: any = { ...f, indexedAt: Date.now() };
            if (entity) {
              doc.counterpartyEntityId = entity.entityId;
              doc.counterpartyEntityName = entity.entityName;
              doc.counterpartyEntityType = entity.entityType;
              doc.counterpartyAttributionSource = entity.source;
            }
            return {
              updateOne: {
                filter: { chainId: f.chainId, txHash: f.txHash, logIndex: f.logIndex },
                update: { $set: doc },
                upsert: true,
              },
            };
          }),
          { ordered: false }
        );
      } catch (e: any) {
        // Ignore duplicate key errors
        if (e.code !== 11000) {
          console.error('[FlowNormalizer] Bulk write error:', e);
        }
      }
    }
    
    return { processed: swaps.length, flows: flows.length, usdCoverage: flows.length > 0 ? flowsWithUsd / flows.length : 0 };
  }
  
  /**
   * Estimate USD value from swap amounts using PricingService
   */
  private async estimateUsd(
    chainId: number,
    altAmount: number, 
    altMeta: { decimals: number; symbol: string; address?: string },
    baseAmount: number,
    baseMeta: { decimals: number; symbol: string; isStable: boolean; address?: string }
  ): Promise<number> {
    // Normalize amounts
    const altNorm = altAmount / Math.pow(10, altMeta.decimals);
    const baseNorm = baseAmount / Math.pow(10, baseMeta.decimals);
    
    // If base is stable, use directly (1:1 USD)
    if (baseMeta.isStable) {
      return baseNorm;
    }
    
    // Try to get price from PricingService
    const baseKey = `${chainId}:${baseMeta.address || baseMeta.symbol}`;
    
    // Check local cache first
    if (priceCache.has(baseKey)) {
      const cached = priceCache.get(baseKey)!;
      return baseNorm * cached.priceUsd;
    }
    
    // Try PricingService for base token
    if (baseMeta.address) {
      try {
        const quote = await pricingService.getUsdPrice({
          chainId,
          token: baseMeta.address,
          allowStale: true,
        });
        
        if (quote && quote.priceUsd > 0) {
          priceCache.set(baseKey, {
            priceUsd: quote.priceUsd,
            source: quote.source,
            confidence: quote.confidence,
          });
          return baseNorm * quote.priceUsd;
        }
      } catch (e) {
        console.warn(`[FlowNormalizer] PricingService error for ${baseMeta.symbol}:`, e);
      }
    }
    
    // Fallback to hardcoded prices
    const fallbackPrice = FALLBACK_PRICES[baseMeta.symbol];
    if (fallbackPrice) {
      priceCache.set(baseKey, {
        priceUsd: fallbackPrice,
        source: 'DEX_VWAP',
        confidence: 0.5,
      });
      return baseNorm * fallbackPrice;
    }
    
    // Can't estimate
    return 0;
  }
  
  /**
   * Get flow stats
   */
  async getStats(chainId: number, windowMs: number = 24 * 60 * 60 * 1000) {
    const since = Date.now() - windowMs;
    
    const stats = await TokenFlowModel.aggregate([
      { $match: { chainId, blockTime: { $gte: since } } },
      {
        $group: {
          _id: null,
          totalFlows: { $sum: 1 },
          totalBuyUsd: { $sum: { $cond: [{ $eq: ['$side', 'BUY'] }, '$usdVolume', 0] } },
          totalSellUsd: { $sum: { $cond: [{ $eq: ['$side', 'SELL'] }, '$usdVolume', 0] } },
          uniqueTokens: { $addToSet: '$tokenAddress' },
          whaleFlows: { $sum: { $cond: ['$isWhale', 1, 0] } },
        },
      },
    ]);
    
    const s = stats[0] || {
      totalFlows: 0,
      totalBuyUsd: 0,
      totalSellUsd: 0,
      uniqueTokens: [],
      whaleFlows: 0,
    };
    
    return {
      chainId,
      windowMs,
      totalFlows: s.totalFlows,
      totalBuyUsd: s.totalBuyUsd,
      totalSellUsd: s.totalSellUsd,
      netUsd: s.totalBuyUsd - s.totalSellUsd,
      uniqueTokens: s.uniqueTokens?.length || 0,
      whaleFlows: s.whaleFlows,
    };
  }
}

// Singleton
export const flowNormalizerService = new FlowNormalizerService();

console.log('[OnChain V2] Flow Normalizer Service loaded');
