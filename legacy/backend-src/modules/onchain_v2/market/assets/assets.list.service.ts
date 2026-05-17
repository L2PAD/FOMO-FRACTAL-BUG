/**
 * OnChain V2 — Assets List Service
 * ==================================
 * 
 * PHASE 4: Assets Tab - Token List
 * Lists tokens by different criteria: signals, TVL, spikes.
 */

import { DexPoolModel } from '../../ingestion/dex/models';
import { TokenFlowModel } from '../flow/flow.model';
import { tokenMetaService } from '../flow/tokenMeta.service';
import { pricingService } from '../pricing';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

type WindowKey = '24h' | '7d' | '30d';
type ListKind = 'signals' | 'tvl' | 'spikes';

export interface AssetsListQuery {
  chainId: number;
  kind: ListKind;
  window: WindowKey;
  limit?: number;
}

export interface AssetListItem {
  chainId: number;
  address: string;
  symbol: string;
  name: string | null;
  priceUsd: number | null;
  priceSource: string;
  reliability: number;
  tvlUsd?: number;
  dexNetUsd?: number;
  cexNetUsd?: number;
  whaleNetUsd?: number;
  trades?: number;
  spikeAbs?: number;
  scoreHint?: number;
  updatedAt?: Date | null;
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

class AssetsListService {
  
  async list(query: AssetsListQuery): Promise<{
    ok: boolean;
    kind: ListKind;
    window?: WindowKey;
    items: AssetListItem[];
    reason?: string;
  }> {
    const { chainId, kind, window } = query;
    const limit = Math.min(Math.max(query.limit ?? 20, 5), 50);
    
    switch (kind) {
      case 'signals':
        return this.listFromSignals(chainId, window, limit);
      case 'tvl':
        return this.listFromTvl(chainId, limit);
      case 'spikes':
        return this.listFromSpikes(chainId, window, limit);
      default:
        return { ok: false, kind, items: [], reason: 'INVALID_KIND' };
    }
  }
  
  /**
   * List tokens from AltFlow signals (highest net flow impact)
   */
  private async listFromSignals(
    chainId: number, 
    window: WindowKey, 
    limit: number
  ): Promise<{ ok: boolean; kind: ListKind; window: WindowKey; items: AssetListItem[] }> {
    // Get tokens from token_flows aggregated
    const flows = await TokenFlowModel.aggregate([
      { $match: { chainId } },
      { $sort: { blockTime: -1 } },
      {
        $group: {
          _id: '$tokenAddress',
          tokenSymbol: { $first: '$tokenSymbol' },
          dexNetUsd: { $sum: '$dexNetUsd' },
          cexNetUsd: { $sum: '$cexNetUsd' },
          whaleNetUsd: { $sum: '$whaleNetUsd' },
          usdVolume: { $sum: '$usdVolume' },
          tradeCount: { $sum: '$tradeCount' },
          lastUpdate: { $max: '$blockTime' },
        },
      },
      {
        $addFields: {
          impactAbs: {
            $add: [
              { $abs: { $ifNull: ['$dexNetUsd', 0] } },
              { $abs: { $ifNull: ['$cexNetUsd', 0] } },
              { $abs: { $ifNull: ['$whaleNetUsd', 0] } },
            ],
          },
        },
      },
      { $sort: { impactAbs: -1 } },
      { $limit: limit },
    ]);
    
    const items = await Promise.all(
      flows.map((f: any) => this.enrichToken(chainId, f._id, f.tokenSymbol, {
        dexNetUsd: f.dexNetUsd || 0,
        cexNetUsd: f.cexNetUsd || 0,
        whaleNetUsd: f.whaleNetUsd || 0,
        trades: f.tradeCount || 0,
        scoreHint: f.impactAbs || 0,
        updatedAt: f.lastUpdate,
      }))
    );
    
    return { ok: true, kind: 'signals', window, items };
  }
  
