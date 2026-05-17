/**
 * Sentiment Dataset Finalize Job
 * ================================
 * 
 * BLOCK 6: Periodic job to finalize matured aggregate snapshots into samples.
 * 
 * Flow:
 * 1. Acquire distributed lock
 * 2. Find candidate aggregates (window closed + grace period)
 * 3. Call finalizeSample() for each
 * 4. Release lock
 * 
 * Job is idempotent — can run frequently without creating duplicates.
 * 
 * ENV Configuration:
 * - SENTIMENT_DATASET_ENABLED=true
 * - SENTIMENT_DATASET_FINALIZE_INTERVAL_MS=21600000 (6h)
 * - SENTIMENT_DATASET_GRACE_MS=7200000 (2h)
 * - SENTIMENT_DATASET_MAX_BATCH=200
 * - SENTIMENT_DATASET_LOCK_TTL_MS=300000 (5min)
 */

import { SentimentDatasetAccumulator, FinalizeResult } from './sentiment-dataset.accumulator.js';
import { SystemLocksService } from '../../system/locks/system-locks.service.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';
import { SentimentWindow } from './sentiment-dir-sample.model.js';
import { horizonDays } from './sentiment-dataset-labels.js';
import { updateWorkerStatus, isWorkerPaused } from '../ops/sentiment-ops.routes.js';

// Lock key for distributed locking
const LOCK_KEY = 'sent:dataset_finalize';

export interface FinalizeJobConfig {
  enabled: boolean;
  intervalMs: number;
  lockTtlMs: number;
  graceMs: number;
  maxBatch: number;
}

export interface JobRunStats {
  startedAt: Date;
  finishedAt: Date;
  processed: number;
  counters: Record<string, number>;
  reasons: Record<string, number>;
  error?: string;
}

export class SentimentDatasetFinalizeJob {
  private timer: NodeJS.Timeout | null = null;
  private lastRunStats: JobRunStats | null = null;
  private isRunning = false;

  constructor(
    private readonly accumulator: SentimentDatasetAccumulator,
    private readonly locks: SystemLocksService,
    private readonly cfg: FinalizeJobConfig
  ) {}

  /**
   * Start the job (interval-based)
   */
  start(): void {
    if (!this.cfg.enabled) {
      console.log('[SentimentDatasetJob] Disabled by config');
      return;
    }

    if (this.timer) {
      console.log('[SentimentDatasetJob] Already running');
      return;
    }

    console.log(`[SentimentDatasetJob] Starting with interval ${this.cfg.intervalMs}ms`);

    // Run immediately once
    void this.tick();

    // Then schedule interval
    this.timer = setInterval(() => void this.tick(), this.cfg.intervalMs);
  }

