/**
 * OnChain V2 — DEX Sync Job
 * ==========================
 * 
 * Background job for syncing DEX swap events.
 * Runs every 60 seconds by default.
 */

import { getDexIngestionService } from './dex_ingestion.service.js';
import { runPerChain } from '../../system/runPerChain.js';
import type { RpcChainId } from '../../rpc-pool/models.js';

// Track running state to prevent overlap
let isRunning = false;
let lastRunResult: {
  chainId: RpcChainId;
  fromBlock: number;
  toBlock: number;
  swapsInserted: number;
  errors: number;
  runAt: number;
} | null = null;

/**
 * Run the DEX sync job for a specific chain
 */
export async function runDexSyncJob(chainId: RpcChainId = 1): Promise<typeof lastRunResult> {
  if (isRunning) {
    console.log('[DexSyncJob] Already running, skipping...');
    return lastRunResult;
  }

  const service = getDexIngestionService(chainId);
  
  if (!service.isEnabled()) {
    console.log('[DexSyncJob] DEX ingestion is disabled');
    return null;
  }

  isRunning = true;
  const startTime = Date.now();

  try {
    console.log(`[DexSyncJob] Starting DEX sync for chain ${chainId}...`);
    
    const result = await service.ingestRecent();
    
    lastRunResult = {
      chainId,
      fromBlock: result.fromBlock,
      toBlock: result.toBlock,
      swapsInserted: result.swapsInserted,
      errors: result.errors,
      runAt: startTime,
    };

    const duration = Date.now() - startTime;
    console.log(
      `[DexSyncJob] Completed: ${result.swapsInserted} swaps from blocks ${result.fromBlock}-${result.toBlock} (${duration}ms)`
    );

    return lastRunResult;
  } catch (err) {
    console.error('[DexSyncJob] Error:', err);
    lastRunResult = {
      chainId,
      fromBlock: 0,
      toBlock: 0,
      swapsInserted: 0,
      errors: 1,
      runAt: startTime,
    };
    return lastRunResult;
  } finally {
    isRunning = false;
  }
}

/**
 * Get last run result
 */
export function getLastDexSyncResult() {
  return lastRunResult;
}

/**
 * Check if job is currently running
 */
export function isDexSyncRunning(): boolean {
  return isRunning;
}

console.log('[OnChain V2] DEX Sync Job loaded');
