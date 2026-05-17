/**
 * META BRAIN V2 — PERFORMANCE EVALUATOR JOB
 * ============================================
 *
 * Evaluates matured runs: checks actual price vs predicted direction.
 *
 * Hit rules:
 *   LONG  → actualReturn > 0        → hit
 *   SHORT → actualReturn < 0        → hit
 *   NEUTRAL → abs(return) <= band   → hit
 *
 * Neutral bands:
 *   1D:  0.15%
 *   7D:  0.50%
 *   30D: 1.00%
 *
 * Price source: Bybit BTCUSDT kline API.
 */

import { getUnevaluatedRuns, markRunEvaluated } from '../runs/meta_brain_runs.repo.js';
import { incrementPerformance } from './performance.repo.js';

const NEUTRAL_BAND: Record<number, number> = {
  1:  0.0015,
  7:  0.005,
  30: 0.01,
};

const BYBIT_BASE = 'https://api.bybit.com';

interface EvalResult {
  evaluated: number;
  skipped: number;
  errors: string[];
}

/**
 * Fetch BTC price at a given timestamp from Bybit klines.
 * Returns close price of the 1D candle that contains the timestamp.
 */
async function fetchPrice(asset: string, ts: number): Promise<number | null> {
  try {
    const symbol = `${asset}USDT`;
    const url = `${BYBIT_BASE}/v5/market/kline?category=linear&symbol=${symbol}&interval=D&start=${ts}&limit=1`;
    const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
    const data = await resp.json() as any;

    if (data.retCode !== 0 || !data.result?.list?.length) return null;

    // Bybit kline: [startTime, open, high, low, close, volume, turnover]
    const candle = data.result.list[0];
    return parseFloat(candle[4]); // close price
  } catch {
    return null;
  }
}

/**
 * Run the performance evaluator for a specific asset and horizon.
 */
export async function evaluatePerformance(
  asset: string,
  horizonDays: number,
  limit: number = 200
): Promise<EvalResult> {
  const nowTs = Date.now();
  const runs = await getUnevaluatedRuns(asset, horizonDays, nowTs, limit);

  let evaluated = 0;
  let skipped = 0;
  const errors: string[] = [];

  for (const run of runs) {
    const exitTs = run.anchorTs + horizonDays * 24 * 3600 * 1000;

    // Fetch entry and exit prices
    const [entryPrice, exitPrice] = await Promise.all([
      fetchPrice(asset, run.anchorTs),
      fetchPrice(asset, exitTs),
    ]);

    if (entryPrice === null || exitPrice === null) {
      skipped++;
      errors.push(`${run.runId}: could not fetch prices (entry=${entryPrice}, exit=${exitPrice})`);
      continue;
    }

    const actualReturn = (exitPrice - entryPrice) / entryPrice;
    const band = NEUTRAL_BAND[horizonDays] ?? 0.005;

    let actualDirection: string;
    if (actualReturn > band) actualDirection = 'LONG';
    else if (actualReturn < -band) actualDirection = 'SHORT';
    else actualDirection = 'NEUTRAL';

    // Evaluate each module signal
    for (const sig of run.signals) {
      const hit = sig.direction === actualDirection;
      const absError = Math.abs(actualReturn);

      await incrementPerformance(
        sig.moduleId,
        asset,
        horizonDays,
        hit,
        absError,
        nowTs
      );
    }

    // Mark run as evaluated
    await markRunEvaluated(run.runId, actualReturn, actualDirection, nowTs);
    evaluated++;
  }

  return { evaluated, skipped, errors };
}
