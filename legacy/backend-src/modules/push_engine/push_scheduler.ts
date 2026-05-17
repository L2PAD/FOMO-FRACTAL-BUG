/**
 * Push Scheduler
 * ==============
 * Periodic cycle (default every 5 min) that:
 *   1. Fetches latest news clusters from news-intelligence pipeline
 *   2. Detects push candidates (with state-based dedupe)
 *   3. Delegates fanout + delivery to pushRouter.routeEvent (unified flow)
 *
 * Uses an in-memory runLock to prevent overlapping cycles.
 * No other job depends on this — safe to disable via env PUSH_ENGINE_ENABLED=0.
 */

import { newsIntelligencePipeline } from '../news-intelligence/pipeline.service.js';
import { detectPushEvents } from './push_detector.js';
import { pushRouter, fromDetectedEvent } from '../../core/notifications/push-router.service.js';
import { ensurePushIndexes } from './push_state.repository.js';
import { maybeFireDigests } from './push_digest.js';
import type { DetectorCycleReport, PushType } from './types.js';

const CYCLE_MS = Number(process.env.PUSH_ENGINE_CYCLE_MS || 5 * 60 * 1000);
let runLock = false;
let timer: NodeJS.Timeout | null = null;

export let lastCycleReport: DetectorCycleReport | null = null;
export let cycleHistory: DetectorCycleReport[] = []; // keep last 20

export async function runCycleOnce(): Promise<DetectorCycleReport> {
  if (runLock) {
    return lastCycleReport ?? {
      ts: new Date(), scanned: 0, emitted: 0, skippedDup: 0, skippedThreshold: 0, tookMs: 0,
      byType: { FORMING: 0, CONFIRMED: 0, TENSION: 0, PERSONAL: 0 },
    };
  }
  runLock = true;
  const t0 = Date.now();
  const byType: Record<PushType, number> = { FORMING: 0, CONFIRMED: 0, TENSION: 0, PERSONAL: 0 };
  let emitted = 0;
  let skippedDup = 0;
  let skippedThreshold = 0;
  let scanned = 0;

  try {
    // 1. Fetch latest clusters
    const feed = await newsIntelligencePipeline.buildFeed({ limit: 40, hoursBack: 24 });
    const clusters = feed.clusters || [];

    // 2. Detect
    const detection = await detectPushEvents(clusters);
    scanned = detection.scanned;
    skippedDup = detection.skippedDup;
    skippedThreshold = detection.skippedThreshold;

    // 3. Route each event through unified router (dedupe + fanout + delivery + state tracking)
    for (const event of detection.events) {
      const unified = fromDetectedEvent(event);
      const res = await pushRouter.routeEvent(unified);
      if (res.duplicated) skippedDup += 1;
      byType[event.type] = (byType[event.type] || 0) + res.sent;
      emitted += res.sent;
      skippedThreshold += res.filteredOut;
    }

    // 4. Time-based digests (morning kickstart + evening recap). Cheap — short-circuits
    //    unless we're in the hour-slot AND haven't fired yet today.
    await maybeFireDigests();
  } catch (err) {
    console.error('[PushEngine.scheduler] cycle failed', err);
  } finally {
    runLock = false;
  }

  const report: DetectorCycleReport = {
    ts: new Date(),
    scanned,
    emitted,
    byType,
    skippedDup,
    skippedThreshold,
    tookMs: Date.now() - t0,
  };
  lastCycleReport = report;
  cycleHistory = [report, ...cycleHistory].slice(0, 20);
  return report;
}

export async function startPushScheduler(): Promise<void> {
  if (process.env.PUSH_ENGINE_ENABLED === '0') {
    console.log('[PushEngine] DISABLED via env (PUSH_ENGINE_ENABLED=0)');
    return;
  }
  await ensurePushIndexes();
  console.log(`[PushEngine] Starting scheduler (cycle=${Math.round(CYCLE_MS / 1000)}s, channel=${process.env.PUSH_ENGINE_CHANNEL || 'mock'})`);
  setTimeout(() => { runCycleOnce().catch((e) => console.error('[PushEngine] initial run', e)); }, 15_000);
  timer = setInterval(() => {
    runCycleOnce().catch((e) => console.error('[PushEngine] cycle run', e));
  }, CYCLE_MS);
}

export function stopPushScheduler(): void {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}
