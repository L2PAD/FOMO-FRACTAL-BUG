/**
 * Exchange Chart V3 Service — FINAL
 * ===================================
 * 1 DB forecast = 1 autonomous candle.
 * open = entryPrice of that forecast.
 * close = targetPrice of that forecast.
 * 
 * NO chaining (no open=prevClose).
 * NO dailyMove distribution.
 * NO interpolation. NO simulation.
 *
 * For 30D: includes overlay7DPoints (7D forecasts visible inside 30D).
 */

import type {
  ExchangeChartV3Query,
  ExchangeChartV3Response,
  ForecastPoint,
  RealCandle,
} from './exchange-chart-v3.types.js';

const DAY_SEC = 86400;
const DAY_MS = DAY_SEC * 1000;

const FORECAST_WINDOW: Record<string, number> = {
  '1D': 2 * DAY_MS,
  '7D': 8 * DAY_MS,
  '30D': 35 * DAY_MS,
};

interface DbForecast {
  createdAt?: number;
  madeAtTs?: number;
  evaluateAfter?: number;
  horizonDays?: number;
  targetPrice: number;
  entryPrice?: number;
  basePrice?: number;
  expectedMovePct?: number;
  direction?: string;
  confidence?: number;
  regime?: string;
  regimeAtCreation?: string;
}

function normalizeDirection(dir?: string): 'LONG' | 'SHORT' | 'NEUTRAL' {
  if (!dir) return 'NEUTRAL';
  const d = dir.toUpperCase();
  if (d === 'UP' || d === 'LONG') return 'LONG';
  if (d === 'DOWN' || d === 'SHORT') return 'SHORT';
  return 'NEUTRAL';
}

function floorToDay(ts: number): number {
  return Math.floor(ts / DAY_SEC) * DAY_SEC;
}

function buildForecastPoints(
  forecasts: DbForecast[],
  horizonDays: number,
  nowMs: number,
  limit: number
): ForecastPoint[] {
  const todayBucket = floorToDay(Math.floor(nowMs / 1000));

  // Convert to points
  const raw: ForecastPoint[] = [];
  for (const f of forecasts) {
    const createdMs = f.createdAt || (f.madeAtTs ? f.madeAtTs * 1000 : 0);
    if (createdMs <= 0) continue;

    const entry = f.entryPrice || f.basePrice || 0;
    if (entry <= 0) continue;

    // Use evaluateAfter from DB if available, otherwise calculate
    let targetDateSec: number;
    if (f.evaluateAfter && f.evaluateAfter > 0) {
      targetDateSec = floorToDay(Math.floor(f.evaluateAfter / 1000));
    } else {
      targetDateSec = floorToDay(Math.floor((createdMs + horizonDays * DAY_MS) / 1000));
    }
    if (targetDateSec <= todayBucket) continue; // only future

    raw.push({
      madeAtTs: Math.floor(createdMs / 1000),
      targetDateTs: targetDateSec,
      entryPrice: entry,
      targetPrice: f.targetPrice,
      expectedMovePct: f.expectedMovePct ?? ((f.targetPrice / entry - 1) * 100),
      confidence: f.confidence ?? 0,
      direction: normalizeDirection(f.direction),
    });
  }

  // Deduplicate by targetDateTs: keep latest madeAtTs
  const map = new Map<number, ForecastPoint>();
  for (const p of raw) {
    const existing = map.get(p.targetDateTs);
    if (!existing || p.madeAtTs > existing.madeAtTs) {
      map.set(p.targetDateTs, p);
    }
  }

  // Sort by targetDateTs, limit to horizonDays
  return Array.from(map.values())
    .sort((a, b) => a.targetDateTs - b.targetDateTs)
    .slice(0, limit);
}

