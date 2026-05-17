/**
 * Engine Backtest Service — Phase BT
 * ====================================
 * Runs historical backtest of the Engine ranking.
 *
 * Logic:
 *   1. Generate calendar of decision dates (from..to, step=stepDays)
 *   2. For each date:
 *      - Fetch AltFlow rankings as-of that timestamp
 *      - Pick topK BUY (or BUY+NEUTRAL) tokens
 *      - For each horizon, compute future return using price data
 *   3. Aggregate: hitRate, avgReturn, equityFinal, maxDD
 *
 * Data sources:
 *   - AltFlowPointModel: historical rankings (as-of timestamp)
 *   - token_flow_buckets: approximate VWAP pricing
 */

import mongoose from 'mongoose';
import { computeProjectRanking } from '../engine/engine_project_ranking.service.js';
import { BacktestRunModel } from './backtestRun.model.js';
import type {
  BacktestRunRequest,
  BacktestPoint,
  BacktestSummary,
  HorizonResult,
  Horizon,
  BacktestMode,
} from './contracts.js';

// ══════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════

function addDays(iso: string, d: number): string {
  const date = new Date(iso);
  date.setUTCDate(date.getUTCDate() + d);
  return date.toISOString().slice(0, 10);
}

function buildDates(from: string, to: string, step: number): string[] {
  const dates: string[] = [];
  let cur = from;
  while (cur <= to) {
    dates.push(cur);
    cur = addDays(cur, step);
  }
  return dates;
}

function isoToTs(iso: string): number {
  return new Date(iso + 'T00:00:00Z').getTime();
}

// ══════════════════════════════════════════════════════
// RANKING AS-OF TIMESTAMP (BT2 — uses official engine with atTs)
// ══════════════════════════════════════════════════════

interface RankingEntry {
  symbol: string;
  tokenAddress: string | null;
  score: number;
  action: string;
  dexNetUsd: number;
  whaleUsd: number;
}

/**
 * Get engine ranking as-of a given timestamp.
 * Uses the official computeProjectRanking with atTs filter
 * so backtest uses the EXACT same scoring as the live engine.
 */
async function getRankingAsOf(params: {
  chainId: number;
  window: string;
  ts: number;
}): Promise<RankingEntry[]> {
  const { chainId, window: win, ts } = params;

  const result = await computeProjectRanking({
    chainId,
    window: win,
    limit: 100,
    atTs: ts,
  });

  return result.projects.map(p => ({
    symbol: p.symbol,
    tokenAddress: p.tokenAddress,
    score: p.score,
    action: p.action,
    dexNetUsd: p.dexNetUsd,
    whaleUsd: p.smartMoneyNet,
  }));
}

// ══════════════════════════════════════════════════════
// PRICE HISTORY — from token_flow_buckets VWAP proxy
// ══════════════════════════════════════════════════════

/**
 * Get approximate price for multiple tokens at a given date.
 * Uses token_flow_buckets net flow / transfers as VWAP proxy.
 * Returns map: tokenAddress -> priceProxy (or null if unavailable).
 */
async function getPricesAt(params: {
  chainId: number;
  symbols: string[];
  ts: number;
}): Promise<Map<string, number>> {
  const { chainId, ts } = params;
  const prices = new Map<string, number>();

  // Get the closest bucket before the target timestamp
  const cutoffLow = ts - 48 * 3600_000;  // look back 48h max
  const cutoffHigh = ts + 24 * 3600_000; // allow 24h forward

  const buckets = await mongoose.connection.collection('token_flow_buckets').find({
    chainId,
    bucketTs: { $gte: new Date(cutoffLow).toISOString(), $lte: new Date(cutoffHigh).toISOString() },
  }).toArray();

  // Group by tokenSymbol, take closest to target ts
  const bySymbol = new Map<string, any>();
  for (const b of buckets) {
    const sym = String(b.tokenSymbol || '').toUpperCase();
    if (!sym) continue;
    const bTs = new Date(b.bucketTs).getTime();
    const existing = bySymbol.get(sym);
    if (!existing || Math.abs(bTs - ts) < Math.abs(new Date(existing.bucketTs).getTime() - ts)) {
      bySymbol.set(sym, b);
    }
  }

  // Approximate price from flow volume
  for (const [sym, b] of bySymbol.entries()) {
    const volume = (b.inflowUsd || 0) + (b.outflowUsd || 0);
    const transfers = b.transfers || 0;
    if (transfers > 0 && volume > 0) {
      // This is a rough proxy — not actual price, but relative volume per transfer
      prices.set(sym, volume / transfers);
    }
  }

  return prices;
}

