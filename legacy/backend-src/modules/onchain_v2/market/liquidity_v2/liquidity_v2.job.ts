/**
 * OnChain V2 — LiquidityScore v2 Job
 * ====================================
 * 
 * BLOCK 7: Background job for computing LARE v2 on schedule.
 */

import { LiquidityV2Service } from './liquidity_v2.service.js';
import { runPerChain } from '../../system/runPerChain.js';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const DEFAULT_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

// ═══════════════════════════════════════════════════════════════
// JOB STATE
// ═══════════════════════════════════════════════════════════════

interface LiquidityV2JobState {
  enabled: boolean;
  intervalMs: number;
  running: boolean;
  tickCount: number;
  lastTickAt: number | null;
  lastError: string | null;
}

let timer: ReturnType<typeof setInterval> | null = null;
let state: LiquidityV2JobState = {
  enabled: false,
  intervalMs: DEFAULT_INTERVAL_MS,
  running: false,
  tickCount: 0,
  lastTickAt: null,
  lastError: null,
};

// ═══════════════════════════════════════════════════════════════
// JOB LIFECYCLE
// ═══════════════════════════════════════════════════════════════

export function startLiquidityV2Job(service: LiquidityV2Service) {
  const enabled = process.env.ONCHAIN_V2_LIQUIDITY_V2_ENABLED === 'true';
  
  if (!enabled) {
    console.log('[LiquidityV2Job] Disabled (ONCHAIN_V2_LIQUIDITY_V2_ENABLED != true)');
    state.enabled = false;
    return { enabled: false, getStatus: () => state };
  }
  
  const intervalMs = Number(process.env.ONCHAIN_V2_LIQUIDITY_V2_INTERVAL_MS) || DEFAULT_INTERVAL_MS;
  
  state.enabled = true;
  state.intervalMs = intervalMs;
  
  async function tick() {
    if (state.running) {
      console.log('[LiquidityV2Job] Skipping tick, previous still running');
      return;
    }
    
    state.running = true;
    state.tickCount++;
    
    try {
      console.log(`[LiquidityV2Job] Tick #${state.tickCount} starting...`);
      
      // Compute both windows for each enabled chain
      await runPerChain('LiquidityV2Job', async (chainId) => {
        const [out24, out7] = await Promise.all([
          service.computeAndStore('24h'),
          service.computeAndStore('7d'),
        ]);
        
        console.log(
          `[LiquidityV2Job] chain=${chainId}: ` +
          `24h=${out24.score.toFixed(1)}/${out24.regime}, ` +
          `7d=${out7.score.toFixed(1)}/${out7.regime}`
        );
      });
      
      state.lastTickAt = Date.now();
      state.lastError = null;
      
      console.log(`[LiquidityV2Job] Tick #${state.tickCount} complete`);
    } catch (error) {
      state.lastError = error instanceof Error ? error.message : 'Unknown error';
      console.error(`[LiquidityV2Job] Tick #${state.tickCount} error:`, state.lastError);
    } finally {
      state.running = false;
    }
  }
  
  // Start interval
  timer = setInterval(tick, intervalMs);
  
  // Run initial tick after short delay
  setTimeout(tick, 5000);
  
  console.log(`[LiquidityV2Job] Started (interval=${intervalMs}ms)`);
  
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
      console.log('[LiquidityV2Job] Stopped');
    },
  };
}

export function getLiquidityV2JobStatus(): LiquidityV2JobState {
  return { ...state };
}

console.log('[OnChain V2] LiquidityScore v2 job loaded');
