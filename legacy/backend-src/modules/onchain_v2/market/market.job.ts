/**
 * Market Series Job
 * ==================
 * 
 * PHASE 1: Liquidity & Alt Rotation Engine
 * 
 * Runs every 10 minutes to collect and persist market series.
 */

import { collectMarketSnapshot, saveMarketSnapshot } from './market.service';
import { runPerChain } from '../system/runPerChain';

const JOB_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

let jobTimer: NodeJS.Timeout | null = null;
let isRunning = false;
let lastRunTimestamp = 0;
let consecutiveErrors = 0;
const MAX_CONSECUTIVE_ERRORS = 5;

/**
 * Execute one market snapshot collection
 */
async function runMarketJob(): Promise<void> {
  if (isRunning) {
    console.log('[Market Job] Already running, skipping');
    return;
  }

  isRunning = true;
  const startTime = Date.now();

  try {
    console.log('[Market Job] Starting collection...');

    await runPerChain('MarketSeriesJob', async (chainId) => {
      const snapshot = await collectMarketSnapshot();
      const savedCount = await saveMarketSnapshot(snapshot);
      
      console.log(
        `[Market Job] chain=${chainId}: Saved ${savedCount} series. Sources: dom=${snapshot.sources.dominance}, supply=${snapshot.sources.supply}`
      );
    });

    lastRunTimestamp = Date.now();
    consecutiveErrors = 0;

    console.log(`[Market Job] Completed in ${Date.now() - startTime}ms.`);
  } catch (error) {
    consecutiveErrors++;
    console.error(`[Market Job] Error (${consecutiveErrors}/${MAX_CONSECUTIVE_ERRORS}):`, error);

    if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
      console.error('[Market Job] Too many consecutive errors, stopping job');
      stopMarketJob();
    }
  } finally {
    isRunning = false;
  }
}

/**
 * Start the market series job
 */
export function startMarketJob(): void {
  if (jobTimer) {
    console.log('[Market Job] Already started');
    return;
  }

  console.log(`[Market Job] Starting with interval ${JOB_INTERVAL_MS / 1000}s`);

  // Run immediately on start
  runMarketJob();

  // Then run on interval
  jobTimer = setInterval(runMarketJob, JOB_INTERVAL_MS);
}

/**
 * Stop the market series job
 */
export function stopMarketJob(): void {
  if (jobTimer) {
    clearInterval(jobTimer);
    jobTimer = null;
    console.log('[Market Job] Stopped');
  }
}

/**
 * Get job status
 */
export function getMarketJobStatus(): {
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
export async function forceRunMarketJob(): Promise<void> {
  await runMarketJob();
}

console.log('[Market Job] Module loaded');
