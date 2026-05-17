/**
 * Exchange Performance V2 Service
 * =================================
 *
 * READS FROM MongoDB `exchange_forecasts` — NO MOCK DATA.
 *
 * Architecture:
 *   exchange_forecasts (immutable append-only)
 *     → Performance API reads & buckets
 *     → UI renders real data
 *
 * Outcome buckets:
 *   evaluated: outcome.label IN (TP, FP, WEAK, FN)
 *   pending:   evaluated=false AND evaluateAfter > now
 *   overdue:   evaluated=false AND evaluateAfter <= now
 *
 * WinRate = TP / (TP + FP + WEAK)
 */

import { getDb } from '../../../db/mongodb.js';
import {
  ExchangePerformanceResponse,
  ExchangePerformanceRow,
  Horizon,
  OutcomeType,
} from './exchange-chart-v2.types.js';

export class ExchangePerformanceV2Service {
  async getPerformance(
    symbol: string,
    horizon: Horizon,
    limit: number = 30
  ): Promise<ExchangePerformanceResponse> {
    const db = getDb();
    const col = db.collection('exchange_forecasts');
    const now = Date.now();

    // Query forecasts for this symbol+horizon, sorted by createdAt DESC
    // Fetch more for 30D to ensure key dates are captured
    const fetchLimit = horizon === '30D' ? Math.max(limit * 3, 90) : limit * 2;
    const docs = await col
      .find({
        asset: symbol,
        horizon: horizon,
      })
      .sort({ createdAt: -1 })
      .limit(fetchLimit)
      .toArray();

    // Deduplicate by evaluateAt date — keep latest record per eval date
    const evalMap = new Map<string, any>();
    for (const doc of docs) {
      const createdMs = doc.createdAt > 1e12 ? doc.createdAt : doc.createdAt * 1000;
      const hDays = doc.horizonDays || (horizon === '24H' ? 1 : horizon === '7D' ? 7 : 30);
      const evalMs = doc.evaluateAfter || (createdMs + hDays * 86400000);
      const evalKey = new Date(evalMs).toISOString().slice(0, 10); // YYYY-MM-DD
      if (!evalMap.has(evalKey) || createdMs > (evalMap.get(evalKey)!.createdAt > 1e12 ? evalMap.get(evalKey)!.createdAt : evalMap.get(evalKey)!.createdAt * 1000)) {
        evalMap.set(evalKey, doc);
      }
    }

    // Convert to sorted array (newest evalAt first), limited
    // BUT always include yesterday/today/tomorrow for UI consistency
    const todayKey = new Date(now).toISOString().slice(0, 10);
    const yesterdayKey = new Date(now - 86400000).toISOString().slice(0, 10);
    const tomorrowKey = new Date(now + 86400000).toISOString().slice(0, 10);
    const keyDates = new Set([yesterdayKey, todayKey, tomorrowKey]);

    const allSorted = [...evalMap.values()]
      .sort((a, b) => {
        const aMs = a.createdAt > 1e12 ? a.createdAt : a.createdAt * 1000;
        const bMs = b.createdAt > 1e12 ? b.createdAt : b.createdAt * 1000;
        return bMs - aMs;
      });

    // Ensure key dates are always included
    const keyDateDocs: any[] = [];
    const rest: any[] = [];
    for (const doc of allSorted) {
      const createdMs = doc.createdAt > 1e12 ? doc.createdAt : doc.createdAt * 1000;
      const hDays = doc.horizonDays || (horizon === '24H' ? 1 : horizon === '7D' ? 7 : 30);
      const evalMs = doc.evaluateAfter || (createdMs + hDays * 86400000);
      const evalDateKey = new Date(evalMs).toISOString().slice(0, 10);
      if (keyDates.has(evalDateKey)) {
        keyDateDocs.push(doc);
      } else {
        rest.push(doc);
      }
    }

    const dedupedDocs = [...keyDateDocs, ...rest.slice(0, limit - keyDateDocs.length)];

    // Map to rows with proper status bucketing
    const rows: ExchangePerformanceRow[] = dedupedDocs.map((doc: any) => {
      const createdMs = doc.createdAt > 1e12 ? doc.createdAt : doc.createdAt * 1000;
      const hDays = doc.horizonDays || (horizon === '24H' ? 1 : horizon === '7D' ? 7 : 30);
      const evaluated = doc.evaluated === true && doc.outcome?.label;
      const evaluateAfter = doc.evaluateAfter || (createdMs + hDays * 86400000);

      // Determine outcome
      let outcome: OutcomeType = 'PENDING';
      if (evaluated && doc.outcome?.label) {
        outcome = doc.outcome.label as OutcomeType;
      } else if (evaluateAfter <= now) {
        outcome = 'OVERDUE';
      }

      // Map direction: UP→LONG, DOWN→SHORT, NEUTRAL→NEUTRAL
      const direction = doc.direction === 'UP' ? 'LONG' as const
        : doc.direction === 'DOWN' ? 'SHORT' as const
        : 'NEUTRAL' as const;

      return {
        createdAt: new Date(doc.createdAt).toISOString(),
        evaluateAt: new Date(evaluateAfter).toISOString(),
        horizon: doc.horizon,
        symbol: doc.asset,
        entry: doc.entryPrice || doc.basePrice,
        actual: doc.outcome?.realPrice ?? null,
        rawTarget: doc.targetPrice,
        finalTarget: doc.targetPrice,
        rawConfidence: doc.confidenceRaw ?? doc.confidence,
        finalConfidence: doc.confidence,
        direction,
        outcome,
        flags: [],
      };
    });

    // Calculate summary from evaluated only
    const evaluated = rows.filter(r =>
      !['PENDING', 'OVERDUE', 'VOIDED'].includes(r.outcome)
    );
    const wins = evaluated.filter(r => r.outcome === 'TP').length;
    const losses = evaluated.filter(r => r.outcome === 'FP').length;
    const weak = evaluated.filter(r => r.outcome === 'WEAK').length;
    const fn = evaluated.filter(r => r.outcome === 'FN').length;
    const pending = rows.filter(r => r.outcome === 'PENDING').length;
    const overdue = rows.filter(r => r.outcome === 'OVERDUE').length;

    const denom = wins + losses + weak;
    const winRate = denom > 0 ? wins / denom : 0;

    const returns = evaluated.map(r => {
      if (!r.actual) return 0;
      return r.direction === 'LONG'
        ? (r.actual - r.entry) / r.entry
        : r.direction === 'SHORT'
        ? (r.entry - r.actual) / r.entry
        : 0;
    });
    const avgReturn = returns.length > 0
      ? returns.reduce((a, b) => a + b, 0) / returns.length
      : 0;

    return {
      ok: true,
      symbol,
      horizon,
      rows,
      summary: {
        total: rows.length,
        evaluated: evaluated.length,
        wins, losses, weak, fn, pending, overdue,
        winRate,
        avgReturn,
      },
    };
  }
}

// Singleton
let instance: ExchangePerformanceV2Service | null = null;

export function getExchangePerformanceV2Service(): ExchangePerformanceV2Service {
  if (!instance) {
    instance = new ExchangePerformanceV2Service();
  }
  return instance;
}
