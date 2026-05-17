/**
 * Ingestion Scheduler
 * ===================
 * Runs bridge ingestion on a fixed interval (default: every 5 minutes).
 * Lock-protected via the orchestrator to prevent overlapping runs.
 */

import { ingestionOrchestratorService } from './ingestion.orchestrator.service.js';

interface SchedulerConfig {
  intervalMs: number;
  limit: number;
  sinceMinutes: number;
}

const DEFAULT_CONFIG: SchedulerConfig = {
  intervalMs: 5 * 60 * 1000, // 5 minutes
  limit: 250,
  sinceMinutes: 30,
};

class IngestionScheduler {
  private timer: ReturnType<typeof setInterval> | null = null;
  private running = false;
  private config: SchedulerConfig;
  private lastRunAt: Date | null = null;
  private runCount = 0;
  private errorCount = 0;

  constructor(config?: Partial<SchedulerConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  start(): void {
    if (this.timer) {
      console.log('[IngestionScheduler] Already running');
      return;
    }

    this.running = true;
    console.log(`[IngestionScheduler] Starting (every ${this.config.intervalMs / 1000}s, limit=${this.config.limit})`);

    // Initial run after 30 seconds (let system stabilize)
    setTimeout(() => this.tick(), 30 * 1000);

    this.timer = setInterval(() => this.tick(), this.config.intervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.running = false;
    console.log('[IngestionScheduler] Stopped');
  }

  getStatus() {
    return {
      running: this.running,
      intervalMs: this.config.intervalMs,
      lastRunAt: this.lastRunAt,
      runCount: this.runCount,
      errorCount: this.errorCount,
    };
  }

  private async tick(): Promise<void> {
    try {
      this.lastRunAt = new Date();
      this.runCount++;

      // Run all adapters (twitter + news)
      await ingestionOrchestratorService.runAll({
        limit: this.config.limit,
        sinceMinutes: this.config.sinceMinutes,
      });
    } catch (err: any) {
      // LOCK_BUSY is normal (means previous run is still going)
      if (!err.message?.includes('LOCK_BUSY')) {
        this.errorCount++;
        console.error('[IngestionScheduler] Tick error:', err.message);
      }
    }
  }
}

export const ingestionScheduler = new IngestionScheduler();
