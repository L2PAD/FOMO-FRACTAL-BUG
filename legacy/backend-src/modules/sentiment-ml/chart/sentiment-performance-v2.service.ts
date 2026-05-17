/**
 * Sentiment Performance V2 Service
 * =================================
 * 
 * Performance table with RAW vs ADJUSTED tracking.
 * Shows historical predictions and outcomes — ONE per day.
 * 
 * Uses Kraken API for real prices (Binance blocked in this region).
 * Falls back to MongoDB fractal_canonical_ohlcv.
 */

import {
  Horizon,
  OutcomeType,
} from './sentiment-chart-v2.types.js';
import {
  getAdjustmentContext,
  applyAdjustments,
  biasToDirection,
  calculateExpectedMove,
} from './sentiment-ui-adjustments.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';
import mongoose from 'mongoose';

function horizonToWindow(horizon: Horizon): '24H' | '7D' | '30D' {
  return horizon;
}

function horizonToMs(horizon: Horizon): number {
  if (horizon === '24H') return 24 * 60 * 60 * 1000;
  if (horizon === '7D') return 7 * 24 * 60 * 60 * 1000;
  return 30 * 24 * 60 * 60 * 1000;
}

// ═══════════════════════════════════════════════════════════════
// PRICE CACHE — avoid hammering Kraken on every row
// ═══════════════════════════════════════════════════════════════

interface PriceCache {
  hourlyPrices: Map<number, number>; // hourTimestamp -> close
  currentPrice: number;
  fetchedAt: number;
}

let priceCache: PriceCache | null = null;
const CACHE_TTL = 60_000; // 1 minute

const KRAKEN_PAIR: Record<string, string> = {
  BTC: 'XBTUSD',
  ETH: 'XETHUSD',
  SOL: 'SOLUSD',
};

/** Fetch current price from Kraken */
async function fetchCurrentPrice(symbol: string): Promise<number> {
  const pair = KRAKEN_PAIR[symbol.toUpperCase()] || `${symbol.toUpperCase()}USD`;
  try {
    const res = await fetch(`https://api.kraken.com/0/public/Ticker?pair=${pair}`);
    if (res.ok) {
      const data = await res.json();
      const result = data?.result || {};
      const key = Object.keys(result)[0];
      if (key && result[key]?.c?.[0]) {
        return parseFloat(result[key].c[0]);
      }
    }
  } catch (err) {
    console.warn('[SentimentPerf] Kraken ticker error:', err);
  }
  // MongoDB fallback
  return await fetchMongoPriceFallback(symbol);
}

/** Fetch hourly OHLC from Kraken for the last N days */
async function fetchHourlyPrices(symbol: string, days: number): Promise<Map<number, number>> {
  const map = new Map<number, number>();
  const pair = KRAKEN_PAIR[symbol.toUpperCase()] || `${symbol.toUpperCase()}USD`;
  const since = Math.floor((Date.now() - days * 86400000) / 1000);

  try {
    const res = await fetch(
      `https://api.kraken.com/0/public/OHLC?pair=${pair}&interval=60&since=${since}`
    );
    if (res.ok) {
      const data = await res.json();
      const result = data?.result || {};
      const key = Object.keys(result).find(k => k !== 'last');
      if (key && Array.isArray(result[key])) {
        for (const candle of result[key]) {
          // candle: [timestamp, open, high, low, close, vwap, volume, count]
          const ts = Number(candle[0]) * 1000; // to ms
          const close = parseFloat(candle[4]);
          // Round to hour
          const hourTs = Math.floor(ts / 3600000) * 3600000;
          map.set(hourTs, close);
        }
      }
    }
  } catch (err) {
    console.warn('[SentimentPerf] Kraken OHLC error:', err);
  }
  return map;
}

