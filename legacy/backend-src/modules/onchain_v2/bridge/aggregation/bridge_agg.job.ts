/**
 * OnChain V2 — Bridge Aggregation Job
 * =====================================
 * 
 * Scheduled job to compute bridge aggregates every 10 minutes.
 */

import { bridgeAggregationService } from './bridge_agg.service.js';
import { BRIDGE_ENABLED } from '../bridge.health.service.js';
import { runPerChain } from '../../system/runPerChain.js';

// ═══════════════════════════════════════════════════════════════
// JOB STATE
// ═══════════════════════════════════════════════════════════════

let timer: ReturnType<typeof setInterval> | null = null;
let running = false;
let tickCount = 0;
let lastTick = 0;
let lastError: string | null = null;

// ═══════════════════════════════════════════════════════════════
// JOB FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Start the aggregation job
 */
export function startBridgeAggJob(intervalMs = 10 * 60 * 1000): void {
  if (timer) {
    console.log('[BridgeAggJob] Already running');
    return;
  }
  
  if (!BRIDGE_ENABLED) {
    console.log('[BridgeAggJob] Bridge disabled, not starting');
    return;
  }
  
  console.log(`[BridgeAggJob] Starting with interval=${intervalMs}ms`);
  
  // Run function
  const run = async () => {
    if (running) return;
    running = true;
    lastTick = Date.now();
    
    try {
      await runPerChain('BridgeAggJob', async (chainId) => {
        await bridgeAggregationService.computeAndUpsert('24h');
        await bridgeAggregationService.computeAndUpsert('7d');
      });
      tickCount++;
      lastError = null;
      
      if (tickCount % 6 === 1) {
        console.log(`[BridgeAggJob] Tick #${tickCount} completed`);
      }
    } catch (e) {
      lastError = e instanceof Error ? e.message : 'Unknown error';
      console.error('[BridgeAggJob] Error:', lastError);
    } finally {
      running = false;
    }
  };
  
  // Start timer
  timer = setInterval(run, intervalMs);
  
  // Fire once at start (with delay to allow DB connection)
  setTimeout(run, 5000);
}

/**
 * Stop the aggregation job
 */
export function stopBridgeAggJob(): void {
  if (timer) {
    clearInterval(timer);
    timer = null;
    console.log('[BridgeAggJob] Stopped');
  }
}

/**
 * Get job status
 */
export function bridgeAggJobStatus(): {
  running: boolean;
  enabled: boolean;
  tickCount: number;
  lastTick: number;
  lastError: string | null;
} {
  return {
    running: !!timer,
    enabled: BRIDGE_ENABLED,
    tickCount,
    lastTick,
    lastError,
  };
}

/**
 * Force immediate tick
 */
export async function forceBridgeAggTick(): Promise<{
  ok: boolean;
  result24h?: any;
  result7d?: any;
  error?: string;
}> {
  if (running) {
    return { ok: false, error: 'Already running' };
  }
  
  running = true;
  lastTick = Date.now();
  
  try {
    const result24h = await bridgeAggregationService.computeAndUpsert('24h');
    const result7d = await bridgeAggregationService.computeAndUpsert('7d');
    tickCount++;
    lastError = null;
    return { ok: true, result24h, result7d };
  } catch (e) {
    lastError = e instanceof Error ? e.message : 'Unknown error';
    return { ok: false, error: lastError };
  } finally {
    running = false;
  }
}

console.log('[OnChain V2] Bridge Aggregation Job loaded');
