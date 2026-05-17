/**
 * Alt Flow Service
 * =================
 * 
 * BLOCK 3.6: Alt Flow Ranking Engine
 * 
 * Computes alt token flow signals from DEX + CEX + whale data.
 * NOT a price predictor - just flow context.
 */

import { AltFlowPointModel } from './altflow.model';
import { DexSwapModel } from '../../ingestion/dex/models';
import { ERC20LogModel, AddressLabelModel } from '../../ingestion/erc20/models';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const WINDOW_MS = {
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
} as const;

// Normalization scales (tune based on typical volumes)
const SCALE_CEX = 5_000_000;   // $5M for normalization
const SCALE_DEX = 2_000_000;   // $2M for normalization
const SCALE_WHALE = 10_000_000; // $10M for normalization
const WHALE_THRESHOLD = 500_000; // $500K = whale transaction

// Score weights
const WEIGHT_CEX = -0.45;  // CEX inflow negative for alts (selling)
const WEIGHT_DEX = 0.45;   // DEX buy pressure positive
const WEIGHT_WHALE = 0.10; // Whale activity neutral/slight positive

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function tanhNorm(x: number, scale: number): number {
  if (!Number.isFinite(x) || scale === 0) return 0;
  return Math.tanh(x / scale);
}

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function computeScore(cexNetUsd: number, dexNetUsd: number, whaleUsd: number): number {
  const cex = tanhNorm(cexNetUsd, SCALE_CEX);
  const dex = tanhNorm(dexNetUsd, SCALE_DEX);
  const wh = tanhNorm(whaleUsd, SCALE_WHALE);

  // CEX inflow = negative (tokens going to exchanges = selling pressure)
  // DEX buy = positive (buying pressure)
  // Whale = slight positive (large interest)
  const raw = (WEIGHT_CEX * cex) + (WEIGHT_DEX * dex) + (WEIGHT_WHALE * wh);
  return Math.max(-1, Math.min(1, raw));
}

function computeConfidence(parts: { 
  hasDex: boolean; 
  hasCex: boolean; 
  whaleUsd: number;
  totalVolume: number;
}): number {
  let c = 0.05; // Base visibility
  if (parts.hasDex) c += 0.35;
  if (parts.hasCex) c += 0.35;
  if (parts.whaleUsd > WHALE_THRESHOLD) c += 0.15;
  if (parts.totalVolume > 1_000_000) c += 0.10;
  return clamp01(c);
}

function buildDrivers(cexNetUsd: number, dexNetUsd: number, whaleUsd: number): string[] {
  const drivers: string[] = [];
  
  if (dexNetUsd > 1_000_000) drivers.push('DEX buy pressure rising');
  else if (dexNetUsd < -1_000_000) drivers.push('DEX sell pressure rising');
  
  if (cexNetUsd > 1_000_000) drivers.push('Net inflows to exchanges');
  else if (cexNetUsd < -1_000_000) drivers.push('Net outflows from exchanges');
  
  if (whaleUsd > 5_000_000) drivers.push('Whale activity detected');
  
  return drivers;
}

function buildFlags(parts: { hasDex: boolean; hasCex: boolean; confidence: number }): string[] {
  const flags: string[] = [];
  if (!parts.hasDex) flags.push('NO_DEX_DATA');
  if (!parts.hasCex) flags.push('NO_CEX_DATA');
  if (parts.confidence < 0.25) flags.push('LOW_CONFIDENCE');
  return flags;
}

// ═══════════════════════════════════════════════════════════════
// MAIN COMPUTATION
// ═══════════════════════════════════════════════════════════════

export interface AltFlowPoint {
  symbol: string;
  score: number;
  confidence: number;
  drivers: string[];
  flags: string[];
  cexNetUsd: number;
  dexNetUsd: number;
  whaleUsd: number;
}

export interface AltFlowResult {
  ok: boolean;
  window: string;
  generatedAt: number;
  topAccumulation: AltFlowPoint[];
  topDistribution: AltFlowPoint[];
  totalTokens: number;
}

/**
 * Compute Alt Flow for a given window
 */