function computeStability(forecasts: DbForecast[]): { label: string; stddev: number } {
  const moves = forecasts
    .filter(f => f.expectedMovePct !== undefined && f.expectedMovePct !== null)
    .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
    .slice(0, 7)
    .map(f => f.expectedMovePct!);

  if (moves.length < 2) return { label: 'unknown', stddev: 0 };

  const mean = moves.reduce((s, m) => s + m, 0) / moves.length;
  const variance = moves.reduce((s, m) => s + (m - mean) ** 2, 0) / (moves.length - 1);
  const stddev = Math.sqrt(variance);

  let label = 'stable';
  if (stddev >= 3) label = 'unstable';
  else if (stddev >= 1.5) label = 'moderate';

  return { label, stddev: Math.round(stddev * 100) / 100 };
}

export class ExchangeChartV3Service {
  async getChart(query: ExchangeChartV3Query): Promise<ExchangeChartV3Response> {
    const { asset, horizon } = query;
    const nowMs = Date.now();
    const nowSec = Math.floor(nowMs / 1000);
    const horizonDays = horizon === '1D' ? 1 : horizon === '7D' ? 7 : 30;

    // 1. Real candles
    const realCandles = await this.getCandles(asset);

    // 2. Forecasts for selected horizon
    const windowMs = FORECAST_WINDOW[horizon] || 7 * DAY_MS;
    const forecasts = await this.getForecasts(asset, horizonDays, nowMs - windowMs);
    const forecastPoints = buildForecastPoints(forecasts, horizonDays, nowMs, horizonDays);

    // 3. overlay7DPoints for 30D mode
    let overlay7DPoints: ForecastPoint[] = [];
    if (horizonDays === 30) {
      const forecasts7D = await this.getForecasts(asset, 7, nowMs - 7 * DAY_MS);
      overlay7DPoints = buildForecastPoints(forecasts7D, 7, nowMs, 7);
    }

    // 4. Stability
    const stability = computeStability(forecasts);

    // 5. Latest for header
    const latest = forecasts.sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))[0];

    return {
      ok: true,
      symbol: asset,
      nowTs: nowSec,
      horizonDays,
      realCandles,
      forecastPoints,
      overlay7DPoints: horizonDays === 30 ? overlay7DPoints : undefined,
      target: latest?.targetPrice ?? 0,
      confidence: latest?.confidence ?? 0,
      direction: normalizeDirection(latest?.direction),
      source: forecasts.length > 0 ? 'db' : 'fallback',
      meta: {
        stability: stability.label,
        stabilityStddev: stability.stddev,
        totalForecasts: forecasts.length,
        uniqueTargetDates: forecastPoints.length,
      },
    };
  }

  private async getForecasts(asset: string, horizonDays: number, minCreatedAt: number): Promise<DbForecast[]> {
    try {
      const { getDb } = await import('../../../db/mongodb.js');
      const db = getDb();
      return await db.collection('exchange_forecasts').find(
        { asset: asset.toUpperCase(), horizonDays, createdAt: { $gte: minCreatedAt } },
        { projection: { _id: 0 } }
      ).toArray() as unknown as DbForecast[];
    } catch (err: any) {
      console.warn('[ExchangeChartV3] DB error:', err.message);
      return [];
    }
  }

  private async getCandles(symbol: string): Promise<RealCandle[]> {
    try {
      const { getPriceHistory } = await import('../../market/chart/price.service.js');
      const { bars } = await getPriceHistory({
        symbol: `${symbol.toUpperCase()}USDT`,
        timeframe: '1h',
        limit: 168,
      });
      return bars.map(b => ({
        time: Math.floor(b.ts / 1000),
        open: b.o, high: b.h, low: b.l, close: b.c,
      }));
    } catch (err: any) {
      console.warn('[ExchangeChartV3] Candle error:', err.message);
      return [];
    }
  }
}

let instance: ExchangeChartV3Service | null = null;
export function getExchangeChartV3Service(): ExchangeChartV3Service {
  if (!instance) instance = new ExchangeChartV3Service();
  return instance;
}
