/**
 * HEAVY VERDICT JOB
 * =================
 * 
 * P3: Smart Caching Layer - Blocks 21, 24, 27
 * Background job that periodically warms up the heavy verdict cache.
 * 
 * Features:
 * - Precomputes verdicts for popular symbols (Block 27)
 * - Runs on configurable interval (default: 2 minutes)
 * - Skips symbols that already have fresh cache
 * - Parallel computation with configurable concurrency
 * - Auto-prunes dead entries after each run
 * - Smart TTL per horizon (Block 23)
 * - Staggered warmup to avoid CPU spikes (Block 27.3)
 * 
 * Symbols: BTC, ETH, SOL (expandable via Block 28)
 * Horizons: 1D, 7D, 30D
 */

import { HeavyVerdictStore, heavyVerdictStore } from '../runtime/heavy-verdict.store.js';
import { HeavyComputeService, heavyComputeService } from '../runtime/heavy-compute.service.js';
import { coinListService } from '../services/coin-list.service.js';
import { resourceMonitorService } from '../services/resource-monitor.service.js';
import type { ForecastHorizon } from '../runtime/heavy-verdict.types.js';

export type HeavyJobConfig = {
  enabled: boolean;
  intervalMs: number;           // Interval between runs (default: 2 minutes)
  symbols: string[];            // Core symbols (always processed)
  horizons: ForecastHorizon[];  // Horizons to warm up
  parallel: number;             // Max parallel computations
  staggerDelayMs: number;       // Block 27.3: Delay between tasks to avoid CPU spikes
  // Extended batch processing for Top 300
  extendedEnabled: boolean;     // Enable Top 300 expansion
  extendedBatchSize: number;    // Coins per batch in extended mode
  extendedBatchDelayMs: number; // Delay between extended batches
  extendedIntervalMs: number;   // How often to run extended analysis (default: 30 min)
  extendedTopN: number;         // How many top coins to analyze
};

// ENV-configurable to balance CPU vs data freshness
const envSymbols = process.env.HEAVY_VERDICT_SYMBOLS?.split(',').map(s => s.trim()).filter(Boolean);
const envInterval = process.env.HEAVY_VERDICT_INTERVAL_MS ? parseInt(process.env.HEAVY_VERDICT_INTERVAL_MS, 10) : undefined;
const envParallel = process.env.HEAVY_VERDICT_PARALLEL ? parseInt(process.env.HEAVY_VERDICT_PARALLEL, 10) : undefined;
const envStagger = process.env.HEAVY_VERDICT_STAGGER_MS ? parseInt(process.env.HEAVY_VERDICT_STAGGER_MS, 10) : undefined;
const envExtendedEnabled = process.env.HEAVY_VERDICT_EXTENDED === 'true' || process.env.HEAVY_VERDICT_EXTENDED === '1';
const envExtendedBatch = process.env.HEAVY_VERDICT_EXTENDED_BATCH ? parseInt(process.env.HEAVY_VERDICT_EXTENDED_BATCH, 10) : undefined;
const envExtendedDelay = process.env.HEAVY_VERDICT_EXTENDED_DELAY_MS ? parseInt(process.env.HEAVY_VERDICT_EXTENDED_DELAY_MS, 10) : undefined;
const envExtendedInterval = process.env.HEAVY_VERDICT_EXTENDED_INTERVAL_MS ? parseInt(process.env.HEAVY_VERDICT_EXTENDED_INTERVAL_MS, 10) : undefined;
const envExtendedTopN = process.env.HEAVY_VERDICT_EXTENDED_TOP_N ? parseInt(process.env.HEAVY_VERDICT_EXTENDED_TOP_N, 10) : undefined;

const DEFAULT_CONFIG: HeavyJobConfig = {
  enabled: true,
  intervalMs: envInterval || 2 * 60_000,
  symbols: envSymbols?.length ? envSymbols : ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'LINK', 'DOGE', 'MATIC'],
  horizons: ['1D', '7D', '30D'],
  parallel: envParallel || 3,
  staggerDelayMs: envStagger || 200,
  // Extended Top 300 analysis
  extendedEnabled: envExtendedEnabled,
  extendedBatchSize: envExtendedBatch || 5,
  extendedBatchDelayMs: envExtendedDelay || 10_000,
  extendedIntervalMs: envExtendedInterval || 30 * 60_000, // 30 min
  extendedTopN: envExtendedTopN || 300,
};

