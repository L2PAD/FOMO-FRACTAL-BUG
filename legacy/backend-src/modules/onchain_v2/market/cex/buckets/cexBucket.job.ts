/**
 * CEX Bucket Job — Phase A3.3
 * ============================
 * Periodic aggregation of CEX flows into pre-computed buckets.
 * Registered in the scheduler, runs every 10 minutes.
 */

import { CexBucketAggregateService } from './cexBucketAggregate.service';
import { runPerChain } from '../../../system/runPerChain';

let running = false;
let lastRunAt: Date | null = null;
let lastError: string | null = null;
let tickCount = 0;
let successCount = 0;
let errorCount = 0;

const aggregateService = new CexBucketAggregateService();

export async function runCexBucketJob(): Promise<void> {
  if (running) {
    console.log('[CexBucketJob] Already running, skipping');
    return;
  }
  running = true;
  tickCount++;

  try {
    await runPerChain('CexBucketJob', async (chainId) => {
      const r24 = await aggregateService.aggregateWindow({ chainId, window: '24h' });
      const r7d = await aggregateService.aggregateWindow({ chainId, window: '7d' });

      console.log(
        `[CexBucketJob] chain=${chainId}: 24h=${r24.bucketsUpserted} buckets (${r24.elapsed}ms), ` +
        `7d=${r7d.bucketsUpserted} buckets (${r7d.elapsed}ms)`
      );
    });

    successCount++;
    lastRunAt = new Date();
    lastError = null;
  } catch (e: any) {
    errorCount++;
    lastError = String(e?.message || e);
    console.error('[CexBucketJob] Failed:', lastError);
  } finally {
    running = false;
  }
}

export function getCexBucketJobStatus() {
  return {
    running,
    tickCount,
    successCount,
    errorCount,
    lastRunAt: lastRunAt?.toISOString() ?? null,
    lastError,
  };
}

export function isCexBucketJobRunning(): boolean {
  return running;
}

/**
 * Force-tick (manual trigger via API)
 */
export async function forceCexBucketTick() {
  await runCexBucketJob();
  return getCexBucketJobStatus();
}
