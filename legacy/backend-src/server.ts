import 'dotenv/config';

// Ensure sentiment worker flags are loaded from .env (dotenv may not load them due to ESM timing)
import { readFileSync } from 'fs';
try {
  const envContent = readFileSync('/app/backend/.env', 'utf8');
  for (const line of envContent.split('\n')) {
    if (line.startsWith('#') || !line.includes('=')) continue;
    const eqIdx = line.indexOf('=');
    const key = line.slice(0, eqIdx).trim();
    const val = line.slice(eqIdx + 1).trim().replace(/^["']|["']$/g, '');
    if (!process.env[key]) process.env[key] = val;
  }
} catch { /* .env not found, rely on system env */ }
import { buildApp } from './app.js';
import { connectMongo, disconnectMongo } from './db/mongoose.js';
import { env } from './config/env.js';
import { scheduler, registerDefaultJobs } from './jobs/scheduler.js';
import { runStartupChecks } from './core/system/startup.checks.js';
import { startHealthMonitor, stopHealthMonitor } from './core/system/health.monitor.js';
import * as bootstrapWorker from './core/bootstrap/bootstrap.worker.js';
import { startTelegramPolling, stopTelegramPolling } from './telegram-polling.worker.js';
import { seedTokenRegistry } from './core/resolver/token.resolver.js';
import { ensureDefaultConfig } from './core/engine/engine_runtime_config.model.js';
import { TokenUniverseModel } from './core/token_universe/token_universe.model.js';
import { seedTokenUniverse } from './core/token_universe/token_universe.seed.js';
import { startMLDataJobs, stopMLDataJobs } from './jobs/ml_data.jobs.js';
import { startMarketWsLayer, stopMarketWsLayer } from './modules/exchange/ingestion/ws/ws.bootstrap.js';

// BATCH 1 - ML Retrain Scheduler
import { startRetrainScheduler, stopRetrainScheduler } from './core/ml_retrain/index.js';

// BATCH 2 - Dataset Export Job
import { startDatasetExportJob, stopDatasetExportJob } from './core/ml_retrain/index.js';

// ML v2.2 - Auto-Retrain Policy
import { seedDefaultPolicies } from './core/ml_retrain/auto_retrain/index.js';

async function main(): Promise<void> {
  console.log('[Server] Starting BlockView Backend...');

  // ═══════════════════════════════════════════════════════════════
  // SYSTEM PROFILE — lazy module bootstrap (cold mode for heavy services)
  // ═══════════════════════════════════════════════════════════════
  const systemProfile = process.env.SYSTEM_PROFILE || 'dev';
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log(`[Server] SYSTEM_PROFILE: ${systemProfile}`);
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  // Apply profile overrides BEFORE buildApp() so that lazy module
  // registration in app.ts sees the correct process.env values.
  if (systemProfile === 'exchange_only') {
    process.env.ONCHAIN_ENABLED = 'false';
    process.env.SENTIMENT_INTAKE_ENABLED = 'false';
    process.env.SENTIMENT_AGG_ENABLED = 'false';
    process.env.SENTIMENT_WORKERS_ENABLED = 'false';
    process.env.SENTIMENT_SHADOW_ENABLED = 'false';
    process.env.SENTIMENT_DATASET_ENABLED = 'false';
    process.env.MULTICHAIN_ENABLED = 'false';
    console.log('[Server] exchange_only → Sentiment workers, Multichain set to COLD (OnChain V2 kept ON)');
  } else if (systemProfile === 'intel_only') {
    process.env.ONCHAIN_ENABLED = 'false';
    process.env.MULTICHAIN_ENABLED = 'false';
    console.log('[Server] intel_only → OnChain, Multichain set to COLD');
  }

  // Connect to MongoDB
  console.log('[Server] Connecting to MongoDB...');
  await connectMongo();

  // Build Fastify app
  const app = buildApp();

  // B6: Run startup checks (fail-fast)
  await runStartupChecks(app);

  // P2.5: Seed token registry with known tokens
  console.log('[Server] Seeding token registry...');
  await seedTokenRegistry();
  
  // P4.1: Run Twitter User Module migration (commented for testing)
  // console.log('[Server] Running Twitter User Module migration...');
  // const { migrateAddOwnerFields } = await import('./modules/twitter-user/index.js');
  // await migrateAddOwnerFields();
  
  // БЛОК 1: Ensure ML Runtime Config exists (default: OFF)
  console.log('[Server] Initializing ML Runtime Config...');
  await ensureDefaultConfig();
  
  // БЛОК 1.5: Ensure Phase 5 Calibration Active defaults
  console.log('[Server] Initializing Phase 5 Calibration defaults...');
  const { ensureCalibrationActiveDefaults } = await import('./core/ml_calibration_phase5/calibration_active.model.js');
  await ensureCalibrationActiveDefaults();
  
  // БЛОК 2: Seed Token Universe if empty
  const tokenCount = await TokenUniverseModel.countDocuments();
  if (tokenCount === 0) {
    console.log('[Server] Seeding Token Universe...');
    await seedTokenUniverse();
  } else {
    console.log(`[Server] Token Universe already has ${tokenCount} tokens`);
  }

  // БЛОК 3: Initialize Signal Reweighting v1.1
  console.log('[Server] Initializing Signal Reweighting...');
  const { initializeSignalReweighting } = await import('./core/signal_reweighting/signal_reweighting.service.js');
  await initializeSignalReweighting();

  // БЛОК 4: Initialize Self-Learning Config (ETAP 5.1)
  console.log('[Server] Initializing Self-Learning Config...');
  const { ensureDefaultSelfLearningConfig } = await import('./core/self_learning/self_learning_config.model.js');
  await ensureDefaultSelfLearningConfig();

  // P1.5.B: Seed Market API Sources if empty
  console.log('[Server] Checking Market API Sources...');
  const { seedMarketSources } = await import('./core/market_data/sources/seed_market_sources.js');
  const seedResult = await seedMarketSources();
  if (seedResult.seeded) {
    console.log(`[Server] Seeded ${seedResult.count} default market sources`);
  } else {
    console.log(`[Server] Market sources already configured (${seedResult.count} sources)`);
  }

  // 🔴 MINIMAL_BOOT MODE - Skip heavy workers for testing
  const minimalBoot = process.env.MINIMAL_BOOT === '1';
  
  // 🚀 START WEBSOCKET LAYER (always enabled for exchange data)
  console.log('[Server] Starting WebSocket Market Data Layer...');
  startMarketWsLayer();
  
  if (minimalBoot) {
    console.log('[Server] ⚠️  MINIMAL_BOOT mode enabled - skipping background workers');
  } else {
    // Register scheduled jobs (profile-aware — see scheduler.ts)
    registerDefaultJobs();

    // Start scheduler jobs
    scheduler.startAll();

    // Health monitor — always active
    startHealthMonitor();

    // Gate heavy workers by system profile
    if (systemProfile === 'full' || systemProfile === 'dev') {
      // Bootstrap worker
      const workerStarted = await bootstrapWorker.start();
      console.log(`[Server] Bootstrap worker: ${workerStarted ? 'started' : 'skipped (lock held)'}`);

      // Telegram polling
      console.log('[Server] Starting Telegram polling worker...');
      startTelegramPolling().catch(err => {
        console.error('[Server] Telegram polling error:', err);
      });

      // ML Data Accumulation Jobs
      console.log('[Server] Starting ML Data Accumulation Jobs...');
      startMLDataJobs();

      // ML Retrain Scheduler
      console.log('[Server] Starting ML Retrain Scheduler...');
      startRetrainScheduler();

      // Dataset Export Job
      console.log('[Server] Starting Dataset Export Job...');
      startDatasetExportJob();

      // Seed default auto-retrain policies
      console.log('[Server] Seeding default auto-retrain policies...');
      await seedDefaultPolicies();
    } else if (systemProfile === 'intel_only') {
      // Intel only — telegram + sentiment, no exchange heavy
      console.log('[Server] Starting Telegram polling worker (intel_only)...');
      startTelegramPolling().catch(err => {
        console.error('[Server] Telegram polling error:', err);
      });
      console.log('[Server] intel_only — ML, Bootstrap workers skipped');
    } else {
      // exchange_only — only exchange + radar, everything else cold
      console.log('[Server] exchange_only — Telegram, ML, Bootstrap workers COLD (not started)');
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // SNAPSHOT SCHEDULER — CRITICAL DATA FLOW FIX
  // ═══════════════════════════════════════════════════════════════
  // Transforms raw module data → decision-ready snapshots for Meta Brain
  // Without this: Meta Brain sees ONLY Sentiment, NOT Exchange/Fractal
  console.log('[Server] Starting Snapshot Scheduler...');
  const { startSnapshotScheduler } = await import('./jobs/snapshot.scheduler.js');
  await startSnapshotScheduler();
  
  console.log('[Server] Starting Outcome Resolver Scheduler...');
  const { startOutcomeResolverScheduler } = await import('./jobs/outcome-resolver.job.js');
  await startOutcomeResolverScheduler();

  // Push Engine (L2 Retention) — MOCK channel by default, 5-min cycle
  try {
    const { startPushScheduler } = await import('./modules/push_engine/index.js');
    await startPushScheduler();
  } catch (err) {
    console.error('[Server] Push Engine start failed:', err);
  }

  // Signal Worker — auto-emit sentiment + polymarket pushes (Wave 1+2)
  try {
    const { startSignalWorker } = await import('./core/notifications/emitters/signal.worker.js');
    startSignalWorker();
  } catch (err) {
    console.error('[Server] Signal Worker start failed:', err);
  }

  // Graceful shutdown
  const shutdown = async (signal: string) => {
    console.log(`[Server] Received ${signal}, shutting down...`);

    // Stop WebSocket Layer
    stopMarketWsLayer();
    
    // Stop Snapshot Scheduler (CRITICAL DATA FLOW)
    const { stopSnapshotScheduler } = await import('./jobs/snapshot.scheduler.js');
    await stopSnapshotScheduler();
    
    // Stop Outcome Resolver Scheduler (TRUTH LAYER)
    const { stopOutcomeResolverScheduler } = await import('./jobs/outcome-resolver.job.js');
    await stopOutcomeResolverScheduler();

    // Stop Telegram polling
    stopTelegramPolling();
    
    // Stop ML Data Jobs
    stopMLDataJobs();
    
    // BATCH 1: Stop Retrain Scheduler
    stopRetrainScheduler();
    
    // BATCH 2: Stop Dataset Export Job
    stopDatasetExportJob();
    
    // Stop monitoring first
    stopHealthMonitor();
    
    // Stop worker
    await bootstrapWorker.stop();
    
    // Stop scheduler
    scheduler.stopAll();
    
    // Close app and DB
    await app.close();
    await disconnectMongo();

    console.log('[Server] Shutdown complete');
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  // Start server
  try {
    await app.listen({ port: env.PORT, host: '0.0.0.0' });
    console.log(`[Server] ✓ Backend started on port ${env.PORT}`);
    console.log(`[Server] Environment: ${env.NODE_ENV}`);
    console.log(`[Server] WebSocket: ${env.WS_ENABLED ? 'enabled' : 'disabled'}`);
    console.log(`[Server] Indexer: ${env.INDEXER_ENABLED && env.INFURA_RPC_URL ? 'enabled' : 'disabled'}`);
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error('[Server] Fatal error:', err);
  process.exit(1);
});