export class HeavyVerdictJob {
  private timer: NodeJS.Timeout | null = null;
  private extendedTimer: NodeJS.Timeout | null = null;
  private running = false;
  private extendedRunning = false;
  private lastRunAt: number = 0;
  private lastExtendedRunAt: number = 0;
  private runCount = 0;
  private extendedRunCount = 0;
  private extendedProcessed = 0;
  private extendedPaused = false;

  constructor(
    private cfg: HeavyJobConfig = DEFAULT_CONFIG,
    private store: HeavyVerdictStore = heavyVerdictStore,
    private compute: HeavyComputeService = heavyComputeService
  ) {}

  /**
   * Start the background job
   */
  start() {
    if (!this.cfg.enabled) {
      console.log('[HeavyVerdictJob] Disabled, not starting');
      return;
    }
    if (this.timer) {
      console.log('[HeavyVerdictJob] Already running');
      return;
    }

    console.log(`[HeavyVerdictJob] Starting with interval=${this.cfg.intervalMs}ms, symbols=${this.cfg.symbols.join(',')}`);

    // Immediate warmup (with delay to let server boot)
    setTimeout(() => {
      void this.tick();
    }, 5000);

    // Periodic warmup
    this.timer = setInterval(() => void this.tick(), this.cfg.intervalMs);

    // Start extended analysis if enabled
    if (this.cfg.extendedEnabled) {
      console.log(`[HeavyVerdictJob] Extended mode: Top ${this.cfg.extendedTopN} coins, batch=${this.cfg.extendedBatchSize}, interval=${this.cfg.extendedIntervalMs}ms`);
      // Start extended analysis after 2 minutes (let core symbols warm up first)
      setTimeout(() => {
        void this.extendedTick();
        this.extendedTimer = setInterval(() => void this.extendedTick(), this.cfg.extendedIntervalMs);
      }, 2 * 60_000);
    }
  }

