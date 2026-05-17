/**
 * Exchange Price Provider Health Service
 * ========================================
 * 
 * EX-S1: DataHealth component for Exchange URI.
 * 
 * Monitors:
 * - Candle freshness (staleness)
 * - Gap rate (missing candles)
 * - Coverage (symbols updating)
 * - Error rate
 */

import mongoose from 'mongoose';

export interface PriceProviderHealthConfig {
  symbols: string[];
  expectedCandleIntervalMin: number;  // e.g., 60 for 1h, 1440 for 1d
  maxStaleMultiplier: number;         // e.g., 3 => stale if > 3x interval
  lookbackCandles: number;            // e.g., 200 candles for gap check
}

export interface PriceProviderHealthResult {
  score: number;  // 0..1
  reasons: string[];
  metrics: {
    coveragePct: number;
    stalePct: number;
    gapPct: number;
    errorRate: number;
    worstLastCandleAgeMin: number;
    symbolsChecked: number;
    symbolsOk: number;
  };
  perSymbol?: Record<string, {
    ok: boolean;
    lastCandleAgeMin: number;
    gapPct: number;
  }>;
}

const DEFAULT_CONFIG: PriceProviderHealthConfig = {
  symbols: ['BTC', 'ETH', 'SOL', 'BNB', 'XRP'],
  expectedCandleIntervalMin: 60,  // 1h candles
  maxStaleMultiplier: 3,
  lookbackCandles: 168,  // 7 days of hourly
};

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

export class ExchangePriceProviderHealthService {
  private config: PriceProviderHealthConfig;

  constructor(config?: Partial<PriceProviderHealthConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Check price provider health by examining candle data
   */
  async check(): Promise<PriceProviderHealthResult> {
    const { symbols, expectedCandleIntervalMin, maxStaleMultiplier, lookbackCandles } = this.config;
    const reasons: string[] = [];
    const perSymbol: Record<string, { ok: boolean; lastCandleAgeMin: number; gapPct: number }> = {};

    let okCount = 0;
    let staleCount = 0;
    let totalGapPct = 0;
    let errorCount = 0;
    let worstAge = 0;

    const db = mongoose.connection.db;
    if (!db) {
      return {
        score: 0.5,
        reasons: ['DB_NOT_CONNECTED'],
        metrics: {
          coveragePct: 0,
          stalePct: 1,
          gapPct: 1,
          errorRate: 1,
          worstLastCandleAgeMin: Infinity,
          symbolsChecked: 0,
          symbolsOk: 0,
        },
      };
    }

    const now = Date.now();
    const staleThresholdMs = expectedCandleIntervalMin * maxStaleMultiplier * 60 * 1000;

    for (const symbol of symbols) {
      try {
        // Try to find candles from price_candles collection
        const candles = await db.collection('price_candles')
          .find({ symbol, interval: '1h' })
          .sort({ ts: -1 })
          .limit(lookbackCandles)
          .toArray();

        if (!candles.length) {
          // No candles found - check alternative collections
          const altCandles = await db.collection('exchange_candles')
            .find({ symbol })
            .sort({ ts: -1 })
            .limit(lookbackCandles)
            .toArray();

          if (!altCandles.length) {
            perSymbol[symbol] = { ok: false, lastCandleAgeMin: Infinity, gapPct: 1 };
            staleCount++;
            errorCount++;
            continue;
          }
        }

        const lastTs = candles.length ? (candles[0].ts || candles[0].timestamp) : 0;
        const lastTsMs = typeof lastTs === 'number' ? lastTs : new Date(lastTs).getTime();
        const ageMin = lastTsMs ? (now - lastTsMs) / 60000 : Infinity;
        worstAge = Math.max(worstAge, ageMin);

        const isStale = ageMin > expectedCandleIntervalMin * maxStaleMultiplier;
        if (isStale) staleCount++;

        // Estimate gap percentage
        const gapPct = this.estimateGapPct(candles, expectedCandleIntervalMin);
        totalGapPct += gapPct;

        const symOk = !isStale && gapPct < 0.10;
        if (symOk) okCount++;

        perSymbol[symbol] = {
          ok: symOk,
          lastCandleAgeMin: Math.round(ageMin),
          gapPct,
        };
      } catch (err) {
        errorCount++;
        perSymbol[symbol] = { ok: false, lastCandleAgeMin: Infinity, gapPct: 1 };
      }
    }

    const symbolsChecked = symbols.length;
    const coveragePct = symbolsChecked ? okCount / symbolsChecked : 0;
    const stalePct = symbolsChecked ? staleCount / symbolsChecked : 1;
    const avgGapPct = symbolsChecked ? totalGapPct / symbolsChecked : 1;
    const errorRate = symbolsChecked ? errorCount / symbolsChecked : 1;

    // Calculate score
    const score = clamp01(
      0.55 * coveragePct +
      0.20 * (1 - stalePct) +
      0.15 * (1 - clamp01(avgGapPct / 0.20)) +
      0.10 * (1 - errorRate)
    );

    // Build reasons
    if (coveragePct < 0.8) reasons.push('LOW_COVERAGE');
    if (stalePct > 0.2) reasons.push('STALE_CANDLES');
    if (avgGapPct > 0.10) reasons.push('GAPS_DETECTED');
    if (errorRate > 0.05) reasons.push('FETCH_ERRORS');
    if (score >= 0.75) reasons.push('PROVIDER_OK');

    return {
      score,
      reasons,
      metrics: {
        coveragePct,
        stalePct,
        gapPct: avgGapPct,
        errorRate,
        worstLastCandleAgeMin: Math.round(worstAge),
        symbolsChecked,
        symbolsOk: okCount,
      },
      perSymbol,
    };
  }

  /**
   * Estimate gap percentage from candle array
   */
  private estimateGapPct(candles: any[], intervalMin: number): number {
    if (candles.length < 3) return 1;

    const expectedMs = intervalMin * 60000;
    let gaps = 0;

    for (let i = 1; i < candles.length; i++) {
      const ts1 = candles[i].ts || candles[i].timestamp;
      const ts0 = candles[i - 1].ts || candles[i - 1].timestamp;
      const t1 = typeof ts1 === 'number' ? ts1 : new Date(ts1).getTime();
      const t0 = typeof ts0 === 'number' ? ts0 : new Date(ts0).getTime();
      const dt = Math.abs(t0 - t1);

      if (dt > expectedMs * 1.5) gaps++;
    }

    return gaps / Math.max(1, candles.length - 1);
  }
}

// Singleton
let providerHealthInstance: ExchangePriceProviderHealthService | null = null;

export function getExchangePriceProviderHealthService(): ExchangePriceProviderHealthService {
  if (!providerHealthInstance) {
    providerHealthInstance = new ExchangePriceProviderHealthService();
  }
  return providerHealthInstance;
}

console.log('[Exchange-ML] Price Provider Health Service loaded (EX-S1)');