/** MongoDB fallback price */
async function fetchMongoPriceFallback(symbol: string): Promise<number> {
  try {
    const db = mongoose.connection.db;
    if (!db) return 0;
    const doc = await db.collection('fractal_canonical_ohlcv').findOne(
      { 'meta.symbol': symbol.toUpperCase() },
      { sort: { ts: -1 }, projection: { 'ohlcv.c': 1, _id: 0 } }
    );
    if (doc?.ohlcv?.c) return doc.ohlcv.c;
  } catch {}
  return 0;
}

/** Get price closest to a target timestamp from the hourly cache */
function getPriceAtTime(hourlyPrices: Map<number, number>, targetMs: number, currentPrice: number): number {
  const hourTs = Math.floor(targetMs / 3600000) * 3600000;
  
  // Exact hour match
  if (hourlyPrices.has(hourTs)) return hourlyPrices.get(hourTs)!;
  
  // Try ±1 hour
  if (hourlyPrices.has(hourTs - 3600000)) return hourlyPrices.get(hourTs - 3600000)!;
  if (hourlyPrices.has(hourTs + 3600000)) return hourlyPrices.get(hourTs + 3600000)!;
  
  // Nearest available
  let bestTs = 0;
  let bestDiff = Infinity;
  for (const [ts] of hourlyPrices) {
    const diff = Math.abs(ts - targetMs);
    if (diff < bestDiff) {
      bestDiff = diff;
      bestTs = ts;
    }
  }
  if (bestTs && bestDiff < 12 * 3600000) return hourlyPrices.get(bestTs)!;
  
  return currentPrice; // last resort
}

/** Ensure price cache is fresh */
async function ensurePriceCache(symbol: string, lookbackDays: number): Promise<PriceCache> {
  if (priceCache && (Date.now() - priceCache.fetchedAt) < CACHE_TTL) {
    return priceCache;
  }
  
  const [currentPrice, hourlyPrices] = await Promise.all([
    fetchCurrentPrice(symbol),
    fetchHourlyPrices(symbol, lookbackDays),
  ]);
  
  priceCache = { hourlyPrices, currentPrice, fetchedAt: Date.now() };
  return priceCache;
}

// ═══════════════════════════════════════════════════════════════
// MAIN SERVICE
// ═══════════════════════════════════════════════════════════════

interface PerformanceRow {
  asOf: string;
  createdAt: string;
  evaluateAt: string;
  horizon: Horizon;
  entry: number;
  actual: number | null;
  rawTarget: number;
  finalTarget: number;
  rawConfidence: number;
  finalConfidence: number;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  outcome: OutcomeType;
  notes: string[];
}

interface PerformanceSummary {
  total: number;
  wins: number;
  losses: number;
  pending: number;
  evaluated: number;
  overdue: number;
  winRate: number;
  avgReturn: number;
}

interface PerformanceResponse {
  ok: true;
  symbol: string;
  horizon: Horizon;
  rows: PerformanceRow[];
  summary: PerformanceSummary;
}

