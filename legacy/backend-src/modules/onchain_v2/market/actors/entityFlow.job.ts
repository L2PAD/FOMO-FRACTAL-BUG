/**
 * Entity Flow Aggregation Job
 * ============================
 * 
 * P0.8: Auto-job that runs every 10 minutes
 * Aggregates TokenFlow into EntityFlow for all windows
 */

import { EntityFlowAggregateService } from './entityFlow.aggregate.service';
import { LabelsService } from '../../labels/labels.service';
import { runPerChain } from '../../system/runPerChain';

type WindowKey = '24h' | '7d' | '30d';

export class EntityFlowJob {
  private timer: NodeJS.Timeout | null = null;
  private running = false;
  private lastRunAt: Date | null = null;
  private lastResult: any = null;
  private runCount = 0;

  constructor(
    private readonly svc: EntityFlowAggregateService,
    private readonly intervalMs: number
  ) {}

  /**
   * Start the job timer
   */
  start() {
    if (this.timer) return;
    console.log('[EntityFlowJob] Starting with interval:', this.intervalMs, 'ms');
    
    this.timer = setInterval(() => {
      this.tick().catch(e => console.error('[EntityFlowJob] Tick error:', e));
    }, this.intervalMs);
    
    // Immediate first tick
    setTimeout(() => {
      this.tick().catch(e => console.error('[EntityFlowJob] Initial tick error:', e));
    }, 5000);
  }

  /**
   * Stop the job timer
   */
  stop() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    console.log('[EntityFlowJob] Stopped');
  }

  /**
   * Get job status
   */
  status() {
    return {
      ok: true,
      enabled: Boolean(this.timer),
      running: this.running,
      runCount: this.runCount,
      lastRunAt: this.lastRunAt?.toISOString() ?? null,
      lastResult: this.lastResult,
    };
  }

  /**
   * Execute one aggregation tick
   */
  async tick(): Promise<any> {
    if (this.running) {
      console.log('[EntityFlowJob] Skip tick - already running');
      return { ok: true, skipped: true };
    }

    this.running = true;
    const startTime = Date.now();

    try {
      const windows: WindowKey[] = ['24h', '7d', '30d'];
      const now = new Date();

      const results: any[] = [];

      await runPerChain('EntityFlowJob', async (chainId) => {
        for (const window of windows) {
          const r = await this.svc.compute({ chainId, window, now, maxBuckets: 48 });
          results.push(r);
          console.log(`[EntityFlowJob] chain=${chainId} ${window}: ${r.upserts} upserts, ${r.buckets} buckets`);
        }
      });

      this.runCount += 1;
      this.lastRunAt = new Date();
      this.lastResult = {
        at: this.lastRunAt.toISOString(),
        durationMs: Date.now() - startTime,
        results,
      };

      return this.lastResult;
    } catch (e: any) {
      console.error('[EntityFlowJob] Error:', e.message);
      this.lastResult = { error: e.message, at: new Date().toISOString() };
      throw e;
    } finally {
      this.running = false;
    }
  }
}

// Singleton instance
let singleton: EntityFlowJob | null = null;

/**
 * Start the Entity Flow aggregation job
 */
export function startEntityFlowJob(deps: { labels: LabelsService }): EntityFlowJob {
  if (singleton) return singleton;

  const intervalMs = Number(process.env.ONCHAIN_V2_ACTORS_INTERVAL_MS || 10 * 60 * 1000);
  const enabled = String(process.env.ONCHAIN_V2_ACTORS_JOB_ENABLED ?? 'true') === 'true';

  const svc = new EntityFlowAggregateService(deps.labels);
  singleton = new EntityFlowJob(svc, intervalMs);

  if (enabled) {
    singleton.start();
  } else {
    console.log('[EntityFlowJob] Disabled by config');
  }

  return singleton;
}

/**
 * Get the singleton job instance
 */
export function getEntityFlowJob(): EntityFlowJob | null {
  return singleton;
}

console.log('[EntityFlowJob] Module loaded');
