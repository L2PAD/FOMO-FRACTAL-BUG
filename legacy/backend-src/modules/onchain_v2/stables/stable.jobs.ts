/**
 * OnChain V2 — Stablecoin Background Jobs
 * =========================================
 * 
 * Background jobs for stablecoin mint/burn tracking:
 * - Indexer job: fetches mint/burn events from chain
 * - Aggregation job: computes supply change metrics
 */

import { stableMintBurnIndexer } from './stable_indexer.js';
import { stableAggregationService } from './stable_aggregation.service.js';
import { STABLE_MINTBURN_ENABLED } from './stable_registry.js';
import { runPerChain } from '../system/runPerChain.js';

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const INDEXER_INTERVAL_MS = 60_000;      // 1 minute
const AGGREGATION_INTERVAL_MS = 600_000; // 10 minutes

// ═══════════════════════════════════════════════════════════════
// JOB STATE
// ═══════════════════════════════════════════════════════════════

let indexerTimer: ReturnType<typeof setInterval> | null = null;
let aggregationTimer: ReturnType<typeof setInterval> | null = null;
let isRunning = false;

// ═══════════════════════════════════════════════════════════════
// INDEXER JOB
// ═══════════════════════════════════════════════════════════════

async function runIndexerTick(): Promise<void> {
  if (!STABLE_MINTBURN_ENABLED) return;
  
  try {
    console.log('[StableJob] Indexer tick starting...');
    const result = await stableMintBurnIndexer.indexAll();
    
    const totalInserted = result.results.reduce(
      (sum, r) => sum + (r.eventsInserted || 0),
      0
    );
    
    console.log(
      `[StableJob] Indexer tick complete: ${result.results.length} chains, ` +
      `${totalInserted} events inserted, ok=${result.ok}`
    );
  } catch (error) {
    console.error('[StableJob] Indexer tick error:', error);
  }
}

// ═══════════════════════════════════════════════════════════════
// AGGREGATION JOB
// ═══════════════════════════════════════════════════════════════

async function runAggregationTick(): Promise<void> {
  if (!STABLE_MINTBURN_ENABLED) return;
  
  try {
    console.log('[StableJob] Aggregation tick starting...');
    const nowTs = Date.now();
    
    await runPerChain('StableAggJob', async (chainId) => {
      const [agg24, agg7, agg30] = await Promise.all([
        stableAggregationService.computeAndUpsert('24h', nowTs),
        stableAggregationService.computeAndUpsert('7d', nowTs),
        stableAggregationService.computeAndUpsert('30d', nowTs),
      ]);
      
      console.log(
        `[StableJob] chain=${chainId}: ` +
        `24h=${agg24.score.value}, 7d=${agg7.score.value}, 30d=${agg30.score.value}`
      );
    });
    
    console.log('[StableJob] Aggregation tick complete');
  } catch (error) {
    console.error('[StableJob] Aggregation tick error:', error);
  }
}

// ═══════════════════════════════════════════════════════════════
// JOB LIFECYCLE
// ═══════════════════════════════════════════════════════════════

export function startStableJobs(): void {
  if (isRunning) {
    console.log('[StableJob] Jobs already running');
    return;
  }
  
  if (!STABLE_MINTBURN_ENABLED) {
    console.log('[StableJob] Stablecoin tracking disabled (ONCHAIN_V2_STABLE_MINTBURN_ENABLED=false)');
    return;
  }
  
  console.log('[StableJob] Starting stablecoin jobs...');
  isRunning = true;
  
  // Run initial tick after short delay
  setTimeout(() => {
    runIndexerTick();
    runAggregationTick();
  }, 5000);
  
  // Set up intervals
  indexerTimer = setInterval(runIndexerTick, INDEXER_INTERVAL_MS);
  aggregationTimer = setInterval(runAggregationTick, AGGREGATION_INTERVAL_MS);
  
  console.log(
    `[StableJob] Jobs started: indexer=${INDEXER_INTERVAL_MS}ms, ` +
    `aggregation=${AGGREGATION_INTERVAL_MS}ms`
  );
}

export function stopStableJobs(): void {
  if (!isRunning) {
    console.log('[StableJob] Jobs not running');
    return;
  }
  
  console.log('[StableJob] Stopping stablecoin jobs...');
  
  if (indexerTimer) {
    clearInterval(indexerTimer);
    indexerTimer = null;
  }
  
  if (aggregationTimer) {
    clearInterval(aggregationTimer);
    aggregationTimer = null;
  }
  
  isRunning = false;
  console.log('[StableJob] Jobs stopped');
}

export function isStableJobsRunning(): boolean {
  return isRunning;
}

console.log('[OnChain V2] Stablecoin jobs module loaded');
