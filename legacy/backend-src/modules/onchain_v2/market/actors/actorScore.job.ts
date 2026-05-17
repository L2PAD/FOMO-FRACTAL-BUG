/**
 * ActorScore Job — Periodic structural score computation
 * =======================================================
 * 
 * P0.9: Runs every 10 minutes, computes Edge Scores for 24h/7d/30d windows.
 */

import { ActorScoreAggregateService } from "./actorScore.aggregate.service";
import { runPerChain } from "../../system/runPerChain";

type WindowKey = "24h" | "7d" | "30d";
const WINDOWS: WindowKey[] = ["24h", "7d", "30d"];

export class ActorScoreJob {
  private lastRunAt: Date | null = null;
  private lastResult: any = null;
  private running = false;

  constructor(private readonly svc: ActorScoreAggregateService) {}

  status() {
    return {
      ok: true,
      running: this.running,
      lastRunAt: this.lastRunAt,
      lastResult: this.lastResult,
    };
  }

  async tick() {
    if (this.running) return this.status();
    this.running = true;
    try {
      const out: any[] = [];
      await runPerChain('ActorScoreJob', async (chainId) => {
        for (const window of WINDOWS) {
          const result = await this.svc.computeLatest({ chainId, window });
          out.push(result);
        }
      });
      this.lastRunAt = new Date();
      this.lastResult = out;
      console.log(`[ActorScoreJob] Tick complete:`, out.map(o => `${o.window}=${o.n}`).join(', '));
      return { ok: true, out };
    } catch (e: any) {
      console.error('[ActorScoreJob] Tick error:', e.message);
      return { ok: false, error: e.message };
    } finally {
      this.running = false;
    }
  }
}

// Singleton
let _job: ActorScoreJob | null = null;

export function getActorScoreJob(): ActorScoreJob {
  if (!_job) {
    _job = new ActorScoreJob(new ActorScoreAggregateService());
  }
  return _job;
}

export function startActorScoreJob(intervalMs: number = 10 * 60 * 1000) {
  const job = getActorScoreJob();
  // Initial tick
  job.tick().catch(e => console.error('[ActorScoreJob] Initial tick error:', e));
  // Periodic
  setInterval(() => {
    job.tick().catch(e => console.error('[ActorScoreJob] Periodic tick error:', e));
  }, intervalMs);
  console.log(`[ActorScoreJob] Started with interval ${intervalMs}ms`);
  return job;
}