// ══════════════════════════════════════════════════════
// PICK TOP-K
// ══════════════════════════════════════════════════════

function pickTop(entries: RankingEntry[], topK: number, mode: BacktestMode): RankingEntry[] {
  let filtered: RankingEntry[];
  if (mode === 'BUY_ONLY') {
    filtered = entries.filter(e => e.action === 'BUY');
  } else {
    filtered = entries.filter(e => e.action === 'BUY' || e.action === 'NEUTRAL');
  }
  filtered.sort((a, b) => b.score - a.score);
  return filtered.slice(0, topK);
}

// ══════════════════════════════════════════════════════
// MAIN SERVICE
// ══════════════════════════════════════════════════════

export async function runBacktest(req: BacktestRunRequest): Promise<BacktestSummary> {
  const start = Date.now();
  const { chainId, from, to, stepDays, window: win, topK, mode, horizons } = req;

  const dates = buildDates(from, to, stepDays);
  const points: BacktestPoint[] = [];
  let totalActionable = 0;
  let totalCoverage = 0;

  // Per-horizon accumulators
  const hAcc: Record<number, { hits: number; returns: number[]; samples: number }> = {};
  for (const h of horizons) {
    hAcc[h] = { hits: 0, returns: [], samples: 0 };
  }

  for (const d of dates) {
    const ts = isoToTs(d);

    // 1. Get ranking as-of this date
    const ranking = await getRankingAsOf({ chainId, window: win, ts });
    const picks = pickTop(ranking, topK, mode);

    if (picks.length === 0) {
      points.push({
        ts: d,
        picks: [],
        scoreAvg: 0,
        coverage: 0,
        actionable: false,
        returnsByH: Object.fromEntries(horizons.map(h => [h, null])),
      });
      continue;
    }

    totalActionable++;
    const scoreAvg = picks.reduce((s, p) => s + p.score, 0) / picks.length;

    // 2. Get prices at decision date
    const px0 = await getPricesAt({ chainId, symbols: picks.map(p => p.symbol), ts });

    // 3. For each horizon, get future prices and compute returns
    const returnsByH: Record<number, number | null> = {};

    for (const h of horizons) {
      const futureDate = addDays(d, h);
      const futureTs = isoToTs(futureDate);

      // Don't compute if future date is beyond data range
      if (futureTs > Date.now()) {
        returnsByH[h] = null;
        continue;
      }

      const px1 = await getPricesAt({ chainId, symbols: picks.map(p => p.symbol), ts: futureTs });

      // Compute average return across picks with both prices
      let sumReturn = 0;
      let counted = 0;
      let hits = 0;

      for (const pick of picks) {
        const p0 = px0.get(pick.symbol);
        const p1 = px1.get(pick.symbol);
        if (p0 && p1 && p0 > 0) {
          const ret = (p1 - p0) / p0;
          sumReturn += ret;
          counted++;
          if (ret > 0) hits++;
        }
      }

      if (counted > 0) {
        const avgRet = sumReturn / counted;
        returnsByH[h] = Math.round(avgRet * 10000) / 10000;
        hAcc[h].returns.push(avgRet);
        hAcc[h].hits += hits;
        hAcc[h].samples += counted;
      } else {
        returnsByH[h] = null;
      }
    }

    const coverage = px0.size / picks.length;
    totalCoverage += coverage;

    points.push({
      ts: d,
      picks: picks.map(p => ({
        symbol: p.symbol,
        tokenAddress: p.tokenAddress,
        score: p.score,
        action: p.action,
      })),
      scoreAvg: Math.round(scoreAvg * 100) / 100,
      coverage: Math.round(coverage * 100) / 100,
      actionable: true,
      returnsByH,
    });
  }

  // 4. Aggregate per-horizon results
  const byH: Record<number, HorizonResult> = {};
  for (const h of horizons) {
    const acc = hAcc[h];
    if (acc.samples === 0) {
      byH[h] = { hitRate: 0, avgReturn: 0, equityFinal: 1, maxDD: 0, samples: 0 };
      continue;
    }

    const hitRate = acc.hits / acc.samples;
    const avgReturn = acc.returns.reduce((s, r) => s + r, 0) / acc.returns.length;

    // Equity curve
    let equity = 1;
    let peak = 1;
    let maxDD = 0;
    for (const r of acc.returns) {
      equity *= (1 + r);
      if (equity > peak) peak = equity;
      const dd = (peak - equity) / peak;
      if (dd > maxDD) maxDD = dd;
    }

    byH[h] = {
      hitRate: Math.round(hitRate * 10000) / 10000,
      avgReturn: Math.round(avgReturn * 10000) / 10000,
      equityFinal: Math.round(equity * 10000) / 10000,
      maxDD: Math.round(maxDD * 10000) / 10000,
      samples: acc.samples,
    };
  }

  // Data quality warning
  let dataWarning: string | null = null;
  if (points.length === 0) {
    dataWarning = 'NO_DATA: No decision points generated. Check date range.';
  } else if (totalActionable === 0) {
    dataWarning = 'NO_ACTIONABLE: No BUY signals in the date range.';
  } else if (totalCoverage / Math.max(totalActionable, 1) < 0.3) {
    dataWarning = 'LOW_COVERAGE: Less than 30% of picks had price data.';
  } else {
    const maxSamples = Math.max(...Object.values(byH).map(h => h.samples));
    if (maxSamples < 10) {
      dataWarning = `SPARSE_DATA: Only ${maxSamples} price-matched samples. Results may not be statistically significant.`;
    }
  }

  const summary: BacktestSummary = {
    chainId,
    from,
    to,
    stepDays,
    window: win,
    topK,
    mode,
    horizons,
    points: points.length,
    actionableRate: points.length > 0 ? Math.round((totalActionable / points.length) * 10000) / 10000 : 0,
    coverage: totalActionable > 0 ? Math.round((totalCoverage / totalActionable) * 10000) / 10000 : 0,
    byH,
    // BT5: structured table
    table: [{
      config: `${mode} top${topK} ${win} step${stepDays}d`,
      h7: byH[7] ?? null,
      h14: byH[14] ?? null,
      h30: byH[30] ?? null,
      h90: byH[90] ?? null,
    }],
    generatedAt: new Date().toISOString(),
    dataWarning,
  };

  // Save to DB
  const elapsed = Date.now() - start;
  await BacktestRunModel.create({
    ...req,
    points: summary.points,
    actionableRate: summary.actionableRate,
    coverage: summary.coverage,
    byH: summary.byH,
    dataWarning: summary.dataWarning,
    elapsed,
  }).catch((err: any) => console.error('[Backtest] Save error:', err));

  return summary;
}

/**
 * Get last N backtest runs for a chain.
 */
export async function getLastBacktestRuns(chainId: number, limit = 10) {
  return BacktestRunModel.find(
    { chainId },
    { _id: 0, __v: 0 },
    { sort: { createdAt: -1 }, limit }
  ).lean();
}

console.log('[Engine] Backtest Service loaded');
