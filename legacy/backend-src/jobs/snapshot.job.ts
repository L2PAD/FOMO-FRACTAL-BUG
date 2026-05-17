/**
 * SNAPSHOT ORCHESTRATOR JOB
 * =========================
 * 
 * Coordinates snapshot generation across all modules.
 * Ensures Meta Brain always has fresh decision-ready data.
 * 
 * CRITICAL PIPELINE ORDER:
 * 1. Fractal Engine   → Generates fractal_state from raw prices
 * 2. Exchange Publisher → Transforms observations → snapshots
 * 3. Fractal Publisher  → Transforms fractal_state → snapshots
 * 
 * Meta Brain reads ONLY snapshots, never raw data.
 */

import mongoose from 'mongoose';
import { runFractalEngineJob } from './fractal-engine.job.js';
import { runExchangePublisherJob } from './exchange-publisher.job.js';
import { runFractalPublisherJob } from './fractal-publisher.job.js';

/**
 * Run snapshot generation for all modules
 */
export async function runSnapshotJob(): Promise<void> {
  const t0 = Date.now();
  console.log('[SnapshotJob] 🚀 Starting snapshot generation...');

  const db = mongoose.connection.db;
  if (!db) {
    console.error('[SnapshotJob] ❌ MongoDB not connected');
    return;
  }

  // CRITICAL: Fractal Engine MUST run BEFORE publisher
  // It generates fractal_state that publisher reads
  try {
    await runFractalEngineJob();
  } catch (err: any) {
    console.error('[SnapshotJob] Fractal engine failed:', err.message);
  }

  // Run publishers
  try {
    await runExchangePublisherJob();
  } catch (err: any) {
    console.error('[SnapshotJob] Exchange publisher failed:', err.message);
  }

  try {
    await runFractalPublisherJob();
  } catch (err: any) {
    console.error('[SnapshotJob] Fractal publisher failed:', err.message);
  }

  const durationMs = Date.now() - t0;

  console.log('[SnapshotJob] ✅ Complete');
  console.log(`  Duration: ${durationMs}ms`);

  // Save job run metadata
  try {
    await db.collection('snapshot_job_runs').insertOne({
      timestamp: new Date(),
      durationMs,
      modules: ['fractal_engine', 'exchange', 'fractal'],
    });
  } catch (err: any) {
    // Non-critical, continue
  }
}

/**
 * Event-driven snapshot trigger (call this when new raw data arrives)
 */
export async function triggerSnapshotForAsset(asset: string, module: 'exchange' | 'fractal'): Promise<void> {
  console.log(`[SnapshotJob] 🔥 Event trigger: ${module} for ${asset}`);
  
  try {
    if (module === 'exchange') {
      const { publishExchangePredictionSnapshots } = await import('../modules/exchange/exchange-prediction.publisher.js');
      await publishExchangePredictionSnapshots(asset);
    } else if (module === 'fractal') {
      // Trigger fractal engine first, then publisher
      const { runFractalEngineJob } = await import('./fractal-engine.job.js');
      await runFractalEngineJob();
      
      const { publishFractalForecastSnapshot } = await import('../modules/fractal/fractal-forecast.publisher.js');
      await publishFractalForecastSnapshot(asset);
    }
  } catch (err: any) {
    console.error(`[SnapshotJob] Event trigger failed for ${asset} ${module}:`, err.message);
  }
}

export default runSnapshotJob;
