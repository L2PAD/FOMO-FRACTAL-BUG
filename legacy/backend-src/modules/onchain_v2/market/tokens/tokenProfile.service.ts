/**
 * Token Profile Service — Phase D2
 * ==================================
 * Fast token snapshot: price, TVL, pool status, evidence, coverage.
 * No series — snapshot only.
 */

import { tokenMetaService } from '../flow/tokenMeta.service';
import { pricingService } from '../pricing';
import { DexPoolModel } from '../../ingestion/dex/models';
import { AltFlowPointModel } from '../altflow/altflow.model';
import { resolveToken } from './tokenResolve.service';

export interface TokenProfileDTO {
  ok: true;
  address: string;
  symbol: string;
  name: string;
  decimals: number;
  verified: boolean;

  priceUsd: number | null;
  priceSource: string;
  priceReliability: number;

  tvlUsd: number;
  poolScore: number;
  poolStatus: string;
  activePools: number;

  trades24h: number;
  pricedShare: number;

  lastUpdated: string | null;
  reason?: string;
}

export async function getTokenProfile(params: {
  chainId: number;
  token: string;
  window?: string;
}): Promise<TokenProfileDTO | { ok: false; reason: string }> {
  const { chainId, token } = params;
  const window = params.window || '7d';

  // 1. Resolve token
  const resolved = await resolveToken(chainId, token);
  if (!resolved) {
    return { ok: false, reason: 'TOKEN_NOT_FOUND' };
  }

  const tokenAddress = resolved.address.toLowerCase();

  // 2. Price
  let priceUsd: number | null = null;
  let priceSource = 'NONE';
  let priceReliability = 0;
  try {
    const priceData = await pricingService.getUsdPrice({ chainId, token: tokenAddress });
    if (priceData) {
      priceUsd = priceData.usd ?? null;
      priceSource = priceData.source ?? 'NONE';
      priceReliability = priceData.reliability ?? 0;
    }
  } catch {}

  // 3. Pools — TVL, score, status
  let tvlUsd = 0;
  let poolScore = 0;
  let poolStatus = 'UNKNOWN';
  let activePools = 0;
  try {
    const pools = await DexPoolModel.find({
      chainId,
      status: { $in: ['ACTIVE', 'DEGRADED'] },
      $or: [
        { token0: tokenAddress },
        { token1: tokenAddress },
      ],
    }).sort({ score: -1 }).limit(20).lean();

    activePools = pools.filter((p: any) => p.status === 'ACTIVE').length;
    tvlUsd = pools.reduce((s, p: any) => s + (Number(p.liquidityUsd) || 0), 0);

    if (pools.length > 0) {
      const best = pools[0] as any;
      poolScore = best.score || 0;
      poolStatus = activePools > 0 ? 'ACTIVE' : 'DEGRADED';
    }
  } catch {}

  // 4. Evidence from AltFlowPoints
  let trades24h = 0;
  let pricedShare = 0;
  let lastUpdated: string | null = null;
  try {
    const latest = await AltFlowPointModel.findOne(
      { chainId: chainId || 1, symbol: resolved.symbol, window: '24h' },
      { _id: 0 }
    ).sort({ t: -1 }).lean() as any;

    if (latest) {
      trades24h = latest.evidence?.trades || 0;
      pricedShare = latest.evidence?.pricedShare || 0;
      lastUpdated = latest.updatedAt ? new Date(latest.updatedAt).toISOString() : null;
    }
  } catch {}

  return {
    ok: true,
    address: resolved.address,
    symbol: resolved.symbol,
    name: resolved.name,
    decimals: resolved.decimals,
    verified: resolved.verified,
    priceUsd,
    priceSource,
    priceReliability,
    tvlUsd,
    poolScore,
    poolStatus,
    activePools,
    trades24h,
    pricedShare,
    lastUpdated,
  };
}