  /**
   * Stop the background job
   */
  stop() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.extendedTimer) {
      clearInterval(this.extendedTimer);
      this.extendedTimer = null;
    }
    console.log('[HeavyVerdictJob] Stopped');
  }

  /**
   * Get job status
   */
  status() {
    return {
      enabled: this.cfg.enabled,
      running: this.running,
      lastRunAt: this.lastRunAt ? new Date(this.lastRunAt).toISOString() : null,
      runCount: this.runCount,
      config: this.cfg,
      extended: {
        enabled: this.cfg.extendedEnabled,
        running: this.extendedRunning,
        paused: this.extendedPaused,
        lastRunAt: this.lastExtendedRunAt ? new Date(this.lastExtendedRunAt).toISOString() : null,
        runCount: this.extendedRunCount,
        totalProcessed: this.extendedProcessed,
        resources: resourceMonitorService.getSnapshot(),
      },
    };
  }

  /**
   * Force a run now (for admin/testing)
   */
  async runNow() {
    await this.tick();
  }

  /**
   * Single tick of the job
   */
  private async tick() {
    if (this.running) {
      console.log('[HeavyVerdictJob] Already running, skipping tick');
      return;
    }
    
    this.running = true;
    this.lastRunAt = Date.now();
    this.runCount++;
    
    console.log(`[HeavyVerdictJob] Tick #${this.runCount} starting...`);

    try {
      const tasks: Array<{ symbol: string; horizon: ForecastHorizon }> = [];
      
      // Build list of tasks (skip if fresh cache exists)
      for (const symbol of this.cfg.symbols) {
        for (const horizon of this.cfg.horizons) {
          const key = this.store.makeKey({ symbol, horizon });
          
          // Skip if we have fresh cache
          if (this.store.getFresh(key)) {
            continue;
          }
          
          tasks.push({ symbol, horizon });
        }
      }

      if (tasks.length === 0) {
        console.log('[HeavyVerdictJob] All entries fresh, nothing to do');
        return;
      }

      console.log(`[HeavyVerdictJob] ${tasks.length} tasks to compute`);

      // Run tasks with limited parallelism and staggering (Block 27.3)
      let idx = 0;
      let computed = 0;
      let errors = 0;

      const worker = async () => {
        while (idx < tasks.length) {
          const taskIdx = idx++;
          const { symbol, horizon } = tasks[taskIdx];
          const key = this.store.makeKey({ symbol, horizon });

          try {
            const payload = await this.compute.compute(symbol, horizon);
            // Block 23: Use horizon-aware TTL
            this.store.setWithHorizon(key, payload, horizon);
            computed++;
            console.log(`[HeavyVerdictJob] Warmed ${symbol}/${horizon} in ${payload.computeMs}ms`);
            
            // Block 27.3: Stagger to avoid CPU spikes
            if (this.cfg.staggerDelayMs > 0) {
              await new Promise(r => setTimeout(r, this.cfg.staggerDelayMs));
            }
          } catch (e: any) {
            console.error(`[HeavyVerdictJob] Error computing ${symbol}/${horizon}: ${e.message}`);
            errors++;
          }
        }
      };

      // Start parallel workers
      const workers = Array.from(
        { length: Math.min(this.cfg.parallel, tasks.length) },
        () => worker()
      );
      
      await Promise.all(workers);

      // Prune dead entries
      const pruned = this.store.prune();

      console.log(`[HeavyVerdictJob] Tick #${this.runCount} done: computed=${computed}, errors=${errors}, pruned=${pruned}`);
      
    } catch (e: any) {
      console.error(`[HeavyVerdictJob] Tick error: ${e.message}`);
    } finally {
      this.running = false;
    }
  }

  /**
   * Extended tick — processes Top 300 coins in small batches with CPU monitoring.
   * Uses CoinGecko for coin list. Stops if CPU/MEM exceeds thresholds.
   */
  private async extendedTick() {
    if (this.extendedRunning) {
      console.log('[HeavyVerdictJob:Extended] Already running, skipping');
      return;
    }

    // Pre-check resources
    if (!resourceMonitorService.checkAndWarn()) {
      this.extendedPaused = true;
      console.log('[HeavyVerdictJob:Extended] Skipping due to resource constraints');
      return;
    }
    this.extendedPaused = false;

    this.extendedRunning = true;
    this.lastExtendedRunAt = Date.now();
    this.extendedRunCount++;

    try {
      // Fetch top coins (cached, refreshes every 6h)
      const allCoins = await coinListService.getTopCoins(this.cfg.extendedTopN);
      
      // Exclude core symbols (already handled by main tick)
      const coreSet = new Set(this.cfg.symbols.map(s => s.toUpperCase()));
      const extendedCoins = allCoins.filter(s => !coreSet.has(s.toUpperCase()));

      console.log(`[HeavyVerdictJob:Extended] Tick #${this.extendedRunCount}: Processing ${extendedCoins.length} extended coins in batches of ${this.cfg.extendedBatchSize}`);

      let processed = 0;
      let errors = 0;
      let stopped = false;

      // Process in batches
      for (let i = 0; i < extendedCoins.length; i += this.cfg.extendedBatchSize) {
        // Check resources before each batch
        if (!resourceMonitorService.checkAndWarn()) {
          console.log(`[HeavyVerdictJob:Extended] PAUSING at batch ${Math.floor(i / this.cfg.extendedBatchSize)} due to resource limits (processed=${processed})`);
          this.extendedPaused = true;
          stopped = true;
          break;
        }

        const batch = extendedCoins.slice(i, i + this.cfg.extendedBatchSize);

        // Process batch sequentially (1 parallel) to minimize CPU impact
        for (const symbol of batch) {
          try {
            // Only compute 30D horizon for extended coins (lighter weight)
            const key = this.store.makeKey({ symbol, horizon: '30D' });
            if (this.store.getFresh(key)) {
              continue; // Skip if fresh
            }

            const payload = await this.compute.compute(symbol, '30D');
            this.store.setWithHorizon(key, payload, '30D');
            processed++;
            this.extendedProcessed++;

            // Stagger within batch
            await new Promise(r => setTimeout(r, this.cfg.staggerDelayMs * 2));
          } catch (e: any) {
            errors++;
            // Don't log every error for 300 coins
            if (errors <= 5) {
              console.warn(`[HeavyVerdictJob:Extended] ${symbol}/30D error: ${e.message}`);
            }
          }
        }

        // Delay between batches
        if (i + this.cfg.extendedBatchSize < extendedCoins.length) {
          await new Promise(r => setTimeout(r, this.cfg.extendedBatchDelayMs));
        }
      }

      const snap = resourceMonitorService.getSnapshot();
      console.log(`[HeavyVerdictJob:Extended] Tick #${this.extendedRunCount} done: processed=${processed}, errors=${errors}, stopped=${stopped}, CPU=${snap.cpuPercent}%, MEM=${snap.memUsedPercent}%`);

    } catch (e: any) {
      console.error(`[HeavyVerdictJob:Extended] Tick error: ${e.message}`);
    } finally {
      this.extendedRunning = false;
    }
  }
}

// Singleton instance
export const heavyVerdictJob = new HeavyVerdictJob();

console.log('[HeavyVerdictJob] Module loaded');
