/**
 * Token Series Job — Phase D3
 * ==============================
 * Periodic aggregation of token flows into pre-computed buckets.
 * Runs every 10 minutes, processes all active tokens.
 */

import { aggregateTokenBuckets, getActiveTokens } from './tokenSeriesAggregate.service';
import { runPerChain } from '../../system/runPerChain';

let running = false;
let lastRunAt: Date | null = null;
let lastError: string | null = null;
let tickCount = 0;
let successCount = 0;
let errorCount = 0;
let tokensProcessed = 0;

export async function runTokenSeriesJob(): Promise<void> {
  if (running) {
    console.log('[TokenSeriesJob] Already running, skipping');
    return;
  }
  running = true;
  tickCount++;
  tokensProcessed = 0;

  try {
    await runPerChain('TokenSeriesJob', async (chainId) => {
      const tokens = getActiveTokens(chainId);

      console.log(`[TokenSeriesJob] chain=${chainId}: Processing ${tokens.length} tokens...`);

      for (const tokenAddr of tokens) {
        try {
          await aggregateTokenBuckets(chainId, tokenAddr);
          tokensProcessed++;
        } catch (err: any) {
          console.error(`[TokenSeriesJob] chain=${chainId} Failed for ${tokenAddr.slice(0, 10)}:`, err?.message);
        }
      }
    });

    successCount++;
    lastRunAt = new Date();
    lastError = null;
    console.log(`[TokenSeriesJob] Done: ${tokensProcessed} tokens across all chains`);
  } catch (e: any) {
    errorCount++;
    lastError = String(e?.message || e);
    console.error('[TokenSeriesJob] Failed:', lastError);
  } finally {
    running = false;
  }
}

export function getTokenSeriesJobStatus() {
  return {
    running,
    tickCount,
    successCount,
    errorCount,
    tokensProcessed,
    lastRunAt: lastRunAt?.toISOString() ?? null,
    lastError,
  };
}

export function isTokenSeriesJobRunning(): boolean {
  return running;
}

export async function forceTokenSeriesTick() {
  await runTokenSeriesJob();
  return getTokenSeriesJobStatus();
}
