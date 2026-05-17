/**
 * OnChain V2 — Pool Liquidity Job
 * =================================
 * 
 * STEP 4.1: TVL/Liquidity Scoring Integration
 * Periodic job to refresh pool liquidity data.
 */

import { poolLiquidityService } from './poolLiquidity.service';
import { poolScoringService } from '../poolScoring.service';
import { runPerChain } from '../../../../system/runPerChain';
import type { LiquidityRefreshResult } from './liquidity.types';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const JOB_ENABLED = process.env.ONCHAIN_V2_LIQUIDITY_JOB_ENABLED !== 'false';
const JOB_INTERVAL_MS = parseInt(process.env.ONCHAIN_V2_LIQUIDITY_JOB_INTERVAL_MS || '600000', 10); // 10 min
const RESCORE_AFTER_REFRESH = process.env.ONCHAIN_V2_LIQUIDITY_RESCORE !== 'false';

// ═══════════════════════════════════════════════════════════════
// JOB STATE
// ═══════════════════════════════════════════════════════════════

interface JobState {
  running: boolean;
  lastRunAt: number | null;
  lastResult: LiquidityRefreshResult | null;
  tickCount: number;
  intervalHandle: NodeJS.Timeout | null;
}

const state: JobState = {
  running: false,
  lastRunAt: null,
  lastResult: null,
  tickCount: 0,
  intervalHandle: null,
};

// ═══════════════════════════════════════════════════════════════
// JOB FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Run a single tick of the liquidity refresh job
 */
async function tick(): Promise<LiquidityRefreshResult | null> {
  if (!JOB_ENABLED) {
    console.log('[LiquidityJob] Job disabled');
    return null;
  }
  
  if (state.running) {
    console.log('[LiquidityJob] Already running, skipping tick');
    return null;
  }
  
  state.running = true;
  state.tickCount++;
  
  try {
    console.log(`[LiquidityJob] Tick #${state.tickCount} starting...`);
    
    // Refresh liquidity for each enabled chain
    await runPerChain('PoolLiquidityJob', async (chainId) => {
      const result = await poolLiquidityService.refreshChain(chainId);
      
      state.lastRunAt = Date.now();
      state.lastResult = result;
      
      // Re-score pools after liquidity refresh
      if (RESCORE_AFTER_REFRESH && result.poolsUpdated > 0) {
        console.log(`[LiquidityJob] chain=${chainId}: Re-scoring pools after liquidity refresh...`);
        const scoreResult = await poolScoringService.scorePoolsForChain({ chainId });
        console.log(
          `[LiquidityJob] chain=${chainId}: Re-scored ${scoreResult.updated} pools: ` +
          `ACTIVE=${scoreResult.summary.ACTIVE}, DEGRADED=${scoreResult.summary.DEGRADED}, ` +
          `DISABLED=${scoreResult.summary.DISABLED}`
        );
      }
    });
    
    return result;
  } catch (err) {
    console.error('[LiquidityJob] Tick error:', err);
    return null;
  } finally {
    state.running = false;
  }
}

/**
 * Start the job
 */
export function startPoolLiquidityJob(): { running: boolean } {
  if (state.intervalHandle) {
    console.log('[LiquidityJob] Already started');
    return { running: true };
  }
  
  if (!JOB_ENABLED) {
    console.log('[LiquidityJob] Job disabled by config');
    return { running: false };
  }
  
  console.log(`[LiquidityJob] Starting with interval ${JOB_INTERVAL_MS}ms`);
  
  // Run first tick immediately
  tick().catch(console.error);
  
  // Schedule periodic ticks
  state.intervalHandle = setInterval(() => {
    tick().catch(console.error);
  }, JOB_INTERVAL_MS);
  
  return { running: true };
}

/**
 * Stop the job
 */
export function stopPoolLiquidityJob(): void {
  if (state.intervalHandle) {
    clearInterval(state.intervalHandle);
    state.intervalHandle = null;
    console.log('[LiquidityJob] Stopped');
  }
}

/**
 * Force run a tick
 */
export async function forceRunPoolLiquidityJob(): Promise<LiquidityRefreshResult | null> {
  return tick();
}

/**
 * Get job status
 */
export function getPoolLiquidityJobStatus(): {
  enabled: boolean;
  running: boolean;
  lastRunAt: number | null;
  tickCount: number;
  intervalMs: number;
} {
  return {
    enabled: JOB_ENABLED,
    running: state.running,
    lastRunAt: state.lastRunAt,
    tickCount: state.tickCount,
    intervalMs: JOB_INTERVAL_MS,
  };
}

console.log('[OnChain V2] Pool Liquidity Job loaded');
