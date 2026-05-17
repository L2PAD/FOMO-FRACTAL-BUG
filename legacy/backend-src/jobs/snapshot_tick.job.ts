/**
 * OnChain V2 — Snapshot Tick Job
 * ================================
 * 
 * Periodic job to build snapshots from indexed data.
 * Runs every 5 minutes.
 */

import { snapshotBuilder } from '../modules/onchain_v2/snapshot-builder/service.js';

// ═══════════════════════════════════════════════════════════════
// JOB STATE
// ═══════════════════════════════════════════════════════════════

interface JobState {
  running: boolean;
  lastRunAt: number;
  lastResult: {
    ok: boolean;
    snapshots: number;
    symbols: string[];
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

// Symbols to build snapshots for
const SYMBOLS = ['ETH', 'BTC'];
const DEFAULT_WINDOW = '1h';
const CHAIN_ID = 1;

// ═══════════════════════════════════════════════════════════════
// JOB FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Run snapshot tick job
 */
export async function runSnapshotTickJob(): Promise<void> {
  if (state.running) {
    console.log('[SnapshotTickJob] Already running, skipping');
    return;
  }
  
  state.running = true;
  state.lastRunAt = Date.now();
  state.runCount++;
  
  const errors: string[] = [];
  const builtSymbols: string[] = [];
  
  try {
    for (const symbol of SYMBOLS) {
      try {
        const result = await snapshotBuilder.buildSnapshot(
          CHAIN_ID,
          symbol,
          DEFAULT_WINDOW as any,
          Date.now()
        );
        
        if (result.saved) {
          builtSymbols.push(symbol);
        }
      } catch (err) {
        const msg = `${symbol}: ${err instanceof Error ? err.message : 'Unknown error'}`;
        errors.push(msg);
        console.error(`[SnapshotTickJob] Error building ${symbol}:`, err);
      }
    }
    
    state.lastResult = {
      ok: errors.length === 0,
      snapshots: builtSymbols.length,
      symbols: builtSymbols,
      errors,
    };
    
    if (builtSymbols.length > 0 || errors.length > 0) {
      console.log(`[SnapshotTickJob] Built ${builtSymbols.length} snapshots, ${errors.length} errors`);
    }
    
  } catch (error) {
    console.error('[SnapshotTickJob] Fatal error:', error);
    state.errorCount++;
    state.lastResult = {
      ok: false,
      snapshots: 0,
      symbols: [],
      errors: [error instanceof Error ? error.message : 'Unknown error'],
    };
  } finally {
    state.running = false;
  }
}

/**
 * Get job status
 */
export function getSnapshotTickJobStatus(): {
  enabled: boolean;
  running: boolean;
  lastRunAt: number;
  lastResult: JobState['lastResult'];
  runCount: number;
  errorCount: number;
  symbols: string[];
  window: string;
} {
  return {
    enabled: isSnapshotTickJobEnabled(),
    running: state.running,
    lastRunAt: state.lastRunAt,
    lastResult: state.lastResult,
    runCount: state.runCount,
    errorCount: state.errorCount,
    symbols: SYMBOLS,
    window: DEFAULT_WINDOW,
  };
}

/**
 * Check if job is enabled
 */
export function isSnapshotTickJobEnabled(): boolean {
  return process.env.ONCHAIN_V2_ENABLED === 'true' && 
         process.env.SNAPSHOT_TICK_ENABLED !== 'false';
}

/**
 * Check if job is running
 */
export function isSnapshotTickJobRunning(): boolean {
  return state.running;
}

console.log('[OnChain V2] Snapshot Tick Job loaded');
