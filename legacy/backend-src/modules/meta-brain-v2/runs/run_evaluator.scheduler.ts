/**
 * META BRAIN V2 — RUN EVALUATOR SCHEDULER
 * ==========================================
 *
 * Periodically evaluates matured Meta Brain runs across all horizons.
 * Runs every EVAL_INTERVAL (6h by default), processing all 3 horizons
 * (1D, 7D, 30D) for BTC.
 *
 * This builds the ML dataset that will power the Self-Learning Layer.
 */

import { runMetaRunEvaluator } from './meta_run_evaluator.job.js';

const EVAL_INTERVAL = 6 * 60 * 60 * 1000; // 6 hours
const HORIZONS = [1, 7, 30] as const;
const ASSET = 'BTC';
const BATCH_LIMIT = 100;

let handle: NodeJS.Timeout | null = null;

async function evaluateAll(): Promise<void> {
  const t0 = Date.now();
  let totalEvaluated = 0;
  let totalSkipped = 0;
  let totalMatured = 0;

  for (const h of HORIZONS) {
    try {
      const result = await runMetaRunEvaluator(ASSET, h, BATCH_LIMIT);
      totalEvaluated += result.evaluated;
      totalSkipped += result.skipped;
      totalMatured += result.totalMatured;

      if (result.evaluated > 0) {
        console.log(`[RunEvalScheduler] ${h}D: evaluated=${result.evaluated}, skipped=${result.skipped}`);
      }
    } catch (err: any) {
      console.error(`[RunEvalScheduler] ${h}D error:`, err?.message);
    }
  }

  const ms = Date.now() - t0;
  if (totalMatured > 0) {
    console.log(`[RunEvalScheduler] Done in ${ms}ms — evaluated=${totalEvaluated}, skipped=${totalSkipped}, matured=${totalMatured}`);
  }
}

export function startRunEvaluatorScheduler(): void {
  if (handle) return;
  console.log(`[RunEvalScheduler] Starting (every ${EVAL_INTERVAL / 3600000}h, horizons=${HORIZONS.join(',')})`);
  // Initial run after 30s delay (let other services boot)
  setTimeout(() => {
    evaluateAll();
    handle = setInterval(evaluateAll, EVAL_INTERVAL);
  }, 30_000);
}

export function stopRunEvaluatorScheduler(): void {
  if (handle) {
    clearInterval(handle);
    handle = null;
  }
}
