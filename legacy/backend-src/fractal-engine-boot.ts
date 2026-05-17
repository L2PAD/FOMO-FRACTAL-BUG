/**
 * FRACTAL ENGINE BOOT
 * ==========================================
 * Integration layer for the Fractal Engine subsystem.
 * Registers all fractal-related routes as a single plugin
 * within the main FOMO platform.
 * 
 * Architecture:
 *   core
 *    ├ exchange
 *    ├ prediction
 *    ├ sentiment
 *    ├ onchain
 *    └ fractal  ← THIS MODULE
 * 
 * This file mirrors app.fractal.ts but adapted as a Fastify plugin,
 * NOT a standalone server.
 */

import type { FastifyInstance } from 'fastify';
import { getMongoDb } from './db/mongoose.js';
import { registerFreezeMiddleware, isFrozen } from './middleware/freeze.middleware.js';
import fs from 'fs';

// ═══════════════════════════════════════════════════════════════
// COLD START: Auto-load seed data from CSV files if MongoDB is empty
// ═══════════════════════════════════════════════════════════════

const SPX_MIN_REQUIRED = 10000;
const BTC_MIN_REQUIRED = 1000;
const DXY_MIN_REQUIRED = 10000;

async function coldStartDataCheck() {
  const db = getMongoDb();

  // SPX CANDLES
  const spxCount = await db.collection('spx_candles').countDocuments();
  console.log(`[Fractal:ColdStart] SPX candles in DB: ${spxCount}`);

  if (spxCount < SPX_MIN_REQUIRED) {
    console.log(`[Fractal:ColdStart] SPX data insufficient (${spxCount} < ${SPX_MIN_REQUIRED}), bootstrapping...`);
    const seedPaths = [
      '/app/backend/data/fractal/bootstrap/spx_stooq_seed.csv',
      '/app/data/spx_stooq.csv',
    ];

    let loaded = false;
    for (const csvPath of seedPaths) {
      if (fs.existsSync(csvPath)) {
        console.log(`[Fractal:ColdStart] Found SPX seed at: ${csvPath}`);
        try {
          const csvContent = fs.readFileSync(csvPath, 'utf-8');
          const lines = csvContent.trim().split('\n');
          const candles: any[] = [];
          for (let i = 1; i < lines.length; i++) {
            const parts = lines[i].split(',');
            if (parts.length >= 5) {
              const dateStr = parts[0].trim();
              const open = parseFloat(parts[1]);
              const high = parseFloat(parts[2]);
              const low = parseFloat(parts[3]);
              const close = parseFloat(parts[4]);
              const volume = parts[5] ? parseFloat(parts[5]) : 0;
              const dateParts = dateStr.split('-');
              const ts = new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2])).getTime();
              if (dateStr && !isNaN(close) && !isNaN(ts)) {
                candles.push({ date: dateStr, ts, open, high, low, close, volume, symbol: 'SPX', source: 'COLD_START_SEED', insertedAt: new Date() });
              }
            }
          }
          if (candles.length > 0) {
            const bulkOps = candles.map(c => ({ updateOne: { filter: { date: c.date, symbol: 'SPX' }, update: { $set: c }, upsert: true } }));
            const result = await db.collection('spx_candles').bulkWrite(bulkOps, { ordered: false });
            console.log(`[Fractal:ColdStart] SPX bootstrap: ${result.upsertedCount + result.modifiedCount} candles`);
            loaded = true;
            break;
          }
        } catch (err) {
          console.error(`[Fractal:ColdStart] SPX load failed from ${csvPath}:`, err);
        }
      }
    }
    if (!loaded) console.error('[Fractal:ColdStart] No SPX seed found!');
  } else {
    console.log(`[Fractal:ColdStart] SPX data OK (${spxCount} candles)`);
  }

  // BTC CANDLES
  const btcCount = await db.collection('fractal_canonical_ohlcv').countDocuments();
  console.log(`[Fractal:ColdStart] BTC candles: ${btcCount}`);
  if (btcCount < BTC_MIN_REQUIRED) {
    console.log(`[Fractal:ColdStart] BTC data insufficient — will load on first request`);
  }

  // DXY CANDLES
  const dxyCount = await db.collection('dxy_candles').countDocuments();
  console.log(`[Fractal:ColdStart] DXY candles: ${dxyCount}`);

  if (dxyCount < DXY_MIN_REQUIRED) {
    console.log(`[Fractal:ColdStart] DXY data insufficient (${dxyCount} < ${DXY_MIN_REQUIRED}), bootstrapping...`);
    const dxySeedPaths = [
      '/app/backend/data/fractal/bootstrap/dxy_extended_seed.csv',
      '/app/backend/data/fractal/bootstrap/dxy_stooq_seed.csv',
      '/app/data/dxy_stooq.csv',
    ];

    let dxyLoaded = false;
    for (const csvPath of dxySeedPaths) {
      if (fs.existsSync(csvPath)) {
        console.log(`[Fractal:ColdStart] Found DXY seed at: ${csvPath}`);
        try {
          const csvContent = fs.readFileSync(csvPath, 'utf-8');
          const lines = csvContent.trim().split('\n');
          const candles: any[] = [];
          for (let i = 1; i < lines.length; i++) {
            const parts = lines[i].split(',');
            if (parts.length >= 5) {
              const dateStr = parts[0].trim();
              const open = parseFloat(parts[1]);
              const high = parseFloat(parts[2]);
              const low = parseFloat(parts[3]);
              const close = parseFloat(parts[4]);
              const volume = parts[5] ? parseFloat(parts[5]) : 0;
              const dateParts = dateStr.split('-');
              const ts = new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2])).getTime();
              if (dateStr && !isNaN(close) && !isNaN(ts)) {
                candles.push({ date: dateStr, ts, open, high, low, close, volume, symbol: 'DXY', source: 'COLD_START_SEED', insertedAt: new Date() });
              }
            }
          }
          if (candles.length > 0) {
            const bulkOps = candles.map(c => ({ updateOne: { filter: { date: c.date, symbol: 'DXY' }, update: { $set: c }, upsert: true } }));
            const result = await db.collection('dxy_candles').bulkWrite(bulkOps, { ordered: false });
            console.log(`[Fractal:ColdStart] DXY bootstrap: ${result.upsertedCount + result.modifiedCount} candles`);
            dxyLoaded = true;
            break;
          }
        } catch (err) {
          console.error(`[Fractal:ColdStart] DXY load failed from ${csvPath}:`, err);
        }
      }
    }
    if (!dxyLoaded) console.error('[Fractal:ColdStart] No DXY seed found!');
  } else {
    console.log(`[Fractal:ColdStart] DXY data OK (${dxyCount} candles)`);
  }

  // Ensure indexes
  await db.collection('spx_candles').createIndex({ ts: -1 }).catch(() => {});
  await db.collection('spx_candles').createIndex({ ts: 1, symbol: 1 }, { unique: true }).catch(() => {});
  await db.collection('spx_candles').createIndex({ date: 1, symbol: 1 }, { unique: true }).catch(() => {});
  await db.collection('dxy_candles').createIndex({ date: -1 }).catch(() => {});
  await db.collection('dxy_candles').createIndex({ date: 1 }, { unique: true }).catch(() => {});

  console.log('[Fractal:ColdStart] Bootstrap complete');
}

