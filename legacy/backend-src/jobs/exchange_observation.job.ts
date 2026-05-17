/**
 * Exchange Observation Collection Job — V5 (WS-First Multi-Provider)
 * 
 * Uses WebSocket-first architecture:
 *   Primary: Binance WS, Bybit WS (perp real-time)
 *   Secondary: REST providers (Hyperliquid, Coinbase, CoinGecko)
 *   Tertiary: Mock + Last Good Tick Cache
 * 
 * Priority-based collection with batch processing:
 *   P1: Top alpha symbols (by alphaScore)
 *   P2: Top main symbols (by volume)
 * 
 * Concurrency guard: batchSize=20, sleep 400ms between batches, jitter between requests.
 * 
 * Config via ENV:
 *   EXCHANGE_OBS_ENABLED=true
 *   EXCHANGE_OBS_LIMIT_SPOT=200
 *   EXCHANGE_OBS_LIMIT_ALPHA=200
 *   EXCHANGE_OBS_INTERVAL_MS=400
 *   EXCHANGE_OBS_BATCH_SIZE=20
 *   EXCHANGE_OBS_TTL_MIN=10
 */

import * as observationService from '../modules/exchange/observation/observation.service.js';
import { getSpotSymbols, getAlphaSymbols, getLastObservationTs } from '../modules/exchange/data/universe_loader.service.js';
import { WsMarketIngestionService } from '../modules/exchange/ingestion/services/ws-market-ingestion.service.js';
import { aggregatedTickToObservationInput } from '../modules/exchange/ingestion/adapters/observation.adapter.js';
import { ALPHA_SYMBOLS, SECONDARY_SYMBOLS } from '../modules/exchange/ingestion/ws/symbol-groups.js';

// Configuration from ENV
const ENABLED = (process.env.EXCHANGE_OBS_ENABLED || 'true').toLowerCase() === 'true';
const LIMIT_SPOT = parseInt(process.env.EXCHANGE_OBS_LIMIT_SPOT || '200', 10);
const LIMIT_ALPHA = parseInt(process.env.EXCHANGE_OBS_LIMIT_ALPHA || '200', 10);
const INTERVAL_MS = parseInt(process.env.EXCHANGE_OBS_INTERVAL_MS || '400', 10);
const BATCH_SIZE = parseInt(process.env.EXCHANGE_OBS_BATCH_SIZE || '20', 10);
const TTL_MIN = parseInt(process.env.EXCHANGE_OBS_TTL_MIN || '10', 10);
const CYCLE_INTERVAL_MS = 10 * 1000; // TEMPORARILY 10 seconds for initial data accumulation (was: 5min)
const MAX_RETRIES = 1;

let isRunning = false;
let intervalId: NodeJS.Timeout | null = null;
let lastRun: Date | null = null;
let stats = { success: 0, skipped: 0, errors: 0, lastCycleMs: 0, totalCycles: 0 };

// CRITICAL FIX: Reset state on module reload (hot reload protection)
if (intervalId) {
  clearInterval(intervalId);
  intervalId = null;
}
isRunning = false;

// Initialize WS-First Multi-Provider Ingestion Service
const ingestionService = new WsMarketIngestionService();

function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

/**
 * Add random jitter to sleep duration (user requested)
 */
function jitter(baseMs: number): number {
  return baseMs + Math.random() * 500; // 0-500ms random jitter
}

/**
 * Collect observation for a single symbol using WS-First Multi-Provider Ingestion
 */
