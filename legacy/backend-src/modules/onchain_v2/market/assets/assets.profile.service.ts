/**
 * OnChain V2 — Assets Profile Service
 * =====================================
 * 
 * PHASE 4: Assets Tab
 * Assembles complete token intelligence profile.
 */

import { DexPoolModel } from '../../ingestion/dex/models';
import { TokenFlowModel } from '../flow/flow.model';
import { tokenMetaService } from '../flow/tokenMeta.service';
import { pricingService } from '../pricing';
import { poolLiquidityService } from '../pricing/pools/liquidity/poolLiquidity.service';
import { computeLiquidityRiskScore } from './liquidityRisk.service';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface AssetsProfileQuery {
  chainId: number;
  token: string; // symbol OR address
  window?: '24h' | '7d' | '30d';
}

export interface TokenProfile {
  ok: boolean;
  token?: {
    chainId: number;
    symbol: string;
    name: string | null;
    address: string;
    decimals: number;
  };
  snapshot?: {
    priceUsd: number | null;
    priceSource: string;
    reliability: number;
  };
  flow?: {
    window: string;
    latest: {
      ts: Date;
      dexNetUsd: number;
      cexNetUsd: number;
      whaleNetUsd: number;
      trades: number;
      pricedShare: number;
    } | null;
    history: Array<{
      ts: Date;
      dexNetUsd: number;
      cexNetUsd: number;
      whaleNetUsd: number;
      trades: number;
    }>;
  };
  pools?: {
    activeCount: number;
    degradedCount: number;
    avgScore: number;
    totalTvlUsd: number;
    concentrationTop1: number;
    concentrationTop3: number;
    topPools: Array<{
      address: string;
      fee: number;
      status: string;
      score: number;
      tvlUsd: number | null;
      token0Symbol: string | null;
      token1Symbol: string | null;
    }>;
  };
  liquidityRisk?: {
    score: number;
    label: string;
    factors: {
      tvlRisk: number;
      poolRisk: number;
      concRisk: number;
    };
  };
  dataQuality?: {
    pricing: {
      usd: number | null;
      source: string;
      reliability: number;
      updatedAt: number | null;
    };
    pools: {
      scanned: number;
      active: number;
      totalTvlUsd: number;
    };
    flows: {
      hasLatest: boolean;
      latestBucketTs: Date | null;
      window: string;
    };
  };
  reason?: string;
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

class AssetsProfileService {
  