  /**
   * Stop the job
   */
  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
      console.log('[SentimentDatasetJob] Stopped');
    }
  }

  /**
   * Get job status for admin API
   */
  getStatus(): {
    enabled: boolean;
    running: boolean;
    intervalMs: number;
    graceMs: number;
    maxBatch: number;
    lastRunStats: JobRunStats | null;
  } {
    return {
      enabled: this.cfg.enabled,
      running: !!this.timer,
      intervalMs: this.cfg.intervalMs,
      graceMs: this.cfg.graceMs,
      maxBatch: this.cfg.maxBatch,
      lastRunStats: this.lastRunStats,
    };
  }

  /**
   * Manual trigger (for admin API)
   */
  async triggerManual(mode: 'live' | 'backfill' = 'live'): Promise<JobRunStats | null> {
    if (this.isRunning) {
      return null;
    }
    await this.tick(mode);
    return this.lastRunStats;
  }

  /**
   * Compute cutoff date for a window (aggregates older than this are candidates)
   */
  private maturedCutoff(window: SentimentWindow): Date {
    const days = horizonDays(window);
    return new Date(Date.now() - (days * 86400_000 + this.cfg.graceMs));
  }

  /**
   * Fetch candidate aggregates for a specific window
   */
  private async fetchCandidates(
    window: SentimentWindow,
    limit: number
  ): Promise<Array<{ symbol: string; window: SentimentWindow; asOf: Date }>> {
    const cutoff = this.maturedCutoff(window);

    // Map window for query (aggregates use 24H, not 1D)
    const aggWindow = window === '24H' ? '24H' : window;

    const docs = await SentimentAggregateModel.find(
      { 
        window: aggWindow, 
        asOf: { $lte: cutoff },
        eventsCount: { $gt: 0 }, // Only non-empty aggregates
      },
      { symbol: 1, window: 1, asOf: 1, _id: 0 }
    )
      .sort({ asOf: 1 }) // Oldest first
      .limit(limit)
      .lean();

    return docs.map(d => ({
      symbol: d.symbol,
      window: window, // Use our normalized window
      asOf: d.asOf,
    }));
  }

  /**
   * Single tick of the job
   */
  private async tick(mode: 'live' | 'backfill' = 'live'): Promise<void> {
    if (this.isRunning) {
      console.log('[SentimentDatasetJob] Tick skipped — already running');
      return;
    }

    // Acquire lock
    const handle = await this.locks.acquire(LOCK_KEY, this.cfg.lockTtlMs);
    if (!handle) {
      console.log('[SentimentDatasetJob] Tick skipped — lock held by another instance');
      return;
    }

    this.isRunning = true;
    const startedAt = new Date();
    const counters: Record<string, number> = {
      CREATED: 0,
      SKIPPED: 0,
      RETRY: 0,
      FAILED: 0,
    };
    const reasons: Record<string, number> = {};

    try {
      // Distribute batch across windows
      const perWindow = Math.max(1, Math.floor(this.cfg.maxBatch / 3));
      const windows: SentimentWindow[] = ['24H', '7D', '30D'];

      // In backfill mode, fetch more candidates and use different cutoff
      const candidateLimit = mode === 'backfill' ? perWindow * 5 : perWindow;

      // Fetch candidates for all windows
      const allCandidates = (
        await Promise.all(windows.map(w => 
          mode === 'backfill' 
            ? this.fetchBackfillCandidates(w, candidateLimit)
            : this.fetchCandidates(w, candidateLimit)
        ))
      ).flat();

      console.log(`[SentimentDatasetJob] Processing ${allCandidates.length} candidates (mode: ${mode})`);

      // Process each candidate
      for (const candidate of allCandidates) {
        const result: FinalizeResult = await this.accumulator.finalizeSample({
          symbol: candidate.symbol,
          window: candidate.window,
          asOf: candidate.asOf,
          mode,
        });

        counters[result.status] = (counters[result.status] ?? 0) + 1;

        if (result.reason) {
          reasons[result.reason] = (reasons[result.reason] ?? 0) + 1;
        }
      }

      this.lastRunStats = {
        startedAt,
        finishedAt: new Date(),
        processed: allCandidates.length,
        counters,
        reasons,
      };

      console.log(`[SentimentDatasetJob] Tick complete:`, this.lastRunStats.counters);

    } catch (err: any) {
      console.error('[SentimentDatasetJob] Tick error:', err);

      this.lastRunStats = {
        startedAt,
        finishedAt: new Date(),
        processed: 0,
        counters,
        reasons,
        error: err?.message ?? String(err),
      };
    } finally {
      this.isRunning = false;
      await this.locks.release(handle);
    }
  }

  /**
   * Fetch candidates for backfill mode (all historical aggregates with closed windows)
   */
  private async fetchBackfillCandidates(
    window: SentimentWindow,
    limit: number
  ): Promise<Array<{ symbol: string; window: SentimentWindow; asOf: Date }>> {
    const days = horizonDays(window);
    // For backfill, cutoff is just when window would have closed (no grace period)
    const cutoff = new Date(Date.now() - days * 86400_000);

    const aggWindow = window === '24H' ? '24H' : window;

    const docs = await SentimentAggregateModel.find(
      { 
        window: aggWindow, 
        asOf: { $lte: cutoff },
        eventsCount: { $gt: 0 },
      },
      { symbol: 1, window: 1, asOf: 1, _id: 0 }
    )
      .sort({ asOf: -1 }) // Newest first for backfill (more recent data first)
      .limit(limit)
      .lean();

    return docs.map(d => ({
      symbol: d.symbol,
      window: window,
      asOf: d.asOf,
    }));
  }
}

// Singleton
let jobInstance: SentimentDatasetFinalizeJob | null = null;

export function getSentimentDatasetJob(): SentimentDatasetFinalizeJob | null {
  return jobInstance;
}

export function createSentimentDatasetJob(
  accumulator: SentimentDatasetAccumulator,
  locks: SystemLocksService,
  cfg: FinalizeJobConfig
): SentimentDatasetFinalizeJob {
  jobInstance = new SentimentDatasetFinalizeJob(accumulator, locks, cfg);
  return jobInstance;
}