async function collectForSymbol(symbol: string): Promise<'success' | 'skip' | 'error'> {
  // TTL check: skip if fresh observation exists
  const lastTs = await getLastObservationTs(symbol);
  if (lastTs) {
    const ageMin = (Date.now() - lastTs) / 60000;
    console.log(`[TTL CHECK] ${symbol} lastTs=${lastTs} ageMin=${ageMin.toFixed(2)} TTL_MIN=${TTL_MIN} skip=${ageMin < TTL_MIN}`);
    if (ageMin < TTL_MIN) {
      console.log(`[TTL SKIP] ${symbol} too fresh (${ageMin.toFixed(2)} < ${TTL_MIN} min)`);
      return 'skip';
    }
  } else {
    console.log(`[TTL CHECK] ${symbol} no lastTs, collecting...`);
  }

  let retries = 0;
  while (retries <= MAX_RETRIES) {
    try {
      console.log(`[OBS] ${symbol} stage=before_tick`);
      
      // Use WS-First Multi-Provider Ingestion Service
      const aggregatedTick = await ingestionService.collect(symbol);
      
      if (!aggregatedTick) {
        console.log(`[OBS] ${symbol} stage=no_tick (WS cache empty, REST unavailable)`);
        retries++;
        if (retries <= MAX_RETRIES) await sleep(jitter(500));
        continue;
      }

      console.log(`[OBS] ${symbol} stage=tick_ok quality=${aggregatedTick.quality} price=${aggregatedTick.price}`);

      // Convert to observation input format
      const input = aggregatedTickToObservationInput(aggregatedTick);
      
      // Write to MongoDB via existing observation service
      let observation;
      try {
        observation = await observationService.createObservationWithIndicators({
          ...input,
          source: 'ws_multi_provider_v5',
        });
      } catch (writeError: any) {
        console.error(`[OBS] ${symbol} stage=write_exception`, writeError.message);
        return 'error';
      }

      if (!observation) {
        console.log(`[OBS] ${symbol} stage=save_null (rate limited or skipped)`);
        return 'skip';
      }

      console.log(`[OBS] ${symbol} stage=saved id=${observation.id}`);
      return 'success';
    } catch (error: any) {
      console.error(`[OBS] ${symbol} stage=collect_error attempt=${retries + 1}:`, error.message);
      retries++;
      if (retries <= MAX_RETRIES) await sleep(jitter(1000));
    }
  }

  return 'error';
}

/**
 * Process symbols in batches with sleep between batches
 */
async function processBatch(symbols: string[]): Promise<{ success: number; skip: number; error: number }> {
  let success = 0, skip = 0, error = 0;

  for (let i = 0; i < symbols.length; i += BATCH_SIZE) {
    const batch = symbols.slice(i, i + BATCH_SIZE);

    // Process batch sequentially (respect rate limits)
    for (const symbol of batch) {
      const result = await collectForSymbol(symbol);
      if (result === 'success') success++;
      else if (result === 'skip') skip++;
      else error++;

      // Throttle between symbols within batch (with jitter)
      if (result !== 'skip') {
        await sleep(jitter(INTERVAL_MS));
      }
    }

    // Sleep between batches (guard)
    if (i + BATCH_SIZE < symbols.length) {
      await sleep(400);
    }
  }

  return { success, skip, error };
}

/**
 * Main collection cycle — priority-based
 */