  async getTokenProfile(query: AssetsProfileQuery): Promise<TokenProfile> {
    const { chainId, token } = query;
    const window = query.window ?? '7d';
    
    // Resolve token metadata
    const meta = await tokenMetaService.get(chainId, token);
    if (!meta?.address) {
      return { ok: false, reason: 'TOKEN_NOT_FOUND' };
    }
    
    const tokenAddress = meta.address.toLowerCase();
    
    // Get price
    let priceData: any = null;
    try {
      priceData = await pricingService.getUsdPrice({ chainId, token: tokenAddress });
    } catch {}
    
    // Get pools for this token
    const pools = await DexPoolModel.find({
      chainId,
      status: { $in: ['ACTIVE', 'DEGRADED'] },
      $or: [
        { token0: tokenAddress },
        { token1: tokenAddress },
      ],
    })
      .sort({ score: -1 })
      .limit(25)
      .lean();
    
    // Calculate pool stats
    const activePools = pools.filter((p: any) => p.status === 'ACTIVE');
    const degradedPools = pools.filter((p: any) => p.status === 'DEGRADED');
    const totalTvlUsd = sum(activePools.map((p: any) => Number(p.liquidityUsd) || 0));
    
    // Concentration metrics
    const sortedByTvl = [...activePools].sort((a: any, b: any) => 
      (Number(b.liquidityUsd) || 0) - (Number(a.liquidityUsd) || 0)
    );
    const top1Tvl = sortedByTvl[0] ? Number(sortedByTvl[0].liquidityUsd) || 0 : 0;
    const top3Tvl = sum(sortedByTvl.slice(0, 3).map((p: any) => Number(p.liquidityUsd) || 0));
    
    const concentrationTop1 = totalTvlUsd > 0 ? top1Tvl / totalTvlUsd : 1;
    const concentrationTop3 = totalTvlUsd > 0 ? top3Tvl / totalTvlUsd : 1;
    
    // Liquidity risk
    const liquidityRisk = computeLiquidityRiskScore({
      totalTvlUsd,
      activePools: activePools.length,
      concentrationTop1,
      concentrationTop3,
    });
    
    // Get latest flow data
    const latestFlow = await TokenFlowModel.findOne({
      chainId,
      tokenAddress,
      window,
    })
      .sort({ blockTime: -1 })
      .lean() as any;
    
    // Get flow history
    const flowHistory = await TokenFlowModel.find({
      chainId,
      tokenAddress,
      window,
    })
      .sort({ blockTime: -1 })
      .limit(180)
      .lean() as any[];
    
    const history = flowHistory.reverse().map((f: any) => ({
      ts: f.blockTime,
      dexNetUsd: f.dexNetUsd || 0,
      cexNetUsd: f.cexNetUsd || 0,
      whaleNetUsd: f.whaleNetUsd || 0,
      trades: f.tradeCount || 0,
    }));
    
    // Pool summary
    const poolSummary = {
      activeCount: activePools.length,
      degradedCount: degradedPools.length,
      avgScore: avg(pools.map((p: any) => Number(p.score) || 0)),
      totalTvlUsd,
      concentrationTop1,
      concentrationTop3,
      topPools: pools.slice(0, 5).map((p: any) => ({
        address: p.address,
        fee: p.fee,
        status: p.status,
        score: p.score || 0,
        tvlUsd: p.liquidityUsd || null,
        token0Symbol: p.token0Symbol || null,
        token1Symbol: p.token1Symbol || null,
      })),
    };
    
    return {
      ok: true,
      token: {
        chainId,
        symbol: meta.symbol,
        name: meta.name || meta.symbol,
        address: meta.address,
        decimals: meta.decimals || 18,
      },
      snapshot: {
        priceUsd: priceData?.usd ?? null,
        priceSource: priceData?.source ?? 'NONE',
        reliability: priceData?.reliability ?? 0,
      },
      flow: {
        window,
        latest: latestFlow ? {
          ts: latestFlow.blockTime,
          dexNetUsd: latestFlow.dexNetUsd || 0,
          cexNetUsd: latestFlow.cexNetUsd || 0,
          whaleNetUsd: latestFlow.whaleNetUsd || 0,
          trades: latestFlow.tradeCount || 0,
          pricedShare: latestFlow.pricedShare || 0,
        } : null,
        history,
      },
      pools: poolSummary,
      liquidityRisk,
      dataQuality: {
        pricing: {
          usd: priceData?.usd ?? null,
          source: priceData?.source ?? 'NONE',
          reliability: priceData?.reliability ?? 0,
          updatedAt: priceData?.updatedAt ?? null,
        },
        pools: {
          scanned: pools.length,
          active: activePools.length,
          totalTvlUsd,
        },
        flows: {
          hasLatest: !!latestFlow,
          latestBucketTs: latestFlow?.blockTime ?? null,
          window,
        },
      },
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function sum(arr: number[]): number {
  return arr.reduce((s, x) => s + (Number.isFinite(x) ? x : 0), 0);
}

function avg(arr: number[]): number {
  const valid = arr.filter(x => Number.isFinite(x));
  if (valid.length === 0) return 0;
  return valid.reduce((s, x) => s + x, 0) / valid.length;
}

export const assetsProfileService = new AssetsProfileService();

console.log('[OnChain V2] Assets Profile Service loaded');
