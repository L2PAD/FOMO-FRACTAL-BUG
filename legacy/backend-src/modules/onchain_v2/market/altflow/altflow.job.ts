/**
 * AltFlow Auto-Job v2
 * ====================
 * 
 * PHASE 3.5: Background job for computing Alt Flow rankings.
 * Now includes Flow Normalizer processing.
 */

import { altflowAggregateService, AltflowWindow } from './altflow.aggregate.service';
import { flowNormalizerService } from '../flow/flowNormalizer.service';
import { getActiveChainIds } from '../../chains/chain.constants';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const DEFAULT_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

// ═══════════════════════════════════════════════════════════════
// JOB STATE
// ═══════════════════════════════════════════════════════════════

interface JobResult {
  chainId: number;
  window: AltflowWindow;
  tokens: number;
  topAcc: string | null;
  topDist: string | null;
}

interface AltFlowJobState {
  enabled: boolean;
  intervalMs: number;
  running: boolean;
  tickCount: number;
  lastTickAt: number | null;
  lastError: string | null;
  lastFlowsProcessed: number;
  lastResult: JobResult[];
}

let timer: ReturnType<typeof setInterval> | null = null;
let state: AltFlowJobState = {
  enabled: false,
  intervalMs: DEFAULT_INTERVAL_MS,
  running: false,
  tickCount: 0,
  lastTickAt: null,
  lastError: null,
  lastFlowsProcessed: 0,
  lastResult: [],
};

// ═══════════════════════════════════════════════════════════════
// JOB LIFECYCLE
// ═══════════════════════════════════════════════════════════════

export function startAltFlowJob() {
  const enabled = process.env.ONCHAIN_V2_ALTFLOW_JOB_ENABLED !== 'false';
  
  if (!enabled) {
    console.log('[AltFlowJob] Disabled (ONCHAIN_V2_ALTFLOW_JOB_ENABLED = false)');
    state.enabled = false;
    return { enabled: false, getStatus: () => state };
  }
  
  const intervalMs = Number(process.env.ONCHAIN_V2_ALTFLOW_INTERVAL_MS) || DEFAULT_INTERVAL_MS;
  
  state.enabled = true;
  state.intervalMs = intervalMs;
  
  async function tick() {
    if (state.running) {
      console.log('[AltFlowJob] Skipping tick, previous still running');
      return;
    }
    
    state.running = true;
    state.tickCount++;
    
    try {
      console.log(`[AltFlowJob] Tick #${state.tickCount} starting...`);
      
      const results: JobResult[] = [];
      let totalFlows = 0;
      
      const chainIds = getActiveChainIds();
      
      for (const chainId of chainIds) {
        // Step 1: Process new DEX swaps into normalized flows
        // Use 7d window to catch older data on first runs
        const flowResult = await flowNormalizerService.processDexSwaps(chainId, 7 * 24 * 60 * 60 * 1000);
        totalFlows += flowResult.flows;
        console.log(`[AltFlowJob] Chain ${chainId}: processed ${flowResult.processed} swaps → ${flowResult.flows} flows`);
        
        // Step 2: Compute aggregations for both windows
        for (const window of ['24h', '7d'] as AltflowWindow[]) {
          const result = await altflowAggregateService.computeAndPersist(window, chainId);
          const formatted = altflowAggregateService.formatForApi(result);
          
          results.push({
            chainId,
            window,
            tokens: result.rows.length,
            topAcc: formatted.topAccumulation[0]?.symbol ?? null,
            topDist: formatted.topDistribution[0]?.symbol ?? null,
          });
          
          console.log(`[AltFlowJob] Chain ${chainId} ${window}: ${result.rows.length} tokens`);
        }
      }
      
      state.lastTickAt = Date.now();
      state.lastError = null;
      state.lastFlowsProcessed = totalFlows;
      state.lastResult = results;
      
      console.log(`[AltFlowJob] Tick #${state.tickCount} complete: ${totalFlows} flows processed`);
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : 'Unknown error';
      console.error(`[AltFlowJob] Tick #${state.tickCount} error:`, state.lastError);
    } finally {
      state.running = false;
    }
  }
  
  // Start interval
  timer = setInterval(tick, intervalMs);
  
  // Run initial tick after short delay
  setTimeout(tick, 15000);
  
  console.log(`[AltFlowJob] Started (interval=${intervalMs}ms)`);
  
  return {
    enabled: true,
    intervalMs,
    getStatus: () => ({ ...state }),
    stop: () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      state.enabled = false;
      console.log('[AltFlowJob] Stopped');
    },
    forceRun: async () => {
      await tick();
      return getAltFlowJobStatus();
    },
  };
}

export function getAltFlowJobStatus(): AltFlowJobState {
  return { ...state };
}

console.log('[AltFlow] Job v2 module loaded');