export async function computeAltFlowWindow(window: '24h' | '7d'): Promise<AltFlowResult> {
  const now = Date.now();
  const since = now - WINDOW_MS[window];

  // 1) Get CEX labels
  const cexLabels = await AddressLabelModel.find(
    { type: 'exchange' },
    { address: 1 }
  ).lean();
  const cexSet = new Set(cexLabels.map(l => (l.address || '').toLowerCase()));
  const hasCexLabels = cexSet.size > 0;

  // 2) Aggregate ERC20 transfers
  const transfers = await ERC20LogModel.find(
    { indexedAt: { $gte: since } },
    { from: 1, to: 1, tokenSymbol: 1, value: 1, valueUsd: 1 }
  ).lean();

  // 3) Aggregate DEX swaps
  const swaps = await DexSwapModel.find(
    { indexedAt: { $gte: since } },
    { direction: 1, tokenSymbol: 1, amountUsd: 1 }
  ).lean();

  // Token aggregation map
  const tokenMap: Record<string, {
    cexNetUsd: number;
    dexNetUsd: number;
    whaleUsd: number;
    dexCount: number;
    cexCount: number;
  }> = {};

  const ensure = (symbol: string) => {
    if (!symbol || symbol === 'UNKNOWN') return null;
    if (!tokenMap[symbol]) {
      tokenMap[symbol] = {
        cexNetUsd: 0,
        dexNetUsd: 0,
        whaleUsd: 0,
        dexCount: 0,
        cexCount: 0,
      };
    }
    return tokenMap[symbol];
  };

  // Process transfers for CEX flow
  for (const tr of transfers) {
    const symbol = tr.tokenSymbol || 'UNKNOWN';
    const a = ensure(symbol);
    if (!a) continue;

    const from = (tr.from || '').toLowerCase();
    const to = (tr.to || '').toLowerCase();
    const usd = Number(tr.valueUsd ?? 0);
    const amtUsd = Number.isFinite(usd) && usd > 0 ? usd : 0;

    // CEX inflow (to exchange)
    if (cexSet.has(to)) {
      a.cexNetUsd += amtUsd;
      a.cexCount += 1;
    }
    // CEX outflow (from exchange)
    if (cexSet.has(from)) {
      a.cexNetUsd -= amtUsd;
      a.cexCount += 1;
    }

    // Whale detection
    if (amtUsd >= WHALE_THRESHOLD) {
      a.whaleUsd += amtUsd;
    }
  }

  // Process DEX swaps
  for (const sw of swaps) {
    const symbol = sw.tokenSymbol || 'UNKNOWN';
    const a = ensure(symbol);
    if (!a) continue;

    const usd = Number(sw.amountUsd ?? 0);
    const amtUsd = Number.isFinite(usd) && usd > 0 ? usd : 0;

    // Buy = positive, Sell = negative
    if (sw.direction === 'buy') {
      a.dexNetUsd += amtUsd;
    } else if (sw.direction === 'sell') {
      a.dexNetUsd -= amtUsd;
    }
    a.dexCount += 1;

    // Whale swap
    if (amtUsd >= WHALE_THRESHOLD) {
      a.whaleUsd += amtUsd;
    }
  }

  // Build flow points
  const points: AltFlowPoint[] = Object.entries(tokenMap)
    .filter(([symbol]) => symbol && symbol !== 'UNKNOWN')
    .map(([symbol, a]) => {
      const score = computeScore(a.cexNetUsd, a.dexNetUsd, a.whaleUsd);
      const confidence = computeConfidence({
        hasDex: a.dexCount > 0,
        hasCex: a.cexCount > 0,
        whaleUsd: a.whaleUsd,
        totalVolume: Math.abs(a.cexNetUsd) + Math.abs(a.dexNetUsd),
      });
      const drivers = buildDrivers(a.cexNetUsd, a.dexNetUsd, a.whaleUsd);
      const flags = buildFlags({
        hasDex: a.dexCount > 0,
        hasCex: a.cexCount > 0 || !hasCexLabels,
        confidence,
      });

      return {
        symbol,
        score,
        confidence,
        drivers,
        flags,
        cexNetUsd: a.cexNetUsd,
        dexNetUsd: a.dexNetUsd,
        whaleUsd: a.whaleUsd,
      };
    });

  // Persist to DB (upsert)
  if (points.length > 0) {
    const ops = points.map(p => ({
      updateOne: {
        filter: { chainId: 1, window, t: now, symbol: p.symbol },
        update: { $set: { ...p, chainId: 1, t: now, window } },
        upsert: true,
      },
    }));
    await AltFlowPointModel.bulkWrite(ops, { ordered: false });
  }

  // Sort by score
  const sorted = [...points].sort((a, b) => b.score - a.score);

  return {
    ok: true,
    window,
    generatedAt: now,
    topAccumulation: sorted.slice(0, 10),
    topDistribution: sorted.slice(-10).reverse(),
    totalTokens: sorted.length,
  };
}

/**
 * Get cached alt flow (read from DB)
 */
export async function getAltFlowCached(window: '24h' | '7d', chainId: number = 1): Promise<AltFlowResult | null> {
  const maxAge = 10 * 60 * 1000; // 10 minutes
  const cutoff = Date.now() - maxAge;

  const points = await AltFlowPointModel.find(
    { chainId, window, t: { $gte: cutoff } },
    { _id: 0 }
  )
    .sort({ score: -1 })
    .lean();

  if (points.length === 0) return null;

  const sorted = [...points].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

  return {
    ok: true,
    window,
    generatedAt: sorted[0]?.t ?? Date.now(),
    topAccumulation: sorted.slice(0, 10) as AltFlowPoint[],
    topDistribution: sorted.slice(-10).reverse() as AltFlowPoint[],
    totalTokens: sorted.length,
  };
}

console.log('[AltFlow] Service loaded');
