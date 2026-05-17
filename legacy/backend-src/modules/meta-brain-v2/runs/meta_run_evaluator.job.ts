/**
 * META BRAIN V2 — ML DATASET BUILDER (Run Evaluator)
 * =====================================================
 *
 * Evaluates matured Meta Brain runs to build the ML dataset.
 *
 * For each run:
 *   1. Wait for horizon to close (anchorTs + horizonDays has passed)
 *   2. Fetch entry price (at anchorTs) and exit price (at anchorTs + horizon)
 *   3. Compute:
 *      - futureReturn  = (exitPrice - entryPrice) / entryPrice
 *      - futureDirection = LONG if return > band, SHORT if < -band, else NEUTRAL
 *      - hit = (metaFinalVerdict === futureDirection)
 *
 * Neutral bands:
 *   1D:  0.15%
 *   7D:  0.50%
 *   30D: 1.00%
 *
 * Price source: Bybit BTCUSDT kline API.
 *
 * This is SEPARATE from the per-module performance evaluator.
 * It evaluates the Meta Brain's OVERALL verdict for ML training.
 */

import { getMongoDb } from '../../../db/mongoose.js';

const COLLECTION = 'meta_brain_runs';

const NEUTRAL_BAND: Record<number, number> = {
  1:  0.0015,
  7:  0.005,
  30: 0.01,
};

const BYBIT_BASE = 'https://api.bybit.com';

interface RunEvalResult {
  evaluated: number;
  skipped: number;
  alreadyEvaluated: number;
  totalMatured: number;
  errors: string[];
  samples: Array<{
    runId: string;
    futureReturn: number;
    futureDirection: string;
    metaVerdict: string;
    hit: boolean;
  }>;
}

/**
 * Fetch price at a given timestamp from Bybit daily klines.
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
 * Find matured runs that haven't been evaluated for the ML dataset.
 * A run is "matured" when anchorTs + horizonDays has passed.
 */
async function getMaturedUnevaluatedRuns(
  asset: string,
  horizonDays: number,
  nowTs: number,
  limit: number
): Promise<any[]> {
  const db = getMongoDb();
  if (!db) return [];

  const maturityMs = horizonDays * 24 * 3600 * 1000;
  const cutoff = nowTs - maturityMs;

  const docs = await db.collection(COLLECTION)
    .find(
      {
        asset,
        horizonDays,
        futureReturn: { $exists: false },
        anchorTs: { $lte: cutoff },
      },
      { projection: { _id: 0 } }
    )
    .sort({ anchorTs: 1 })
    .limit(limit)
    .toArray();

  return docs;
}

/**
 * Run the ML dataset evaluator for a specific asset and horizon.
 */
export async function runMetaRunEvaluator(
  asset: string,
  horizonDays: number,
  limit: number = 200
): Promise<RunEvalResult> {
  const db = getMongoDb();
  const nowTs = Date.now();
  const runs = await getMaturedUnevaluatedRuns(asset, horizonDays, nowTs, limit);

  const result: RunEvalResult = {
    evaluated: 0,
    skipped: 0,
    alreadyEvaluated: 0,
    totalMatured: runs.length,
    errors: [],
    samples: [],
  };

  if (!db) {
    result.errors.push('No database connection');
    return result;
  }

  for (const run of runs) {
    const exitTs = run.anchorTs + horizonDays * 24 * 3600 * 1000;

    // Fetch entry and exit prices
    const [entryPrice, exitPrice] = await Promise.all([
      fetchPrice(asset, run.anchorTs),
      fetchPrice(asset, exitTs),
    ]);

    if (entryPrice === null || exitPrice === null) {
      result.skipped++;
      result.errors.push(`${run.runId}: price fetch failed (entry=${entryPrice}, exit=${exitPrice})`);
      continue;
    }

    const futureReturn = (exitPrice - entryPrice) / entryPrice;
    const band = NEUTRAL_BAND[horizonDays] ?? 0.005;

    let futureDirection: string;
    if (futureReturn > band) futureDirection = 'LONG';
    else if (futureReturn < -band) futureDirection = 'SHORT';
    else futureDirection = 'NEUTRAL';

    const hit = run.metaFinalVerdict === futureDirection;

    // Update run document with ML dataset fields
    await db.collection(COLLECTION).updateOne(
      { runId: run.runId },
      {
        $set: {
          futureReturn,
          futureDirection,
          hit,
          mlEvaluatedAt: nowTs,
          entryPrice,
          exitPrice,
        },
      }
    );

    result.evaluated++;
    result.samples.push({
      runId: run.runId,
      futureReturn,
      futureDirection,
      metaVerdict: run.metaFinalVerdict,
      hit,
    });
  }

  return result;
}
