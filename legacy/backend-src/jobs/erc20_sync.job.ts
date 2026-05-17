/**
 * OnChain V2 — ERC20 Sync Job
 * ============================
 * 
 * Periodic job to sync ERC20 transfers from blockchain.
 * Runs every 30 seconds.
 */

import { erc20Indexer } from '../modules/onchain_v2/ingestion/erc20/index.js';
import type { RpcChainId } from '../modules/onchain_v2/rpc-pool/models.js';

// ═══════════════════════════════════════════════════════════════
// JOB STATE
// ═══════════════════════════════════════════════════════════════

interface JobState {
  running: boolean;
  lastRunAt: number;
  lastResult: {
    ok: boolean;
    logsProcessed: number;
    errors: string[];
  } | null;
  runCount: number;
  errorCount: number;
}

const state: JobState = {
  running: false,
  lastRunAt: 0,
  lastResult: null,
  runCount: 0,
  errorCount: 0,
};

// Chains to sync (can be configured via env)
const CHAINS_TO_SYNC: RpcChainId[] = [1];  // ETH mainnet only for now

// ═══════════════════════════════════════════════════════════════
// JOB FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Run ERC20 sync job
 */
export async function runERC20SyncJob(): Promise<void> {
  if (state.running) {
    console.log('[ERC20SyncJob] Already running, skipping');
    return;
  }
  
  state.running = true;
  state.lastRunAt = Date.now();
  state.runCount++;
  
  try {
    let totalLogs = 0;
    const errors: string[] = [];
    
    for (const chainId of CHAINS_TO_SYNC) {
      try {
        const result = await erc20Indexer.sync({
          chainId,
          maxBlocksPerBatch: 50,
        });
        
        totalLogs += result.logsProcessed;
        errors.push(...result.errors);
        
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        errors.push(`Chain ${chainId}: ${message}`);
        state.errorCount++;
      }
    }
    
    state.lastResult = {
      ok: errors.length === 0,
      logsProcessed: totalLogs,
      errors,
    };
    
    if (totalLogs > 0 || errors.length > 0) {
      console.log(`[ERC20SyncJob] Completed: ${totalLogs} logs, ${errors.length} errors`);
    }
    
  } catch (error) {
    console.error('[ERC20SyncJob] Fatal error:', error);
    state.errorCount++;
    state.lastResult = {
      ok: false,
      logsProcessed: 0,
      errors: [error instanceof Error ? error.message : 'Unknown error'],
    };
  } finally {
    state.running = false;
  }
}

/**
 * Get job status
 */
export function getERC20SyncJobStatus(): {
  enabled: boolean;
  running: boolean;
  lastRunAt: number;
  lastResult: JobState['lastResult'];
  runCount: number;
  errorCount: number;
  chains: RpcChainId[];
} {
  return {
    enabled: process.env.ONCHAIN_V2_ENABLED === 'true' && 
             process.env.ERC20_SYNC_ENABLED !== 'false',
    running: state.running,
    lastRunAt: state.lastRunAt,
    lastResult: state.lastResult,
    runCount: state.runCount,
    errorCount: state.errorCount,
    chains: CHAINS_TO_SYNC,
  };
}

/**
 * Check if job is enabled
 */
export function isERC20SyncJobEnabled(): boolean {
  return process.env.ONCHAIN_V2_ENABLED === 'true' && 
         process.env.ERC20_SYNC_ENABLED !== 'false';
}

console.log('[OnChain V2] ERC20 Sync Job loaded');