// ═══════════════════════════════════════════════════════════════
// MAIN BOOT FUNCTION — registers all Fractal Engine routes
// ═══════════════════════════════════════════════════════════════

export async function bootFractalEngine(app: FastifyInstance): Promise<void> {
  console.log('');
  console.log('===================================================');
  console.log('  FRACTAL ENGINE — Initializing as subsystem');
  console.log(`  FROZEN: ${isFrozen() ? 'YES' : 'NO'}`);
  console.log('===================================================');

  // Register freeze middleware
  registerFreezeMiddleware(app);

  // ── Core Fractal Module ──
  const { registerFractalModule } = await import('./modules/fractal/index.js');
  await registerFractalModule(app);
  app.log.info('[Fractal] Core module registered');

  // ── BTC Terminal ──
  const { registerBtcRoutes } = await import('./modules/btc/index.js');
  await registerBtcRoutes(app);
  app.log.info('[Fractal] BTC Terminal registered');

  // ── SPX Terminal ──
  const { registerSpxRoutes } = await import('./modules/spx/index.js');
  await registerSpxRoutes(app);
  app.log.info('[Fractal] SPX Terminal registered');

  // ── SPX Core (Fractal Engine) ──
  const { registerSpxCoreRoutes } = await import('./modules/spx-core/index.js');
  await registerSpxCoreRoutes(app);
  app.log.info('[Fractal] SPX Core registered');

  // ── SPX Memory Layer ──
  const { registerSpxMemoryRoutes } = await import('./modules/spx-memory/spx-memory.routes.js');
  await registerSpxMemoryRoutes(app);

  // ── SPX Attribution ──
  const { registerSpxAttributionRoutes } = await import('./modules/spx-attribution/spx-attribution.routes.js');
  await registerSpxAttributionRoutes(app);

  // ── SPX Drift Intelligence ──
  const { registerSpxDriftRoutes } = await import('./modules/spx-drift/spx-drift.routes.js');
  await registerSpxDriftRoutes(app);

  // ── SPX Consensus ──
  const { registerSpxConsensusRoutes } = await import('./modules/spx-consensus/spx-consensus.routes.js');
  await registerSpxConsensusRoutes(app);

  // ── SPX Calibration ──
  const { registerSpxCalibrationRoutes } = await import('./modules/spx-calibration/spx-calibration.routes.js');
  await registerSpxCalibrationRoutes(app);

  // ── SPX Rules ──
  const { registerSpxRulesRoutes } = await import('./modules/spx-rules/spx-rules.routes.js');
  registerSpxRulesRoutes(app);

  // ── SPX Guardrails ──
  const { registerSpxGuardrailsRoutes } = await import('./modules/spx-guardrails/spx-guardrails.routes.js');
  await registerSpxGuardrailsRoutes(app);

  // ── SPX Crisis ──
  const { registerSpxCrisisRoutes, registerSpxCrisisDebugRoutes } = await import('./modules/spx-crisis/spx-crisis.routes.js');
  await registerSpxCrisisRoutes(app);
  await registerSpxCrisisDebugRoutes(app);

  // ── SPX Regime ──
  const { registerSpxRegimeRoutes } = await import('./modules/spx-regime/regime.routes.js');
  await registerSpxRegimeRoutes(app);

  // ── Lifecycle Engine ──
  const { registerLifecycleRoutes } = await import('./modules/lifecycle/lifecycle.routes.js');
  await registerLifecycleRoutes(app);

  // ── Daily Run Orchestrator ──
  const { registerDailyRunRoutes } = await import('./modules/ops/daily-run/index.js');
  await registerDailyRunRoutes(app);

  // ── SPX Unified Routes (BTC-compatible contract) ──
  const { registerSpxUnifiedRoutes } = await import('./modules/fractal/api/fractal.spx.routes.js');
  await registerSpxUnifiedRoutes(app);

  // ── Forward Performance Admin ──
  const { registerForwardAdminRoutes } = await import('./modules/forward/api/forward.admin.routes.js');
  await registerForwardAdminRoutes(app);

  // ── DXY Module ──
  const { registerDxyModule } = await import('./modules/dxy/index.js');
  await registerDxyModule(app);

  // ── DXY Forward Performance ──
  const { registerDxyForwardRoutes } = await import('./modules/dxy/forward/api/dxy_forward.admin.routes.js');
  await registerDxyForwardRoutes(app);

  // ── DXY Macro Module ──
  const { registerDxyMacroModule } = await import('./modules/dxy-macro/index.js');
  await registerDxyMacroModule(app);

  // ── CPI Macro Module ──
  const { registerCpiModule } = await import('./modules/dxy-macro-cpi/index.js');
  await registerCpiModule(app);

  // ── UNRATE Macro Module ──
  const { registerUnrateModule } = await import('./modules/dxy-macro-unrate/index.js');
  await registerUnrateModule(app);

  // ── DXY Walk-Forward Validation ──
  const { registerDxyWalkRoutes } = await import('./modules/dxy/walk/dxy-walk.routes.js');
  await registerDxyWalkRoutes(app);

  // ── DXY Macro Core Platform ──
  const { registerDxyMacroCoreModule } = await import('./modules/dxy-macro-core/index.js');
  await registerDxyMacroCoreModule(app);

  // ── AE Brain Module ──
  const { registerAeRoutes } = await import('./modules/ae-brain/api/ae.routes.js');
  await registerAeRoutes(app);

  // ── AE Cluster Module ──
  const { registerClusterRoutes } = await import('./modules/ae-brain/cluster/api/cluster.routes.js');
  await registerClusterRoutes(app);

  // ── AE Transition Module ──
  const { registerTransitionRoutes } = await import('./modules/ae-brain/transition/api/transition.routes.js');
  await registerTransitionRoutes(app);

  // ── SPX Cascade (DXY/AE → SPX) ──
  const { registerSpxCascadeRoutes } = await import('./modules/spx-cascade/spx_cascade.routes.js');
  await registerSpxCascadeRoutes(app);

  // ── SPX Cascade Validation ──
  const { registerSpxValidationRoutes } = await import('./modules/spx-cascade/spx_validation.routes.js');
  await registerSpxValidationRoutes(app);

  // ── BTC Cascade (DXY/AE/SPX → BTC) ──
  const { registerBtcCascadeRoutes } = await import('./modules/btc-cascade/btc_cascade.routes.js');
  await registerBtcCascadeRoutes(app);

  // ── BTC Cascade Validation ──
  const { registerBtcValidationRoutes } = await import('./modules/btc-cascade/validation/btc_validation.routes.js');
  await registerBtcValidationRoutes(app);

  // ── P3.3 Bias Check ──
  const { registerP33BiasCheckRoutes } = await import('./modules/admin/p33_bias_check.routes.js');
  await registerP33BiasCheckRoutes(app);

  // ── Engine Global (Asset Allocation) ──
  const { registerEngineGlobalRoutes } = await import('./modules/engine-global/engine_global.routes.js');
  await registerEngineGlobalRoutes(app);

  // ── Guard Hysteresis ──
  const { registerGuardHysteresisRoutes } = await import('./modules/dxy-macro-guard/guard_hysteresis.routes.js');
  await registerGuardHysteresisRoutes(app);

  // ── Liquidity Engine ──
  const { registerLiquidityRoutes } = await import('./modules/liquidity-engine/liquidity.routes.js');
  await registerLiquidityRoutes(app);

  // ── Combined Terminal ──
  const { registerCombinedRoutes } = await import('./modules/combined/index.js');
  await registerCombinedRoutes(app);

  // ── Model Config Routes ──
  const { default: modelConfigRoutes } = await import('./modules/fractal/config/model-config.routes.js');
  await app.register(modelConfigRoutes);

  // ── Lifecycle Admin Routes ──
  const { default: lifecycleAdminRoutes } = await import('./modules/fractal/lifecycle/lifecycle.admin.routes.js');
  await app.register(lifecycleAdminRoutes);

  // ── Index Engine V2 ──
  const { registerIndexEngineRoutes } = await import('./modules/index-engine/routes/index.routes.js');
  await registerIndexEngineRoutes(app);

  // ── Macro Engine (V1/V2) ──
  const { registerMacroEngineRoutes } = await import('./modules/macro-engine/routes/macro_engine.routes.js');
  await registerMacroEngineRoutes(app);

  // ── V2 Calibration Objective ──
  const { registerV2CalibrationObjectiveRoutes } = await import('./modules/macro-engine/v2/v2_calibration_objective.routes.js');
  await registerV2CalibrationObjectiveRoutes(app);

  // ── RC Calibration ──
  const { registerRCCalibrationRoutes } = await import('./modules/macro-engine/v2/rc_calibration.routes.js');
  await registerRCCalibrationRoutes(app);

  // ── Compare + Validation Layer ──
  const { registerCompareRoutes } = await import('./modules/macro-engine/compare/compare.routes.js');
  await registerCompareRoutes(app);

  // ── Shadow Audit ──
  const { shadowAuditRoutes } = await import('./modules/macro-engine/shadow/shadow_audit.routes.js');
  await shadowAuditRoutes(app);

  // ── Brain V2 ──
  const { brainRoutes } = await import('./modules/brain/routes/brain.routes.js');
  await brainRoutes(app);

  // ── Brain ML (Quantile Forecasts) ──
  const { brainMlRoutes } = await import('./modules/brain/ml/routes/brain_ml.routes.js');
  await brainMlRoutes(app);
  const { brainForecastRoutes } = await import('./modules/brain/ml/routes/brain_forecast.routes.js');
  await brainForecastRoutes(app);

  // ── Cross-Asset Regime Classifier ──
  const { crossAssetRoutes } = await import('./modules/brain/routes/cross_asset.routes.js');
  await crossAssetRoutes(app);

  // ── Brain Compare + Simulation ──
  const { brainCompareSimRoutes } = await import('./modules/brain/routes/brain_compare_sim.routes.js');
  await brainCompareSimRoutes(app);

  // ── Stress + Crash-Test ──
  const { stressCrashTestRoutes } = await import('./modules/brain/routes/stress_crash_test.routes.js');
  await stressCrashTestRoutes(app);

  // ── Regime Memory ──
  const { regimeMemoryRoutes } = await import('./modules/brain/routes/regime_memory.routes.js');
  await regimeMemoryRoutes(app);

  // ── Meta Risk ──
  const { metaRiskRoutes } = await import('./modules/brain/routes/meta_risk.routes.js');
  await metaRiskRoutes(app);

  // ── Capital Allocation Optimizer ──
  const { optimizerRoutes } = await import('./modules/brain/optimizer/optimizer.routes.js');
  await optimizerRoutes(app);

  // ── Adaptive Coefficient Learning ──
  const { adaptiveRoutes } = await import('./modules/brain/adaptive/adaptive.routes.js');
  await adaptiveRoutes(app);

  // ── Portfolio Return Backtest ──
  const { p13BacktestRoutes } = await import('./modules/backtest/p13.routes.js');
  await p13BacktestRoutes(app);

  // ── Regime & Volatility Analysis ──
  const { analysisRoutes } = await import('./modules/analysis/routes/analysis.routes.js');
  await analysisRoutes(app);

  // ── Capital Scaling ──
  const { capitalScalingRoutes } = await import('./modules/capital-scaling/index.js');
  await capitalScalingRoutes(app);

  // ── UI Brain (User Page) ──
  const { brainOverviewRoutes } = await import('./modules/ui-brain/index.js');
  await brainOverviewRoutes(app);

  // ── UI DXY ──
  const { dxyOverviewRoutes } = await import('./modules/ui-dxy/index.js');
  await dxyOverviewRoutes(app);

  // ── SPX Macro Overlay ──
  const { spxMacroOverlayRoutes } = await import('./modules/spx-macro-overlay/index.js');
  await spxMacroOverlayRoutes(app);

  // ── Horizon Meta (Adaptive Similarity) ──
  const { horizonMetaRoutes, ensureProjectionTrackingIndexes } = await import('./modules/fractal/horizon-meta/index.js');
  await horizonMetaRoutes(app);
  await ensureProjectionTrackingIndexes();

  // ── Cross-Asset Composite Lifecycle ──
  const { compositeLifecycleRoutes } = await import('./modules/cross-asset/index.js');
  await compositeLifecycleRoutes(app);

  // ── BTC Overlay (SPX → BTC Influence) ──
  const { btcOverlayRoutes } = await import('./modules/btc-overlay/index.js');
  await btcOverlayRoutes(app);

  // ── Admin Jobs & Health ──
  const { default: adminJobsRoutes } = await import('./modules/jobs/admin_jobs.routes.js');
  await adminJobsRoutes(app);

  // ── Timeline ──
  const { default: registerTimelineRoutes } = await import('./modules/admin/timeline/timeline.routes.js');
  await registerTimelineRoutes(app);

  // ── Health Scheduler ──
  const { startHealthScheduler } = await import('./modules/jobs/health_scheduler.job.js');
  startHealthScheduler();

  // ── Unified Admin Dashboard ──
  const { default: registerDashboardRoutes } = await import('./modules/admin/dashboard/dashboard.routes.js');
  await registerDashboardRoutes(app);

  // ── Drift Analytics ──
  const { registerDriftAnalyticsRoutes } = await import('./modules/admin/drift-analytics/index.js');
  await registerDriftAnalyticsRoutes(app);

  // ── Cold Start Data Check ──
  console.log('[Fractal] Running cold start data check...');
  await coldStartDataCheck();

  console.log('===================================================');
  console.log('  FRACTAL ENGINE — All modules registered');
  console.log('===================================================');
  console.log('');
}