  /**
   * List tokens by total TVL across ACTIVE pools
   */
  private async listFromTvl(
    chainId: number, 
    limit: number
  ): Promise<{ ok: boolean; kind: ListKind; items: AssetListItem[] }> {
    // Aggregate TVL by token from pools
    const rows = await DexPoolModel.aggregate([
      { $match: { chainId, status: 'ACTIVE', liquidityUsd: { $gt: 0 } } },
      {
        $facet: {
          t0: [
            { $group: { _id: '$token0', symbol: { $first: '$token0Symbol' }, tvlUsd: { $sum: '$liquidityUsd' } } },
          ],
          t1: [
            { $group: { _id: '$token1', symbol: { $first: '$token1Symbol' }, tvlUsd: { $sum: '$liquidityUsd' } } },
          ],
        },
      },
      { $project: { merged: { $concatArrays: ['$t0', '$t1'] } } },
      { $unwind: '$merged' },
      {
        $group: {
          _id: '$merged._id',
          symbol: { $first: '$merged.symbol' },
          tvlUsd: { $sum: '$merged.tvlUsd' },
        },
      },
      { $sort: { tvlUsd: -1 } },
      { $limit: limit },
    ]);
    
    const items = await Promise.all(
      rows.map((r: any) => this.enrichToken(chainId, r._id, r.symbol, {
        tvlUsd: r.tvlUsd || 0,
      }))
    );
    
    return { ok: true, kind: 'tvl', items };
  }
  
  /**
   * List tokens with recent flow spikes (largest change between periods)
   */
  private async listFromSpikes(
    chainId: number, 
    window: WindowKey, 
    limit: number
  ): Promise<{ ok: boolean; kind: ListKind; window: WindowKey; items: AssetListItem[]; reason?: string }> {
    // Get recent flows and calculate delta
    const flows = await TokenFlowModel.aggregate([
      { $match: { chainId } },
      { $sort: { blockTime: -1 } },
      {
        $group: {
          _id: '$tokenAddress',
          tokenSymbol: { $first: '$tokenSymbol' },
          recentFlow: { $first: '$$ROOT' },
          totalDexNet: { $sum: '$dexNetUsd' },
          totalCexNet: { $sum: '$cexNetUsd' },
          totalWhaleNet: { $sum: '$whaleNetUsd' },
          tradeCount: { $sum: '$tradeCount' },
        },
      },
      {
        $addFields: {
          spikeAbs: {
            $add: [
              { $abs: { $ifNull: ['$recentFlow.dexNetUsd', 0] } },
              { $abs: { $ifNull: ['$recentFlow.cexNetUsd', 0] } },
              { $abs: { $ifNull: ['$recentFlow.whaleNetUsd', 0] } },
            ],
          },
        },
      },
      { $sort: { spikeAbs: -1 } },
      { $limit: limit },
    ]);
    
    const items = await Promise.all(
      flows.map((f: any) => this.enrichToken(chainId, f._id, f.tokenSymbol, {
        spikeAbs: f.spikeAbs || 0,
        dexNetUsd: f.recentFlow?.dexNetUsd || 0,
        cexNetUsd: f.recentFlow?.cexNetUsd || 0,
        whaleNetUsd: f.recentFlow?.whaleNetUsd || 0,
        trades: f.tradeCount || 0,
        updatedAt: f.recentFlow?.blockTime,
      }))
    );
    
    return { ok: true, kind: 'spikes', window, items };
  }
  
  /**
   * Enrich token with metadata and price
   */
  private async enrichToken(
    chainId: number,
    tokenAddress: string,
    tokenSymbol: string | null,
    extra: Partial<AssetListItem>
  ): Promise<AssetListItem> {
    const addr = String(tokenAddress).toLowerCase();
    
    // Get metadata
    let meta: any = null;
    try {
      meta = await tokenMetaService.resolve(chainId, addr);
    } catch {}
    
    // Get price
    let price: any = null;
    try {
      price = await pricingService.getUsdPrice({ chainId, token: addr });
    } catch {}
    
    return {
      chainId,
      address: addr,
      symbol: meta?.symbol || tokenSymbol || 'UNKNOWN',
      name: meta?.name || null,
      priceUsd: price?.usd ?? null,
      priceSource: price?.source ?? extra?.priceSource ?? 'NONE',
      reliability: price?.reliability ?? 0,
      ...extra,
    };
  }
}

export const assetsListService = new AssetsListService();

console.log('[OnChain V2] Assets List Service loaded');