export class SentimentPerformanceV2Service {
  /**
   * Get performance history for symbol/horizon.
   * Returns ONE forecast per day, sorted newest→oldest.
   */
  async getPerformance(
    symbol: string,
    horizon: Horizon,
    limit: number = 30
  ): Promise<PerformanceResponse> {
    const window = horizonToWindow(horizon);
    const context = await getAdjustmentContext();
    const hMs = horizonToMs(horizon);
    const now = Date.now();

    // 1. Aggregate: pick the LAST aggregate per calendar day
    const dailyAggs = await SentimentAggregateModel.aggregate([
      { $match: { symbol: symbol.toUpperCase(), window } },
      { $sort: { asOf: -1 } },
      {
        $group: {
          _id: { $dateToString: { format: '%Y-%m-%d', date: '$asOf' } },
          doc: { $first: '$$ROOT' },
        },
      },
      { $sort: { _id: -1 } },
      { $limit: limit },
    ]);

    // 2. Load price cache (covers lookback period)
    const lookbackDays = Math.max(40, limit + 10);
    const cache = await ensurePriceCache(symbol, lookbackDays);

    const rows: PerformanceRow[] = [];
    let wins = 0;
    let losses = 0;
    let pending = 0;
    let overdue = 0;
    let totalReturn = 0;

    for (const { doc: agg } of dailyAggs) {
      const asOf = agg.asOf ? new Date(agg.asOf).toISOString() : new Date().toISOString();
      const createdAt = asOf;
      const aggTime = new Date(asOf).getTime();
      const evaluateAtMs = aggTime + hMs;
      const evaluateAt = new Date(evaluateAtMs).toISOString();

      // Raw values from aggregate
      const rawConfidence = agg.confidence ?? agg.weightedConfidence ?? 0.5;
      const bias = agg.bias ?? 0;
      const rawExpectedMovePct = calculateExpectedMove(bias, rawConfidence);

      // Real entry price at asOf time
      const entry = getPriceAtTime(cache.hourlyPrices, aggTime, cache.currentPrice);

      // Apply adjustments
      const adjusted = applyAdjustments(rawConfidence, rawExpectedMovePct, entry, context);

      const rawTarget = entry * (1 + rawExpectedMovePct);
      const finalTarget = adjusted.finalTarget;
      const direction = context.safeMode ? 'NEUTRAL' : biasToDirection(bias);

      // Determine outcome using REAL prices
      let outcome: OutcomeType = 'PENDING';
      let actual: number | null = null;

      if (now > evaluateAtMs) {
        // Forecast expired — get real price at evaluation time
        actual = getPriceAtTime(cache.hourlyPrices, evaluateAtMs, 0);
        
        // If evaluation time is recent (< 2 days ago), use current price as approximation
        if (!actual || actual === 0) {
          if (now - evaluateAtMs < 2 * 86400000) {
            actual = cache.currentPrice;
          }
        }

        if (actual && actual > 0 && entry > 0) {
          const actualMove = (actual - entry) / entry;
          const predictedMove = rawExpectedMovePct;

          if (Math.abs(predictedMove) < 0.005) {
            outcome = 'WEAK';
          } else if (
            (predictedMove > 0 && actualMove > 0) ||
            (predictedMove < 0 && actualMove < 0)
          ) {
            const accuracy = Math.min(1, Math.abs(actualMove) / Math.abs(predictedMove));
            outcome = accuracy > 0.5 ? 'TP' : 'WEAK';
            if (outcome === 'TP') wins++;
          } else {
            outcome = 'FP';
            losses++;
          }

          if (outcome === 'TP') {
            totalReturn += Math.abs(actualMove);
          } else if (outcome === 'FP') {
            totalReturn -= Math.abs(actualMove);
          }
        } else {
          outcome = 'OVERDUE';
          overdue++;
        }
      } else {
        pending++;
      }

      rows.push({
        asOf,
        createdAt,
        evaluateAt,
        horizon,
        entry,
        actual,
        rawTarget,
        finalTarget,
        rawConfidence,
        finalConfidence: adjusted.finalConfidence,
        direction,
        outcome,
        notes: adjusted.notes,
      });
    }

    const total = rows.length;
    const evaluated = wins + losses;
    const winRate = evaluated > 0 ? wins / evaluated : 0;
    const avgReturn = evaluated > 0 ? totalReturn / evaluated : 0;

    return {
      ok: true,
      symbol,
      horizon,
      rows,
      summary: {
        total,
        wins,
        losses,
        pending,
        evaluated,
        overdue,
        winRate,
        avgReturn,
      },
    };
  }
}

// Singleton
let instance: SentimentPerformanceV2Service | null = null;

export function getSentimentPerformanceV2Service(): SentimentPerformanceV2Service {
  if (!instance) {
    instance = new SentimentPerformanceV2Service();
  }
  return instance;
}
