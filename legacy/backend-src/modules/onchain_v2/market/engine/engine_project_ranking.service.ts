/**
 * Engine Project Ranking Service — Phase B1
 * ==========================================
 * 
 * Produces ranked list of tokens based on 4 deterministic signals:
 *   1. DEX Net (from AltFlowPointModel)
 *   2. CEX Net (from CexFlowBucketModel) — inverted: outflow = bullish
 *   3. Smart Money (from AltFlowPointModel.whaleUsd)
 *   4. Liquidity (from AltFlowPointModel.quality.poolScore)
 *
 * Score formula (deterministic, transparent):
 *   score = 0.35 * norm(dexNet) + 0.25 * norm(smartMoney)
 *         + 0.20 * liquidityNorm + 0.20 * norm(-cexNet)
 *
 * Action:
 *   score >= 0.6  → BUY
 *   score <= -0.6 → SELL
 *   else          → NEUTRAL
 */

import mongoose from 'mongoose';
import { CexFlowBucketModel } from '../cex/buckets/cexFlowBucket.model.js';
import { AltFlowPointModel } from '../altflow/altflow.model.js';

// ══════════════════════════════════════════════════════
// TYPES
// ══════════════════════════════════════════════════════

export type ProjectAction = 'BUY' | 'SELL' | 'NEUTRAL';

export interface ProjectRankingPoint {
  symbol: string;
  tokenAddress: string | null;
  chainId: number;

  // Raw signals
  dexNetUsd: number;
  cexNetUsd: number;       // negative = outflow = bullish
  smartMoneyNet: number;   // whale flows
  liquidityScore: number;  // 0..1 normalized poolScore

  // Normalized components [-1..1]
  components: {
    dex: number;
    cex: number;
    smartMoney: number;
    liquidity: number;
  };

  // Final
  score: number;           // [-1..1]
  action: ProjectAction;
  confidence: number;

  // Evidence
  evidence: {
    dexTrades: number;
    cexTransfers: number;
    pricedShare: number;
    poolScore: number | null;
    poolStatus: string | null;
  };
}

// ══════════════════════════════════════════════════════
// WEIGHTS & THRESHOLDS
// ══════════════════════════════════════════════════════

const W_DEX = 0.35;
const W_SMART = 0.25;
const W_LIQ = 0.20;
const W_CEX = 0.20;

const BUY_THRESHOLD = 0.6;
const SELL_THRESHOLD = -0.6;

// ══════════════════════════════════════════════════════
// NORMALIZATION — Rank-based percentile [-1..1]
// ══════════════════════════════════════════════════════

function normalizeArray(values: number[]): number[] {
  if (values.length === 0) return [];
  if (values.length === 1) return [0];

  // Sort indices by value
  const indexed = values.map((v, i) => ({ v, i }));
  indexed.sort((a, b) => a.v - b.v);

  const result = new Array(values.length);
  for (let rank = 0; rank < indexed.length; rank++) {
    // Map rank [0..N-1] to [-1..1]
    const norm = (2 * rank / (indexed.length - 1)) - 1;
    result[indexed[rank].i] = norm;
  }
  return result;
}

// ══════════════════════════════════════════════════════
// SERVICE
// ══════════════════════════════════════════════════════