async function runCycle(): Promise<void> {
  console.log(`[ExchangeObsJob] runCycle() called. isRunning=${isRunning}, ENABLED=${ENABLED}`);
  
  // TEMPORARY FIX: Comment out isRunning check to force execution
  // if (isRunning) {
  //   console.log('[ExchangeObsJob] ❌ runCycle SKIPPED - already running!');
  //   return;
  // }
  
  if (!ENABLED) {
    console.log('[ExchangeObsJob] ❌ runCycle SKIPPED - not enabled!');
    return;
  }

  isRunning = true;
  console.log('[ExchangeObsJob] ✅ runCycle STARTED');
  const startTime = Date.now();

  try {
    // CRITICAL: Only collect symbols with active WS subscriptions
    // Principle: "Only trade what you can observe well"
    const symbols = [...ALPHA_SYMBOLS, ...SECONDARY_SYMBOLS];
    
    console.log(`[ExchangeObsJob] V5 WS-First Cycle: ${symbols.length} symbols (WS-subscribed only)`);
    console.log(`[ExchangeObsJob] Symbols: ${symbols.join(', ')}`);

    // Process all symbols
    const results = await processBatch(symbols);
    console.log(`[ExchangeObsJob] Results: ${results.success} collected, ${results.skip} skipped, ${results.error} errors`);

    stats.success += results.success;
    stats.skipped += results.skip;
    stats.errors += results.error;
    stats.lastCycleMs = Date.now() - startTime;
    stats.totalCycles++;

    console.log(`[ExchangeObsJob] V5 Cycle done: ${results.success}/${symbols.length} collected, ${results.skip} skipped, ${results.error} errors, ${stats.lastCycleMs}ms`);

  } catch (error: any) {
    console.error('[ExchangeObsJob] Cycle failed:', error.message);
  } finally {
    isRunning = false;
    lastRun = new Date();
  }
}

/**
 * Start the collection job
 */
export function startExchangeObservationJob(): { success: boolean; message: string } {
  if (!ENABLED) {
    return { success: false, message: 'EXCHANGE_OBS_ENABLED=false' };
  }
  if (intervalId) {
    return { success: false, message: 'Job already running' };
  }

  console.log(`[ExchangeObsJob] Starting V5 WS-First (spot=${LIMIT_SPOT}, alpha=${LIMIT_ALPHA}, batch=${BATCH_SIZE}, interval=${INTERVAL_MS}ms, ttl=${TTL_MIN}min)`);

  // Run immediately (async, don't await - let it run in background)
  console.log('[ExchangeObsJob] Triggering first runCycle() in background...');
  runCycle().catch(err => console.error('[ExchangeObsJob] First runCycle failed:', err));

  // Schedule periodic runs
  intervalId = setInterval(() => {
    runCycle().catch(err => console.error('[ExchangeObsJob] Scheduled runCycle failed:', err));
  }, CYCLE_INTERVAL_MS);
  console.log(`[ExchangeObsJob] Scheduled periodic runs every ${CYCLE_INTERVAL_MS}ms`);

  return { success: true, message: `Started V5 WS-First: spot=${LIMIT_SPOT}, alpha=${LIMIT_ALPHA}, batch=${BATCH_SIZE}` };
}

/**
 * Stop the collection job
 */
export function stopExchangeObservationJob(): { success: boolean; message: string } {
  if (!intervalId) {
    return { success: false, message: 'Job not running' };
  }

  clearInterval(intervalId);
  intervalId = null;
  console.log('[ExchangeObsJob] Job stopped');
  return { success: true, message: 'Job stopped' };
}

/**
 * Get job status
 */
export function getExchangeObservationJobStatus(): {
  running: boolean;
  enabled: boolean;
  lastRun: Date | null;
  stats: typeof stats;
  config: { limitSpot: number; limitAlpha: number; intervalMs: number; batchSize: number; ttlMin: number };
} {
  return {
    running: intervalId !== null,
    enabled: ENABLED,
    lastRun,
    stats,
    config: { limitSpot: LIMIT_SPOT, limitAlpha: LIMIT_ALPHA, intervalMs: INTERVAL_MS, batchSize: BATCH_SIZE, ttlMin: TTL_MIN },
  };
}

/**
 * Trigger manual run
 */
export async function triggerManualCollection(): Promise<{
  success: boolean;
  collected: number;
  errors: number;
}> {
  if (isRunning) {
    return { success: false, collected: 0, errors: 0 };
  }

  const beforeSuccess = stats.success;
  const beforeErrors = stats.errors;

  await runCycle();

  return {
    success: true,
    collected: stats.success - beforeSuccess,
    errors: stats.errors - beforeErrors,
  };
}

console.log('[ExchangeObsJob] V5 WS-First Module loaded (WebSocket-Priority Ingestion System)');
