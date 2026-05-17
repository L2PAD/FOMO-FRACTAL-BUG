/**
 * OnChain V2 — Rolling & Drift Auto Job
 * =======================================
 * 
 * Production-safe governance layer auto-compute.
 * 
 * Rules:
 * - Rolling: every 30 min OR when snapshotCount >= +3
 * - Drift: ONLY after rolling, not more than 1x per 30 min
 */

import { rollingStatsService } from '../modules/onchain_v2/governance/rolling.service.js';
import { driftService } from '../modules/onchain_v2/governance/drift.service.js';
import { OnchainObservationModel } from '../modules/onchain_v2/core/persistence/models.js';

// ═══════════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════════

const SYMBOLS = ['ETH', 'BTC'];
const ROLLING_MIN_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes
const SNAPSHOT_DELTA_THRESHOLD = 3; // Compute if +3 snapshots
const CHAIN_ID = 1;

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface SymbolState {
  lastRollingAt: number;
  lastDriftAt: number;
  lastSnapshotCount: number;
  lastRollingResult: any;
  lastDriftResult: any;
}

interface JobState {
  running: boolean;
  states: Map<string, SymbolState>;
  runCount: number;
  lastRunAt: number;
}

const state: JobState = {
  running: false,
  states: new Map(),
  runCount: 0,
  lastRunAt: 0,
};

// Initialize state for each symbol
for (const symbol of SYMBOLS) {
  state.states.set(symbol, {
    lastRollingAt: 0,
    lastDriftAt: 0,
    lastSnapshotCount: 0,
    lastRollingResult: null,
    lastDriftResult: null,
  });
}

// ═══════════════════════════════════════════════════════════════
// JOB FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Run rolling & drift job
 */
export async function runRollingDriftJob(): Promise<void> {
  if (state.running) {
    console.log('[RollingDriftJob] Already running, skipping');
    return;
  }
  
  state.running = true;
  state.lastRunAt = Date.now();
  state.runCount++;
  
  try {
    for (const symbol of SYMBOLS) {
      await processSymbol(symbol);
    }
  } catch (error) {
    console.error('[RollingDriftJob] Fatal error:', error);
  } finally {
    state.running = false;
  }
}

/**
 * Process a single symbol
 */
async function processSymbol(symbol: string): Promise<void> {
  const symbolState = state.states.get(symbol)!;
  const now = Date.now();
  
  try {
    // Get current snapshot count
    const currentCount = await OnchainObservationModel.countDocuments({ symbol });
    const snapshotDelta = currentCount - symbolState.lastSnapshotCount;
    const timeSinceLastRolling = now - symbolState.lastRollingAt;
    
    // Decide if we should compute rolling
    const shouldComputeRolling = 
      timeSinceLastRolling >= ROLLING_MIN_INTERVAL_MS ||
      (snapshotDelta >= SNAPSHOT_DELTA_THRESHOLD && timeSinceLastRolling >= 5 * 60 * 1000);
    
    if (!shouldComputeRolling) {
      return;
    }
    
    console.log(`[RollingDriftJob] Computing rolling for ${symbol} (delta=${snapshotDelta}, time=${Math.round(timeSinceLastRolling/60000)}min)`);
    
    // Compute rolling
    const rollingResult = await rollingStatsService.computeRolling({
      symbol,
      window: '30d',
      chainId: CHAIN_ID,
    });
    
    symbolState.lastRollingAt = now;
    symbolState.lastSnapshotCount = currentCount;
    symbolState.lastRollingResult = {
      sampleCount: rollingResult?.sampleCount ?? 0,
      avgScore: rollingResult?.score?.avg ?? 0,
      computedAt: now,
    };
    
    console.log(`[RollingDriftJob] Rolling computed for ${symbol}: samples=${rollingResult?.sampleCount ?? 0}`);
    
    // Compute drift (only after rolling, respecting min interval)
    const timeSinceLastDrift = now - symbolState.lastDriftAt;
    if (timeSinceLastDrift >= ROLLING_MIN_INTERVAL_MS) {
      const driftResult = await driftService.calculateDrift({
        symbol,
        metric: 'score',
        window: '30d',
      });
      
      symbolState.lastDriftAt = now;
      symbolState.lastDriftResult = {
        psi: driftResult.psi,
        level: driftResult.level,
        hasBaseline: driftResult.hasBaseline,
        checkedAt: now,
      };
      
      console.log(`[RollingDriftJob] Drift computed for ${symbol}: psi=${driftResult.psi.toFixed(3)}, level=${driftResult.level}`);
    }
    
  } catch (error) {
    console.error(`[RollingDriftJob] Error processing ${symbol}:`, error);
  }
}

/**
 * Get job status
 */
export function getRollingDriftJobStatus(): {
  enabled: boolean;
  running: boolean;
  lastRunAt: number;
  runCount: number;
  symbols: Array<{
    symbol: string;
    lastRollingAt: number;
    lastDriftAt: number;
    lastSnapshotCount: number;
    lastRollingResult: any;
    lastDriftResult: any;
  }>;
  config: {
    minIntervalMs: number;
    snapshotDeltaThreshold: number;
  };
} {
  const symbols = [];
  for (const [symbol, s] of state.states.entries()) {
    symbols.push({
      symbol,
      lastRollingAt: s.lastRollingAt,
      lastDriftAt: s.lastDriftAt,
      lastSnapshotCount: s.lastSnapshotCount,
      lastRollingResult: s.lastRollingResult,
      lastDriftResult: s.lastDriftResult,
    });
  }
  
  return {
    enabled: isRollingDriftJobEnabled(),
    running: state.running,
    lastRunAt: state.lastRunAt,
    runCount: state.runCount,
    symbols,
    config: {
      minIntervalMs: ROLLING_MIN_INTERVAL_MS,
      snapshotDeltaThreshold: SNAPSHOT_DELTA_THRESHOLD,
    },
  };
}

/**
 * Check if job is enabled
 */
export function isRollingDriftJobEnabled(): boolean {
  return process.env.ONCHAIN_V2_ENABLED === 'true' && 
         process.env.ROLLING_DRIFT_ENABLED !== 'false';
}

/**
 * Check if job is running
 */
export function isRollingDriftJobRunning(): boolean {
  return state.running;
}

/**
 * Force compute for a symbol (manual trigger)
 */
export async function forceComputeRollingDrift(symbol: string): Promise<{
  rolling: any;
  drift: any;
}> {
  const symbolState = state.states.get(symbol);
  if (!symbolState) {
    throw new Error(`Unknown symbol: ${symbol}`);
  }
  
  const now = Date.now();
  
  // Force rolling
  const rollingResult = await rollingStatsService.computeRolling({
    symbol,
    window: '30d',
    chainId: CHAIN_ID,
  });
  
  symbolState.lastRollingAt = now;
  symbolState.lastSnapshotCount = await OnchainObservationModel.countDocuments({ symbol });
  symbolState.lastRollingResult = {
    sampleCount: rollingResult?.sampleCount ?? 0,
    avgScore: rollingResult?.score?.avg ?? 0,
    computedAt: now,
  };
  
  // Force drift
  const driftResult = await driftService.calculateDrift({
    symbol,
    metric: 'score',
    window: '30d',
  });
  
  symbolState.lastDriftAt = now;
  symbolState.lastDriftResult = {
    psi: driftResult.psi,
    level: driftResult.level,
    hasBaseline: driftResult.hasBaseline,
    checkedAt: now,
  };
  
  return {
    rolling: symbolState.lastRollingResult,
    drift: symbolState.lastDriftResult,
  };
}

console.log('[OnChain V2] Rolling & Drift Job loaded');
