/**
 * LiquidityScore Job
 * ===================
 * 
 * PHASE 2.1: Scheduler for liquidity computation
 * 
 * Runs every 10 minutes, after market.job
 */

import { tickLiquidity } from './liquidity.service';
import { runPerChain } from '../../system/runPerChain';

const JOB_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes
const JOB_OFFSET_MS = 60 * 1000; // 1 minute after market job

let jobTimer: NodeJS.Timeout | null = null;
let isRunning = false;
let lastRunTimestamp = 0;
let consecutiveErrors = 0;
const MAX_CONSECUTIVE_ERRORS = 5;

/**
 * Execute one liquidity tick
 */
async function runLiquidityJob(): Promise<void> {
  if (isRunning) {
    console.log('[Liquidity Job] Already running, skipping');
    return;
  }

  isRunning = true;
  const startTime = Date.now();

  try {
    console.log('[Liquidity Job] Starting tick...');

    await runPerChain('LiquidityJob', async (chainId) => {
      const point = await tickLiquidity();
      console.log(
        `[Liquidity Job] chain=${chainId}: Score=${point.score}, Regime=${point.regime}, Conf=${point.confidence.toFixed(2)}`
      );
    });

    lastRunTimestamp = Date.now();
    consecutiveErrors = 0;

    console.log(`[Liquidity Job] Completed in ${Date.now() - startTime}ms.`);
  } catch (error) {
    consecutiveErrors++;
    console.error(`[Liquidity Job] Error (${consecutiveErrors}/${MAX_CONSECUTIVE_ERRORS}):`, error);

    if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
      console.error('[Liquidity Job] Too many consecutive errors, stopping job');
      stopLiquidityJob();
    }
  } finally {
    isRunning = false;
  }
}

/**
 * Start the liquidity job (with offset after market job)
 */
export function startLiquidityJob(): void {
  if (jobTimer) {
    console.log('[Liquidity Job] Already started');
    return;
  }

  console.log(`[Liquidity Job] Starting with interval ${JOB_INTERVAL_MS / 1000}s (offset ${JOB_OFFSET_MS / 1000}s)`);

  // Run after short delay (to let market job run first)
  setTimeout(() => {
    runLiquidityJob();
  }, JOB_OFFSET_MS);

  // Then run on interval
  jobTimer = setInterval(runLiquidityJob, JOB_INTERVAL_MS);
}

/**
 * Stop the liquidity job
 */
export function stopLiquidityJob(): void {
  if (jobTimer) {
    clearInterval(jobTimer);
    jobTimer = null;
    console.log('[Liquidity Job] Stopped');
  }
}

/**
 * Get job status
 */
export function getLiquidityJobStatus(): {
  running: boolean;
  lastRun: number;
  intervalMs: number;
  consecutiveErrors: number;
} {
  return {
    running: jobTimer !== null,
    lastRun: lastRunTimestamp,
    intervalMs: JOB_INTERVAL_MS,
    consecutiveErrors,
  };
}

/**
 * Force run job (for admin/testing)
 */
export async function forceRunLiquidityJob(): Promise<void> {
  await runLiquidityJob();
}

console.log('[Liquidity Job] Module loaded');
