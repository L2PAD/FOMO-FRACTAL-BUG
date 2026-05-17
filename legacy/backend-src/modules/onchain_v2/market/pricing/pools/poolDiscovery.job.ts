/**
 * OnChain V2 — Pool Discovery Job
 * =================================
 * 
 * STEP 4.1: Scheduled job for pool discovery, TVL refresh, and scoring
 * 
 * Flow: discover → TVL refresh → score → activate
 */

import { poolDiscoveryService } from './poolDiscovery.service';
import { poolScoringService } from './poolScoring.service';
import { poolLiquidityService } from './liquidity/poolLiquidity.service';
import { chainRegistry } from '../../../chains';
import { ONCHAIN_FLAGS } from '../../../core/featureFlags';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface JobState {
  running: boolean;
  lastRunAt: number | null;
  lastResult: {
    chainId: number;
    discovered: number;
    tvlRefreshed: number;
    scored: number;
    statusSummary: Record<string, number>;
  }[] | null;
  nextRunAt: number | null;
  intervalMs: number;
  enabled: boolean;
  tickCount: number;
}

// ═══════════════════════════════════════════════════════════════
// JOB
// ═══════════════════════════════════════════════════════════════

let jobHandle: NodeJS.Timeout | null = null;
let jobState: JobState = {
  running: false,
  lastRunAt: null,
  lastResult: null,
  nextRunAt: null,
  intervalMs: 0,
  enabled: false,
  tickCount: 0,
};

/**
 * Run one discovery + TVL + scoring tick
 */
async function tick(): Promise<void> {
  if (jobState.running) {
    console.log('[PoolDiscoveryJob] Tick skipped - already running');
    return;
  }
  
  jobState.running = true;
  jobState.tickCount++;
  const results: JobState['lastResult'] = [];
  
  try {
    // Phase 5.3: Feature flag checks
    if (ONCHAIN_FLAGS.FREEZE_MODE) {
      console.log('[PoolDiscoveryJob] FREEZE_MODE active — skipping tick');
      return;
    }

    const activeChains = chainRegistry.getActiveIds();
    
    for (const chainId of activeChains) {
      try {
        console.log(`[PoolDiscoveryJob] Starting tick #${jobState.tickCount} for chain ${chainId}...`);
        
        // 1. Discover new pools from Token Universe
        const discovery = ONCHAIN_FLAGS.DISCOVERY_WRITE
          ? await poolDiscoveryService.discoverFromUniverse({ chainId })
          : { poolsFound: 0, poolsUpserted: 0 };
        if (!ONCHAIN_FLAGS.DISCOVERY_WRITE) {
          console.log(`[PoolDiscoveryJob] Chain ${chainId}: discovery write disabled`);
        } else {
          console.log(`[PoolDiscoveryJob] Chain ${chainId}: discovered ${discovery.poolsFound} pools, ${discovery.poolsUpserted} new`);
        }
        
        // 2. Refresh TVL for all CANDIDATE + DEGRADED pools
        const tvlResult = await poolLiquidityService.refreshChain(chainId);
        console.log(`[PoolDiscoveryJob] Chain ${chainId}: TVL refreshed for ${tvlResult.poolsUpdated} pools`);
        
        // 3. Score all pools (this also sets status ACTIVE/DEGRADED/DISABLED)
        const scoring = await poolScoringService.scorePoolsForChain({ chainId });
        console.log(`[PoolDiscoveryJob] Chain ${chainId}: scored ${scoring.updated}, ACTIVE=${scoring.summary.ACTIVE}, DEGRADED=${scoring.summary.DEGRADED}, DISABLED=${scoring.summary.DISABLED}`);
        
        results.push({
          chainId,
          discovered: discovery.poolsUpserted,
          tvlRefreshed: tvlResult.poolsUpdated,
          scored: scoring.updated,
          statusSummary: scoring.summary,
        });
        
      } catch (e) {
        console.error(`[PoolDiscoveryJob] Error on chain ${chainId}:`, e);
      }
    }
    
    jobState.lastRunAt = Date.now();
    jobState.lastResult = results;
    
    if (jobHandle && jobState.intervalMs > 0) {
      jobState.nextRunAt = Date.now() + jobState.intervalMs;
    }
  } finally {
    jobState.running = false;
  }
}

/**
 * Start the discovery job
 */
export function startPoolDiscoveryJob(opts?: {
  enabled?: boolean;
  intervalMs?: number;
}): { running: boolean; stop: () => void } {
  const enabled = opts?.enabled ?? (process.env.ONCHAIN_V2_POOL_DISCOVERY_ENABLED === 'true');
  const intervalMs = opts?.intervalMs ?? parseInt(process.env.ONCHAIN_V2_POOL_DISCOVERY_INTERVAL_MS || '600000');
  
  jobState.enabled = enabled;
  jobState.intervalMs = intervalMs;
  
  if (!enabled) {
    console.log('[PoolDiscoveryJob] Disabled by config');
    return { running: false, stop: () => {} };
  }
  
  if (jobHandle) {
    console.log('[PoolDiscoveryJob] Already running');
    return { running: true, stop: stopPoolDiscoveryJob };
  }
  
  // Run first tick after short delay
  setTimeout(() => tick().catch(console.error), 5000);
  
  // Schedule recurring ticks
  jobHandle = setInterval(() => tick().catch(console.error), intervalMs);
  jobState.nextRunAt = Date.now() + intervalMs;
  
  console.log(`[PoolDiscoveryJob] Started (interval=${intervalMs}ms)`);
  
  return { running: true, stop: stopPoolDiscoveryJob };
}

/**
 * Stop the discovery job
 */
export function stopPoolDiscoveryJob(): void {
  if (jobHandle) {
    clearInterval(jobHandle);
    jobHandle = null;
    jobState.nextRunAt = null;
    console.log('[PoolDiscoveryJob] Stopped');
  }
}

/**
 * Force run a tick (manual trigger)
 */
export async function forceRunPoolDiscoveryJob(): Promise<JobState['lastResult']> {
  await tick();
  return jobState.lastResult;
}

/**
 * Get job status
 */
export function getPoolDiscoveryJobStatus(): JobState {
  return { ...jobState };
}

console.log('[OnChain V2] Pool Discovery Job v2 loaded');
