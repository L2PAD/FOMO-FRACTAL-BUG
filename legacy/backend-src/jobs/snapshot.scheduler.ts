/**
 * SNAPSHOT SCHEDULER
 * ==================
 * 
 * Runs snapshot job every 5 minutes
 * Ensures Meta Brain always has fresh data
 */

import { runSnapshotJob } from './snapshot.job.js';

let snapshotInterval: NodeJS.Timeout | null = null;

const INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

export function startSnapshotScheduler(): void {
  if (snapshotInterval) {
    console.log('[SnapshotScheduler] Already running');
    return;
  }

  console.log('[SnapshotScheduler] ✅ Starting (every 5 min)');

  // Run immediately on startup
  runSnapshotJob().catch(err => {
    console.error('[SnapshotScheduler] Initial run failed:', err.message);
  });

  // Then every 5 minutes
  snapshotInterval = setInterval(() => {
    runSnapshotJob().catch(err => {
      console.error('[SnapshotScheduler] Scheduled run failed:', err.message);
    });
  }, INTERVAL_MS);
}

export function stopSnapshotScheduler(): void {
  if (snapshotInterval) {
    clearInterval(snapshotInterval);
    snapshotInterval = null;
    console.log('[SnapshotScheduler] ✅ Stopped');
  }
}

export default { start: startSnapshotScheduler, stop: stopSnapshotScheduler };