export async function computeProjectRanking(args: {
  chainId: number;
  window: string;
  limit?: number;
  filterAction?: ProjectAction;
  atTs?: number;  // BT2: as-of timestamp for backtest (latest bucket <= atTs)
}): Promise<{
  ok: true;
  chainId: number;
  window: string;
  totalTokens: number;
  projects: ProjectRankingPoint[];
  generatedAt: string;
}> {
  const { chainId, window: win, limit = 100, filterAction, atTs } = args;
  const tag = `[EngineRanking:${win}]`;

  // 1. Get AltFlow points — with optional as-of timestamp filter
  const altflowFilter: any = { chainId: chainId || 1, window: win };
  if (atTs) {
    altflowFilter.t = { $lte: atTs };
  }

  const altflowPoints = await AltFlowPointModel.find(
    altflowFilter,
    {},
    { sort: { t: -1 } }
  ).lean();

  // Deduplicate by symbol (take latest 't')
  const altflowMap = new Map<string, any>();
  for (const p of altflowPoints) {
    const sym = String((p as any).symbol || '').toUpperCase();
    if (!sym) continue;
    if (!altflowMap.has(sym) || (p as any).t > altflowMap.get(sym).t) {
      altflowMap.set(sym, p);
    }
  }

  console.log(`${tag} AltFlow: ${altflowMap.size} unique tokens`);

  // 2. Build symbol→address mapping from token_registry
  const registry = mongoose.connection.collection('token_registry');
  const regDocs = await registry.find({ chain: 'ethereum' }).toArray();
  const symToAddr = new Map<string, string>();
  for (const d of regDocs) {
    const sym = String(d.symbol || '').toUpperCase();
    const addr = String(d.address || '').toLowerCase();
    if (sym && addr) symToAddr.set(sym, addr);
  }

  // 3. Get latest CEX bucket aggregates (per token)
  const latestBucket = await CexFlowBucketModel.findOne(
    { chainId, window: win },
    { bucketStart: 1 },
    { sort: { bucketStart: -1 } }
  ).lean();

  const cexByToken = new Map<string, { netUsd: number; transfers: number }>();

  if (latestBucket) {
    const buckets = await CexFlowBucketModel.aggregate([
      { $match: { chainId, window: win, bucketStart: (latestBucket as any).bucketStart } },
      {
        $group: {
          _id: '$tokenAddress',
          inflowUsd: { $sum: '$inflowUsd' },
          outflowUsd: { $sum: '$outflowUsd' },
          netUsd: { $sum: '$netUsd' },
          transferCount: { $sum: '$transferCount' },
        },
      },
    ]);

    for (const b of buckets) {
      cexByToken.set(String(b._id).toLowerCase(), {
        netUsd: b.netUsd ?? 0,
        transfers: b.transferCount ?? 0,
      });
    }
  }

  console.log(`${tag} CEX buckets: ${cexByToken.size} tokens`);

  // 4. Build raw project list
  interface RawProject {
    symbol: string;
    tokenAddress: string | null;
    dexNetUsd: number;
    cexNetUsd: number;
    smartMoneyNet: number;
    liquidityScore: number;
    confidence: number;
    dexTrades: number;
    cexTransfers: number;
    pricedShare: number;
    poolScore: number | null;
    poolStatus: string | null;
  }

  const projects: RawProject[] = [];

  for (const [symbol, af] of altflowMap.entries()) {
    const dexNetUsd = af.dexNetUsd ?? 0;
    const smartMoneyNet = af.whaleUsd ?? 0;
    const poolScore = af.quality?.poolScore ?? 50;
    const liquidityScore = Math.max(0, Math.min(1, poolScore / 100));
    const confidence = af.confidence ?? 0;
    const dexTrades = af.evidence?.trades ?? 0;
    const pricedShare = af.evidence?.pricedShare ?? 0;
    const poolStatus = af.quality?.poolStatus ?? 'UNKNOWN';

    // Try to get token address
    const tokenAddress = symToAddr.get(symbol) || null;

    // Get CEX data by address
    let cexNetUsd = 0;
    let cexTransfers = 0;
    if (tokenAddress) {
      const cex = cexByToken.get(tokenAddress);
      if (cex) {
        cexNetUsd = cex.netUsd;
        cexTransfers = cex.transfers;
      }
    }

    projects.push({
      symbol, tokenAddress,
      dexNetUsd, cexNetUsd, smartMoneyNet, liquidityScore,
      confidence, dexTrades, cexTransfers, pricedShare,
      poolScore, poolStatus,
    });
  }

  if (projects.length === 0) {
    return {
      ok: true, chainId, window: win,
      totalTokens: 0, projects: [],
      generatedAt: new Date().toISOString(),
    };
  }

  // 5. Normalize signals using rank-based normalization
  const dexNorm = normalizeArray(projects.map(p => p.dexNetUsd));
  const smNorm = normalizeArray(projects.map(p => p.smartMoneyNet));
  // For CEX: NEGATIVE net = outflow = bullish, so invert
  const cexNorm = normalizeArray(projects.map(p => -p.cexNetUsd));

  // 6. Compute final scores
  const result: ProjectRankingPoint[] = projects.map((p, i) => {
    const dex = dexNorm[i];
    const sm = smNorm[i];
    const cex = cexNorm[i];
    const liq = (p.liquidityScore - 0.5) * 2; // map 0..1 → -1..1

    const score = W_DEX * dex + W_SMART * sm + W_LIQ * liq + W_CEX * cex;

    // Clamp to [-1, 1]
    const clampedScore = Math.max(-1, Math.min(1, score));

    let action: ProjectAction = 'NEUTRAL';
    if (clampedScore >= BUY_THRESHOLD) action = 'BUY';
    else if (clampedScore <= SELL_THRESHOLD) action = 'SELL';

    return {
      symbol: p.symbol,
      tokenAddress: p.tokenAddress,
      chainId,
      dexNetUsd: p.dexNetUsd,
      cexNetUsd: p.cexNetUsd,
      smartMoneyNet: p.smartMoneyNet,
      liquidityScore: p.liquidityScore,
      components: { dex, cex, smartMoney: sm, liquidity: liq },
      score: Math.round(clampedScore * 100) / 100,
      action,
      confidence: p.confidence,
      evidence: {
        dexTrades: p.dexTrades,
        cexTransfers: p.cexTransfers,
        pricedShare: p.pricedShare,
        poolScore: p.poolScore,
        poolStatus: p.poolStatus,
      },
    };
  });

  // 7. Sort by absolute score (strongest signals first)
  result.sort((a, b) => Math.abs(b.score) - Math.abs(a.score));

  // 8. Apply filter
  let filtered = filterAction
    ? result.filter(r => r.action === filterAction)
    : result;

  // 9. Limit
  filtered = filtered.slice(0, limit);

  console.log(`${tag} Produced ${result.length} rankings (${result.filter(r => r.action === 'BUY').length} BUY, ${result.filter(r => r.action === 'SELL').length} SELL)`);

  return {
    ok: true, chainId, window: win,
    totalTokens: result.length,
    projects: filtered,
    generatedAt: new Date().toISOString(),
  };
}

console.log('[Engine] Project Ranking Service loaded');
