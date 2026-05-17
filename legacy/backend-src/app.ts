import Fastify, { FastifyInstance } from 'fastify';
import cors from '@fastify/cors';
import fastifyWebsocket from '@fastify/websocket';
import { env } from './config/env.js';
import { registerRoutes } from './api/routes.js';
import { zodPlugin } from './plugins/zod.js';
import { setupWebSocketGateway } from './core/websocket/index.js';
import { AppError } from './common/errors.js';

/**
 * Build Fastify Application
 */
export function buildApp(): FastifyInstance {
  const app = Fastify({
    logger: {
      level: env.LOG_LEVEL,
    },
    trustProxy: true,
    pluginTimeout: 300000,
  });

  // CORS
  app.register(cors, {
    origin: env.CORS_ORIGINS === '*' ? true : env.CORS_ORIGINS.split(','),
    credentials: true,
  });

  // Plugins
  app.register(zodPlugin);
  
  // WebSocket plugin - register at root level
  if (env.WS_ENABLED) {
    app.register(fastifyWebsocket, {
      options: { maxPayload: 1048576 }
    });
    app.log.info('WebSocket plugin registered');
  }

  // Global error handler
  app.setErrorHandler((err, _req, reply) => {
    app.log.error(err);

    if (err instanceof AppError) {
      return reply.status(err.statusCode).send({
        ok: false,
        error: err.code,
        message: err.message,
      });
    }

    // Fastify validation errors
    if (err.validation) {
      return reply.status(400).send({
        ok: false,
        error: 'VALIDATION_ERROR',
        message: err.message,
      });
    }

    // Unknown errors
    const statusCode = (err as { statusCode?: number }).statusCode ?? 500;
    return reply.status(statusCode).send({
      ok: false,
      error: 'INTERNAL_ERROR',
      message: env.NODE_ENV === 'production' ? 'Internal server error' : err.message,
    });
  });

  // Not found handler
  app.setNotFoundHandler((_req, reply) => {
    reply.status(404).send({
      ok: false,
      error: 'NOT_FOUND',
      message: 'Route not found',
    });
  });

  // Register routes
  app.register(registerRoutes);
  
  // Register Twitter User Module (P4.1 + Block 4 Control Plane + Phase 1.1 API Keys)
  console.log('[BOOT] before twitter-user module');
  app.register(async (fastify) => {
    console.log('[BOOT] inside twitter-user module registration');
    
    const {
      createTwitterUserModule,
      registerTwitterUserRoutes,
      registerTwitterWebhookRoutes,
      registerApiKeyRoutes,
      registerParseTargetRoutes,
      registerQuotaRoutes,
      registerSchedulerRoutes,
      registerScrollRuntimeRoutes,
      registerRuntimeSelectionRoutes,
      registerParseRoutes,
      registerDebugRoutes,
      registerAccountRoutes,
    } = await import('./modules/twitter-user/index.js');
    
    // Phase 5.2.1: Telegram Binding routes
    const { telegramBindingRoutes } = await import('./modules/twitter-user/routes/telegram-binding.routes.js');

    console.log('[BOOT] twitter-user module imported');

    const cookieEncKey = process.env.COOKIE_ENC_KEY || '';
    const twitterModule = createTwitterUserModule({ cookieEncKey });

    console.log('[BOOT] twitter-user module created');

    // Register all routes
    await registerTwitterUserRoutes(fastify, {
      integration: twitterModule.integration,
      sessions: twitterModule.sessions,
    });
    
    // Phase 1.1: API Key management routes
    await registerApiKeyRoutes(fastify);
    
    // Webhook routes (now uses API Key auth)
    await registerTwitterWebhookRoutes(fastify, {
      sessions: twitterModule.sessions,
    });
    
    // Block 4 routes
    await registerParseTargetRoutes(fastify);
    await registerQuotaRoutes(fastify);
    await registerSchedulerRoutes(fastify);
    await registerScrollRuntimeRoutes(fastify);
    
    // Phase 1.3: Runtime Selection routes
    await registerRuntimeSelectionRoutes(fastify);
    
    // Phase 1.4: Parse routes
    await registerParseRoutes(fastify);
    
    // Debug routes
    await registerDebugRoutes(fastify);
    
    // A.2.1: Account Management routes
    await registerAccountRoutes(fastify);
    
    // Phase 5.2.1: Telegram Binding routes
    await telegramBindingRoutes(fastify);

    console.log('[BOOT] all routes registered (Block 4 + Phase 1.1-1.4 + Debug + A.2.1 Accounts + Phase 5.2.1 Telegram)');

    fastify.log.info('Twitter User Module (P4.1 + Block 4 + Phase 1.1-1.4) registered');
  });
  console.log('[BOOT] after twitter-user module');
  
  // A.3 - Admin Control Plane
  app.register(async (fastify) => {
    console.log('[BOOT] registering twitter-admin module');
    try {
      const adminModule = await import('./modules/twitter-admin/routes/admin.routes.js');
      await adminModule.registerAdminTwitterRoutes(fastify);
      console.log('[BOOT] twitter-admin module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register twitter-admin module:', err);
    }
  });
  
  // Register Twitter module (v4.0)
  app.register(async (instance) => {
    const { registerTwitterModule } = await import('./modules/twitter/twitter.module.js');
    await registerTwitterModule(instance);
  });

  // NOTE: Twitter Parser Admin module DISABLED - replaced by MULTI architecture
  // New routes registered via twitter/accounts, twitter/sessions, twitter/slots
  // app.register(async (instance) => {
  //   const { registerTwitterParserAdminModule } = await import('./modules/twitter_parser_admin/index.js');
  //   await registerTwitterParserAdminModule(instance);
  // });

  // WebSocket endpoint - register after websocket plugin
  if (env.WS_ENABLED) {
    app.after(() => {
      setupWebSocketGateway(app);
    });
  }

  // Universal Sentiment API v1 (always enabled — standalone service)
  app.register(async (fastify) => {
    try {
      const { registerSentimentV1Routes } = await import('./modules/sentiment/v1.routes.js');
      await registerSentimentV1Routes(fastify);
      console.log('[BOOT] Sentiment V1 universal API registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment V1 API:', err);
    }
  });

  // Register Sentiment Module (S2.1) — legacy, gated
  app.register(async (fastify) => {
    const sentimentEnabled = process.env.SENTIMENT_ENABLED === 'true';
    if (sentimentEnabled) {
      console.log('[BOOT] Registering sentiment module...');
      try {
        const { initSentimentModule } = await import('./modules/sentiment/index.js');
        await initSentimentModule(fastify);
        console.log('[BOOT] Sentiment module registered successfully');
      } catch (err) {
        console.error('[BOOT] Failed to register sentiment module:', err);
      }
    } else {
      console.log('[BOOT] Sentiment module disabled (SENTIMENT_ENABLED != true)');
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // SENTIMENT-ML MODULE (Block 1-4: Full Pipeline)
  // ═══════════════════════════════════════════════════════════════
  // New Sentiment architecture with Connections integration via port/adapter pattern.
  // Follows Exchange module architecture: isolated, auto-learning, production-grade.
  //
  // Block 1: ConnectionsAdapter → Enrichment
  // Block 2: Intake Worker → Symbol Extraction → sentiment_events
  // Block 3: Weighted Sentiment Engine (deterministic weighting)
  // Block 4: Aggregation Engine (24H/7D/30D)
  app.register(async (fastify) => {
    const sentimentMLEnabled = process.env.SENTIMENT_ML_ENABLED === 'true';
    const intakeEnabled = process.env.SENTIMENT_INTAKE_ENABLED === 'true';
    const aggEnabled = process.env.SENTIMENT_AGG_ENABLED === 'true';
    
    console.log('[BOOT] Registering Sentiment-ML module (Block 1-4)...');
    console.log(`[BOOT] SENTIMENT_ML_ENABLED=${sentimentMLEnabled}, INTAKE=${intakeEnabled}, AGG=${aggEnabled}`);
    try {
      // Import dependencies
      const { getDb } = await import('./db/mongodb.js');
      const { initSentimentML, startSentimentIntakeWorker, startSentimentAggregateWorker } = await import('./modules/sentiment-ml/index.js');
      const { registerSentimentMLAdminRoutes } = await import('./modules/sentiment-ml/routes/sentiment-ml.admin.routes.js');
      const { registerSentimentIntakeAdminRoutes } = await import('./modules/sentiment-ml/routes/sentiment-intake.admin.routes.js');
      const { registerSentimentAggregateRoutes } = await import('./modules/sentiment-ml/routes/sentiment-aggregate.routes.js');
      const { registerSentimentAggregateAdminRoutes } = await import('./modules/sentiment-ml/routes/sentiment-aggregate.admin.routes.js');
      
      // Initialize module with MongoDB client
      const db = getDb();
      initSentimentML(db.client);
      
      // Register admin routes (always available for monitoring)
      await fastify.register(registerSentimentMLAdminRoutes, { prefix: '/api/admin/sentiment-ml' });
      
      // Block 2: Register intake admin routes
      await fastify.register(registerSentimentIntakeAdminRoutes, { prefix: '/api/admin/sentiment-ml' });
      
      // Block 4: Register aggregate public routes
      await fastify.register(registerSentimentAggregateRoutes, { prefix: '/api/sentiment' });
      
      // Block 4: Register aggregate admin routes
      await fastify.register(registerSentimentAggregateAdminRoutes, { prefix: '/api/admin/sentiment-ml' });
      
      // BLOCK P1.1 + P1.2: Sentiment UI V2 routes (reliability-adjusted)
      const { registerSentimentUIV2Routes } = await import('./modules/sentiment-ml/chart/sentiment-ui-v2.routes.js');
      await fastify.register(registerSentimentUIV2Routes);
      
      // BLOCK P3: Sentiment Intelligence Page routes
      const { registerSentimentIntelligenceRoutes } = await import('./modules/sentiment-ml/intelligence/sentiment-intelligence.routes.js');
      await fastify.register(registerSentimentIntelligenceRoutes);
      
      console.log(`[BOOT] Sentiment-ML module registered (Block 1-4, P1.1-P3)`);
      console.log('[BOOT] Sentiment-ML routes: /api/admin/sentiment-ml/*, /api/sentiment/*, /api/market/chart/sentiment-v2, /api/market/sentiment/*');
      
      // BLOCK E1-E5: Exchange UI V2 routes (reliability-adjusted)
      const { registerExchangeUIV2Routes } = await import('./modules/exchange-ml/chart/exchange-ui-v2.routes.js');
      await fastify.register(registerExchangeUIV2Routes);
      console.log('[BOOT] Exchange UI V2 routes: /api/market/chart/exchange-v2, /api/market/exchange/*');
      
      // BLOCK E6: Exchange Admin Snapshot routes
      const { registerExchangeAdminSnapshotRoutes } = await import('./modules/exchange-ml/admin/exchange-admin-snapshot.routes.js');
      await fastify.register(registerExchangeAdminSnapshotRoutes);
      console.log('[BOOT] Exchange Admin routes: /api/admin/exchange-ml/admin-snapshot');
      
      // Block 2: Start intake worker (background processing)
      if (intakeEnabled) {
        setTimeout(async () => {
          try {
            await startSentimentIntakeWorker();
            console.log('[BOOT] Sentiment-ML Intake Worker started');
          } catch (workerErr) {
            console.error('[BOOT] Failed to start Sentiment Intake Worker:', workerErr);
          }
        }, 5000);
      }
      
      // Block 4: Start aggregation worker
      if (aggEnabled) {
        setTimeout(async () => {
          try {
            await startSentimentAggregateWorker();
            console.log('[BOOT] Sentiment-ML Aggregate Worker started');
          } catch (workerErr) {
            console.error('[BOOT] Failed to start Sentiment Aggregate Worker:', workerErr);
          }
        }, 8000); // Start after intake worker
      }
      
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment-ML module:', err);
    }
  });

  // Block 6: Sentiment Dataset Module (with fastify-plugin)
  app.register(async (fastify) => {
    const datasetEnabled = process.env.SENTIMENT_DATASET_ENABLED === 'true';
    console.log(`[BOOT] SENTIMENT_DATASET_ENABLED=${datasetEnabled}`);
    
    if (!datasetEnabled) {
      console.log('[BOOT] Sentiment Dataset disabled');
      return;
    }
    
    try {
      // Import and register routes
      const { sentimentDatasetRoutesPlugin } = await import('./modules/sentiment-ml/dataset/index.js');
      await fastify.register(sentimentDatasetRoutesPlugin);
      console.log('[BOOT] Sentiment Dataset routes registered');
      
      // Initialize job
      const { 
        SentimentDatasetAccumulator,
        createSentimentDatasetJob,
        getSentimentPriceAdapter,
      } = await import('./modules/sentiment-ml/dataset/index.js');
      const { getSystemLocksService } = await import('./modules/system/locks/index.js');
      
      const priceAdapter = getSentimentPriceAdapter();
      const graceMs = Number(process.env.SENTIMENT_DATASET_GRACE_MS || 2 * 60 * 60 * 1000);
      const accumulator = new SentimentDatasetAccumulator(priceAdapter, { graceMs });
      
      const locks = getSystemLocksService();
      const job = createSentimentDatasetJob(accumulator, locks, {
        enabled: true,
        intervalMs: Number(process.env.SENTIMENT_DATASET_FINALIZE_INTERVAL_MS || 6 * 60 * 60 * 1000),
        lockTtlMs: Number(process.env.SENTIMENT_DATASET_LOCK_TTL_MS || 5 * 60 * 1000),
        graceMs,
        maxBatch: Number(process.env.SENTIMENT_DATASET_MAX_BATCH || 200),
      });
      
      console.log('[BOOT] Sentiment Dataset Job initialized');
      
      // Start job after delay
      setTimeout(() => {
        try {
          job.start();
          console.log('[BOOT] Sentiment Dataset Finalize Job started');
        } catch (jobErr) {
          console.error('[BOOT] Failed to start Dataset Job:', jobErr);
        }
      }, 10000);
      
    } catch (err) {
      console.error('[BOOT] Failed to setup Sentiment Dataset module:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/dataset' });

  // Block 7: Sentiment Early Validation (monitoring only)
  app.register(async (fastify) => {
    const datasetEnabled = process.env.SENTIMENT_DATASET_ENABLED === 'true';
    
    if (!datasetEnabled) {
      console.log('[BOOT] Sentiment Validation disabled (dataset not enabled)');
      return;
    }
    
    try {
      const { sentimentEarlyValidationRoutesPlugin } = await import('./modules/sentiment-ml/validation/index.js');
      await fastify.register(sentimentEarlyValidationRoutesPlugin);
      console.log('[BOOT] Sentiment Early Validation routes registered (BLOCK 7)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Validation:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/validation' });

  // Historical Replay Admin Routes
  app.register(async (fastify) => {
    const datasetEnabled = process.env.SENTIMENT_DATASET_ENABLED === 'true';
    
    if (!datasetEnabled) {
      console.log('[BOOT] Sentiment Replay disabled (dataset not enabled)');
      return;
    }
    
    try {
      const { sentimentReplayRoutesPlugin } = await import('./modules/sentiment-ml/replay/index.js');
      await fastify.register(sentimentReplayRoutesPlugin);
      console.log('[BOOT] Sentiment Replay routes registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Replay:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/replay' });

  // Block 8: Sentiment Binary ML Layer
  app.register(async (fastify) => {
    const datasetEnabled = process.env.SENTIMENT_DATASET_ENABLED === 'true';
    
    if (!datasetEnabled) {
      console.log('[BOOT] Sentiment Binary ML disabled (dataset not enabled)');
      return;
    }
    
    try {
      const { sentimentBinaryAdminRoutesPlugin } = await import('./modules/sentiment-ml/binary/index.js');
      await fastify.register(sentimentBinaryAdminRoutesPlugin);
      console.log('[BOOT] Sentiment Binary ML routes registered (BLOCK 8)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Binary ML:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/binary' });

  // Block 9: Sentiment Shadow Mode (24H only)
  app.register(async (fastify) => {
    const datasetEnabled = process.env.SENTIMENT_DATASET_ENABLED === 'true';
    
    if (!datasetEnabled) {
      console.log('[BOOT] Sentiment Shadow Mode disabled (dataset not enabled)');
      return;
    }
    
    try {
      const { sentimentShadowRoutesPlugin } = await import('./modules/sentiment-ml/shadow/index.js');
      await fastify.register(sentimentShadowRoutesPlugin);
      console.log('[BOOT] Sentiment Shadow Mode routes registered (BLOCK 9)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Shadow Mode:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/shadow' });

  // Sentiment ML Performance (equity, metrics)
  app.register(async (fastify) => {
    const datasetEnabled = process.env.SENTIMENT_DATASET_ENABLED === 'true';
    
    if (!datasetEnabled) {
      console.log('[BOOT] Sentiment ML Perf disabled (dataset not enabled)');
      return;
    }
    
    try {
      const { sentimentMlPerfRoutesPlugin } = await import('./modules/sentiment-ml/perf/index.js');
      await fastify.register(sentimentMlPerfRoutesPlugin);
      console.log('[BOOT] Sentiment ML Performance routes registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment ML Perf:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/perf' });

  // BLOCK 1 HARDENING: Sentiment Operations & Monitoring
  app.register(async (fastify) => {
    try {
      const sentimentOpsRoutes = await import('./modules/sentiment-ml/ops/sentiment-ops.routes.js');
      await fastify.register(sentimentOpsRoutes.default);
      console.log('[BOOT] Sentiment Ops routes registered (BLOCK 1 Hardening)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Ops:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/ops' });

  // BLOCK 5: Sentiment Lifecycle (Promotion/Rollback)
  app.register(async (fastify) => {
    try {
      const lifecycleRoutes = await import('./modules/sentiment-ml/lifecycle/sentiment_lifecycle.routes.js');
      await fastify.register(lifecycleRoutes.default);
      console.log('[BOOT] Sentiment Lifecycle routes registered (BLOCK 5)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Lifecycle:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/lifecycle' });

  // BLOCK 6: Sentiment Capital & Risk Layer
  app.register(async (fastify) => {
    try {
      const riskRoutes = await import('./modules/sentiment-ml/risk/sent_risk.routes.js');
      await fastify.register(riskRoutes.default);
      console.log('[BOOT] Sentiment Risk routes registered (BLOCK 6)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Risk:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/risk' });

  // BLOCK 7: Sentiment Simulation Layer
  app.register(async (fastify) => {
    try {
      const simRoutes = await import('./modules/sentiment-ml/simulation/sentiment_sim.routes.js');
      await fastify.register(simRoutes.default);
      console.log('[BOOT] Sentiment Simulation routes registered (BLOCK 7)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Simulation:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/sim' });

  // BLOCK 10: Sentiment Guards & Drift Monitor
  app.register(async (fastify) => {
    try {
      const guardRoutes = await import('./modules/sentiment-ml/guards/sentiment_guard.routes.js');
      await fastify.register(guardRoutes.default);
      console.log('[BOOT] Sentiment Guard routes registered (BLOCK 10)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Guards:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/guards' });

  // BLOCK S1: Sentiment Unified Reliability Index
  app.register(async (fastify) => {
    try {
      const reliabilityRoutes = await import('./modules/sentiment-ml/reliability/sentiment-reliability.routes.js');
      await fastify.register(reliabilityRoutes.default);
      console.log('[BOOT] Sentiment Reliability routes registered (BLOCK S1)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Reliability:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/reliability' });

  // BLOCK S2: Sentiment Drift Baseline Versioning
  app.register(async (fastify) => {
    try {
      const baselineRoutes = await import('./modules/sentiment-ml/drift/sentiment-drift-baseline.routes.js');
      await fastify.register(baselineRoutes.default);
      console.log('[BOOT] Sentiment Drift Baseline routes registered (BLOCK S2)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Drift Baseline:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/drift/baseline' });

  // BLOCK S3: Sentiment Drift Stabilizer (EMA + Persistence)
  app.register(async (fastify) => {
    try {
      const stabilizerRoutes = await import('./modules/sentiment-ml/drift/sentiment-drift-stabilizer.routes.js');
      await fastify.register(stabilizerRoutes.default);
      console.log('[BOOT] Sentiment Drift Stabilizer routes registered (BLOCK S3)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Drift Stabilizer:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/drift/stabilizer' });

  // BLOCK S4: Sentiment Capital Gates (Lifecycle Integration)
  app.register(async (fastify) => {
    try {
      const capitalRoutes = await import('./modules/sentiment-ml/lifecycle/sentiment_capital.routes.js');
      await fastify.register(capitalRoutes.default);
      console.log('[BOOT] Sentiment Capital routes registered (BLOCK S4)');
    } catch (err) {
      console.error('[BOOT] Failed to register Sentiment Capital routes:', err);
    }
  }, { prefix: '/api/admin/sentiment-ml/capital' });

  // INGESTION LAYER: Universal multi-source ingestion pipeline
  app.register(async (fastify) => {
    try {
      const { registerIngestionModule } = await import('./modules/ingestion/index.js');
      await registerIngestionModule(fastify);
      console.log('[BOOT] Ingestion module registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Ingestion module:', err);
    }
  }, { prefix: '/api/admin/ingestion' });

  // NEWS CONTROL LAYER: Admin API for news source management and health monitoring
  app.register(async (fastify) => {
    try {
      const { registerNewsControlModule } = await import('./modules/news-control/index.js');
      await registerNewsControlModule(fastify);
      console.log('[BOOT] News Control module registered');
    } catch (err) {
      console.error('[BOOT] Failed to register News Control module:', err);
    }
  }, { prefix: '/api/admin/news' });

  // NEWS INTELLIGENCE LAYER: Clustering, scoring, feed API (NO AI)
  app.register(async (fastify) => {
    try {
      const { registerNewsIntelligenceModule } = await import('./modules/news-intelligence/index.js');
      await registerNewsIntelligenceModule(fastify);
      console.log('[BOOT] News Intelligence module registered');
    } catch (err) {
      console.error('[BOOT] Failed to register News Intelligence module:', err);
    }
  }, { prefix: '/api/news' });

  // F1/F2: Shared Admin (Manifests + Evidence Store)
  app.register(async (fastify) => {
    try {
      const sharedRoutes = await import('./modules/shared/shared-admin.routes.js');
      await fastify.register(sharedRoutes.default);
      console.log('[BOOT] Shared Admin routes registered (F1/F2)');
    } catch (err) {
      console.error('[BOOT] Failed to register Shared Admin routes:', err);
    }
  }, { prefix: '/api/admin/modules' });

  // Register Runtime Control Admin (S4.ADM)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering runtime control admin module...');
    try {
      const runtimeControlRoutes = await import('./modules/admin/runtime-control.routes.js');
      await runtimeControlRoutes.default(fastify);
      console.log('[BOOT] Runtime control admin module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register runtime control admin module:', err);
    }
  });

  // Register Price Layer (S5.2)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering price layer module (S5.2)...');
    try {
      const { priceLayerRoutes } = await import('./modules/price-layer/index.js');
      await priceLayerRoutes(fastify);
      console.log('[BOOT] Price layer module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register price layer module:', err);
    }
    
    // S5.6.H — Historical Replay Module
    try {
      const { registerReplayRoutes } = await import('./modules/replay/index.js');
      await registerReplayRoutes(fastify);
      console.log('[BOOT] Replay module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register replay module:', err);
    }
  });

  // S10 — Exchange Intelligence Module
  app.register(async (fastify) => {
    console.log('[BOOT] Registering S10 Exchange module...');
    try {
      const { registerExchangeModule } = await import('./modules/exchange/index.js');
      await registerExchangeModule(fastify);
      console.log('[BOOT] S10 Exchange module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register S10 Exchange module:', err);
    }
  });

  // News Intelligence Module
  app.register(async (fastify) => {
    console.log('[BOOT] Registering News Intelligence module...');
    try {
      const { registerNewsIntelligenceModule } = await import('./modules/news-intelligence/index.js');
      await registerNewsIntelligenceModule(fastify);
      console.log('[BOOT] News Intelligence module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register News Intelligence module:', err);
    }
  });

  // Push Engine Module (L2 Retention) — admin-only, MOCK delivery by default
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Push Engine module (admin)...');
    try {
      const { registerPushEngineModule } = await import('./modules/push_engine/index.js');
      await registerPushEngineModule(fastify);
      console.log('[BOOT] Push Engine admin routes registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Push Engine module:', err);
    }
  }, { prefix: '/api/push' });

  // Signal of the Moment — public endpoint for Expo HomeScreen hero card
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Signals public routes...');
    try {
      const { registerSignalPublicRoutes } = await import('./core/notifications/signal.routes.js');
      await registerSignalPublicRoutes(fastify);
      console.log('[BOOT] Signals public routes registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Signals routes:', err);
    }
  }, { prefix: '/api/signals' });


  // Phase 2 — Observability Module (Transparency & Diagnostics)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Phase 2 Observability module...');
    try {
      const { registerObservabilityRoutes } = await import('./modules/observability/index.js');
      await registerObservabilityRoutes(fastify);
      console.log('[BOOT] Phase 2 Observability module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Observability module:', err);
    }
  });

  // Phase 3 — ML Confidence Calibration Module
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Phase 3 ML module...');
    try {
      const { registerMlRoutes } = await import('./modules/ml/index.js');
      await registerMlRoutes(fastify);
      console.log('[BOOT] Phase 3 ML module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register ML module:', err);
    }
  });

  // Phase 4 — Final Decision Module (Buy/Sell/Avoid)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Phase 4 Decision module...');
    try {
      const { registerDecisionRoutes } = await import('./modules/finalDecision/index.js');
      await registerDecisionRoutes(fastify);
      console.log('[BOOT] Phase 4 Decision module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Decision module:', err);
    }
  });

  // S10.7 — Exchange ML Module
  app.register(async (fastify) => {
    console.log('[BOOT] Registering S10.7 Exchange ML module...');
    try {
      const { mlRoutes, mlShadowRoutes, mlopsPromotionRoutes, step3PromotionRoutes } = await import('./modules/exchange-ml/index.js');
      await fastify.register(mlRoutes);
      await fastify.register(mlShadowRoutes);
      await fastify.register(mlopsPromotionRoutes);
      await fastify.register(step3PromotionRoutes);
      console.log('[BOOT] S10.7 Exchange ML module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register S10.7 Exchange ML module:', err);
    }
  });

  // EX-S1: Exchange Reliability (URI)
  app.register(async (fastify) => {
    try {
      const reliabilityRoutes = await import('./modules/exchange-ml/reliability/exchange-reliability.routes.js');
      await fastify.register(reliabilityRoutes.default);
      console.log('[BOOT] Exchange Reliability routes registered (EX-S1)');
    } catch (err) {
      console.error('[BOOT] Failed to register Exchange Reliability:', err);
    }
  }, { prefix: '/api/admin/exchange-ml/reliability' });

  // EX-S2/S3: Exchange Drift (Baseline + Stabilizer)
  app.register(async (fastify) => {
    try {
      const driftRoutes = await import('./modules/exchange-ml/drift/exchange-drift.routes.js');
      await fastify.register(driftRoutes.default);
      console.log('[BOOT] Exchange Drift routes registered (EX-S2/S3)');
    } catch (err) {
      console.error('[BOOT] Failed to register Exchange Drift:', err);
    }
  }, { prefix: '/api/admin/exchange-ml/drift' });

  // EX-S4: Exchange Capital Gates
  app.register(async (fastify) => {
    try {
      const capitalRoutes = await import('./modules/exchange-ml/lifecycle/exchange_capital.routes.js');
      await fastify.register(capitalRoutes.default);
      console.log('[BOOT] Exchange Capital routes registered (EX-S4)');
    } catch (err) {
      console.error('[BOOT] Failed to register Exchange Capital:', err);
    }
  }, { prefix: '/api/admin/exchange-ml/capital' });

  // S10.8 — Meta-Brain (Exchange → Meta-Brain Hook)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering S10.8 Meta-Brain module...');
    try {
      const { metaBrainRoutes } = await import('./modules/meta-brain/index.js');
      await fastify.register(metaBrainRoutes);
      console.log('[BOOT] S10.8 Meta-Brain module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register S10.8 Meta-Brain module:', err);
    }
  });

  // C1 — Fusion Layer (Exchange × Sentiment Alignment)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering C1 Fusion module...');
    try {
      const { alignmentRoutes } = await import('./modules/fusion/index.js');
      await fastify.register(alignmentRoutes, { prefix: '/api/v10/fusion' });
      console.log('[BOOT] C1 Fusion module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register C1 Fusion module:', err);
    }
  });

  // C2.1 — Onchain Data Foundation (Legacy)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering C2.1 Onchain module...');
    try {
      const { onchainRoutes } = await import('./modules/onchain/index.js');
      await fastify.register(onchainRoutes, { prefix: '/api/v10/onchain' });
      console.log('[BOOT] C2.1 Onchain module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register C2.1 Onchain module:', err);
    }
  });

  // OnChain V2 — Isolated Module (Feature Flagged)
  app.register(async (fastify) => {
    const onchainV2Enabled = process.env.ONCHAIN_V2_ENABLED === 'true';
    console.log(`[BOOT] ONCHAIN_V2_ENABLED=${onchainV2Enabled}`);
    
    if (!onchainV2Enabled) {
      console.log('[BOOT] OnChain V2 module disabled');
      return;
    }
    
    try {
      const { onchainV2Routes, initializeOnchainProvider } = await import('./modules/onchain_v2/index.js');
      
      // Initialize provider
      await initializeOnchainProvider();
      
      // Register routes
      await fastify.register(onchainV2Routes, { prefix: '/api/v10/onchain-v2' });
      
      console.log('[BOOT] OnChain V2 module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register OnChain V2 module:', err);
    }
  });

  // C2.2 — Exchange × On-chain Validation
  app.register(async (fastify) => {
    console.log('[BOOT] Registering C2.2 Validation module...');
    try {
      const { validationRoutes } = await import('./modules/validation/index.js');
      await fastify.register(validationRoutes, { prefix: '/api/v10/validation' });
      console.log('[BOOT] C2.2 Validation module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register C2.2 Validation module:', err);
    }
  });

  // On-Chain Lite — Infura + DefiLlama data provider
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Onchain-Lite module...');
    try {
      const { onchainLiteRoutes } = await import('./modules/onchain-lite/onchain-lite.routes.js');
      await onchainLiteRoutes(fastify);
      console.log('[BOOT] Onchain-Lite module registered at /api/onchain/*');
    } catch (err) {
      console.error('[BOOT] Failed to register Onchain-Lite module:', err);
    }
  });

  // Admin Indexer Control Panel
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Admin Indexer routes...');
    try {
      const { adminIndexerRoutes } = await import('./core/admin/admin.indexer.routes.js');
      await fastify.register(adminIndexerRoutes, { prefix: '/api/admin/indexer' });
      console.log('[BOOT] Admin Indexer routes registered at /api/admin/indexer/*');
    } catch (err) {
      console.error('[BOOT] Failed to register Admin Indexer routes:', err);
    }
  });

  // C3 — Meta-Brain v2 Signal Layer (Phase 1)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Meta-Brain V2 Signal Layer...');
    try {
      const metaBrainV2Routes = (await import('./modules/meta-brain-v2/routes/meta-brain-v2.routes.js')).default;
      await fastify.register(metaBrainV2Routes, { prefix: '/api/meta-brain-v2' });
      console.log('[BOOT] Meta-Brain V2 Signal Layer registered at /api/meta-brain-v2');
    } catch (err) {
      console.error('[BOOT] Failed to register Meta-Brain V2:', err);
    }
  });

  // C3.1 — Data Health Check (CRITICAL MONITORING)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Data Health Check...');
    try {
      const { dataHealthRoutes } = await import('./core/system/data-health.routes.js');
      await fastify.register(dataHealthRoutes, { prefix: '/api/system' });
      console.log('[BOOT] Data Health Check registered at /api/system/data-health');
    } catch (err) {
      console.error('[BOOT] Failed to register Data Health Check:', err);
    }
  });

  // Phase 1.2 — Market Module (Search + Asset Resolver)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Phase 1.2 Market module...');
    try {
      const { marketRoutes } = await import('./modules/market/index.js');
      await fastify.register(marketRoutes, { prefix: '/api/v10/market' });
      console.log('[BOOT] Phase 1.2 Market module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Market module:', err);
    }
  });

  // Phase 2.1 — Features Module (Feature Snapshot Builder)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Phase 2.1 Features module...');
    try {
      const { featureRoutes } = await import('./modules/features/index.js');
      await fastify.register(featureRoutes, { prefix: '/api/v10/features' });
      console.log('[BOOT] Phase 2.1 Features module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Features module:', err);
    }
  });

  // Phase 2.2 — Dataset Module (ML Dataset Builder)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Phase 2.2 Dataset module...');
    try {
      const { datasetRoutes } = await import('./modules/dataset/index.js');
      await fastify.register(datasetRoutes, { prefix: '/api/v10/dataset' });
      console.log('[BOOT] Phase 2.2 Dataset module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Dataset module:', err);
    }
  });

  // Phase 2.3 — Confidence Module (Confidence Decay Engine)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Phase 2.3 Confidence module...');
    try {
      const { confidenceRoutes } = await import('./modules/confidence/index.js');
      await fastify.register(confidenceRoutes, { prefix: '/api/v10/confidence' });
      console.log('[BOOT] Phase 2.3 Confidence module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Confidence module:', err);
    }
  });

  // Phase 1 (Prod) — Network Admin Module
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Phase 1 Network module...');
    try {
      const { networkAdminRoutes } = await import('./modules/network/index.js');
      await fastify.register(networkAdminRoutes, { prefix: '/api/v10/admin/network' });
      console.log('[BOOT] Phase 1 Network module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Network module:', err);
    }
  });

  // Phase 5 — Learning Module (Auto-Learning Loop)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Phase 5 Learning module...');
    try {
      const { registerLearningModule } = await import('./modules/learning/index.js');
      await registerLearningModule(fastify);
      console.log('[BOOT] Phase 5 Learning module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Learning module:', err);
    }
  });

  // Product Signals — Alerts Module (Telegram/Discord notifications)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Alerts module...');
    try {
      const { registerAlertRoutes, alertDispatcher } = await import('./modules/alerts/index.js');
      await registerAlertRoutes(fastify);
      await alertDispatcher.init();
      console.log('[BOOT] Alerts module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Alerts module:', err);
    }
  });

  // Product Signals — Snapshot Module (Share Links)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Snapshot module...');
    try {
      const { registerSnapshotRoutes } = await import('./modules/snapshot/index.js');
      await registerSnapshotRoutes(fastify);
      console.log('[BOOT] Snapshot module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Snapshot module:', err);
    }
  });

  // FOMO Alerts Module (Telegram notifications)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering FOMO Alerts module...');
    try {
      const { registerFomoAlertRoutes, fomoAlertEngine } = await import('./modules/fomo-alerts/index.js');
      await registerFomoAlertRoutes(fastify);
      await fomoAlertEngine.init();
      console.log('[BOOT] FOMO Alerts module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register FOMO Alerts module:', err);
    }
  });

  // Macro Context Module (Market State Anchor)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Macro Context module...');
    try {
      const { macroRoutes, startMacroAlertMonitor } = await import('./modules/macro/index.js');
      await fastify.register(macroRoutes, { prefix: '/api/v10/macro' });
      
      // Start macro alert monitoring
      startMacroAlertMonitor();
      
      console.log('[BOOT] Macro Context module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Macro Context module:', err);
    }
  });

  // Macro Intelligence Module (Market Regime Engine)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Macro Intelligence module...');
    try {
      const { macroIntelRoutes } = await import('./modules/macro-intel/index.js');
      await fastify.register(macroIntelRoutes, { prefix: '/api/v10/macro-intel' });
      console.log('[BOOT] Macro Intelligence module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Macro Intelligence module:', err);
    }
  });

  // Market Expectation Module (P1 - Expectation → Outcome → Feedback Loop)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Market Expectation module...');
    try {
      const { registerMarketExpectationRoutes } = await import('./modules/market-expectation/index.js');
      await registerMarketExpectationRoutes(fastify);
      console.log('[BOOT] Market Expectation module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Market Expectation module:', err);
    }
  });

  // Assets Module (Canonical Asset + Multi-Venue Truth Layer)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Assets module...');
    try {
      const { registerAssetsRoutes } = await import('./modules/assets/index.js');
      await registerAssetsRoutes(fastify);
      console.log('[BOOT] Assets module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Assets module:', err);
    }
  });

  // Central Chart Module
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Chart module...');
    try {
      const { chartRoutes } = await import('./modules/chart/index.js');
      await fastify.register(chartRoutes);
      console.log('[BOOT] Chart module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Chart module:', err);
    }
  });

  // Price vs Expectation Module (композитный endpoint для графика)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Price vs Expectation module...');
    try {
      const { priceVsExpectationRoutes } = await import('./modules/chart/price_vs_expectation.routes.js');
      await fastify.register(priceVsExpectationRoutes);
      console.log('[BOOT] Price vs Expectation module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Price vs Expectation module:', err);
    }
  });

  // Price vs Expectation V2 Module (new forecast-based system)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Price vs Expectation V2 module...');
    try {
      const { priceVsExpectationV2Routes } = await import('./modules/chart/price_vs_expectation_v2.routes.js');
      await fastify.register(priceVsExpectationV2Routes);
      console.log('[BOOT] Price vs Expectation V2 module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Price vs Expectation V2 module:', err);
    }
  });

  // Price vs Expectation V3 Module (Verdict Engine adapter)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Price vs Expectation V3 (Verdict Adapter) module...');
    try {
      const { verdictAdapterRoutes } = await import('./modules/chart/verdict_adapter.routes.js');
      await fastify.register(verdictAdapterRoutes);
      console.log('[BOOT] Price vs Expectation V3 module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Price vs Expectation V3 module:', err);
    }
  });

  // Candles API (TradingView-like OHLC data)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Candles API module...');
    try {
      const { registerCandlesRoutes } = await import('./modules/market/chart/candles.routes.js');
      await registerCandlesRoutes(fastify);
      console.log('[BOOT] Candles API module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Candles API module:', err);
    }
  });

  // Exchange Learning Health Module (admin debug)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Exchange Learning Health module...');
    try {
      const { exchangeLearningHealthRoutes } = await import('./modules/exchange/admin/exchange_learning_health.routes.js');
      await fastify.register(exchangeLearningHealthRoutes);
      console.log('[BOOT] Exchange Learning Health module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Exchange Learning Health module:', err);
    }
  });

  // Alt Scanner Module (Cross-sectional Altcoin Analysis)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Alt Scanner module...');
    try {
      const { registerAltScannerRoutes } = await import('./modules/exchange-alt/index.js');
      await registerAltScannerRoutes(fastify);
      console.log('[BOOT] Alt Scanner module registered successfully');
    } catch (err) {
      console.error('[BOOT] Failed to register Alt Scanner module:', err);
    }
  });

  // P1.1 — Verdict Engine Module (Cross-Horizon Ensemble Decision Engine)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Verdict Engine module...');
    try {
      const { VerdictEngineImpl, IntelligenceMetaBrainAdapter, ShadowHealthAdapter } = await import('./modules/verdict/index.js');
      const { CredibilityService } = await import('./modules/evolution/index.js');
      const verdictRoutes = await import('./modules/verdict/api/verdict.routes.js');
      
      // Create services
      const credibilityService = new CredibilityService();
      
      // P2: Real MetaBrain adapter (connects to /modules/intelligence/)
      const metaBrain = new IntelligenceMetaBrainAdapter();
      
      // P2: Real Health adapter (connects to ML Shadow Monitor)
      const healthPort = new ShadowHealthAdapter();
      
      // Create engine with all real adapters:
      // - MetaBrain: applies invariants, risk caps, macro regime
      // - Calibration: applies credibility-based confidence modifiers
      // - Health: applies shadow monitor damping
      const engine = new VerdictEngineImpl(
        metaBrain,
        {
          getConfidenceModifier: (args: any) => credibilityService.getConfidenceModifier(args),
        },
        healthPort
      );
      
      // Register routes
      await verdictRoutes.default(fastify, { engine });
      
      console.log('[BOOT] Verdict Engine module registered with real MetaBrain + ShadowHealth');
    } catch (err) {
      console.error('[BOOT] Failed to register Verdict Engine module:', err);
    }
  });

  // P1.2 — Evolution Module (Self-Learning Feedback Loop)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Evolution module...');
    try {
      const { OutcomeService, CredibilityService, RealPriceAdapter, startEvolutionCron } = await import('./modules/evolution/index.js');
      const evolutionRoutes = await import('./modules/evolution/api/evolution.routes.js');
      
      // Create services
      const credibilityService = new CredibilityService();
      
      // P1: Real PricePort using price.service.ts
      // Single source of truth for: chart, outcomes, forecast baseline, evolution
      const pricePort = new RealPriceAdapter();
      
      const outcomeService = new OutcomeService(pricePort, credibilityService);
      
      // Register routes with pricePort for testing endpoint
      await evolutionRoutes.default(fastify, { outcomeService, credibilityService, pricePort });
      
      // Start cron job for automatic outcome evaluation — skip in MINIMAL_BOOT
      if (process.env.MINIMAL_BOOT !== '1') {
        try {
          startEvolutionCron(outcomeService);
        } catch (cronErr) {
          console.warn('[BOOT] Evolution cron failed to start (node-cron might not be installed):', cronErr);
        }
      } else {
        console.log('[BOOT] MINIMAL_BOOT — Evolution cron skipped');
      }
      
      console.log('[BOOT] Evolution module registered with RealPriceAdapter');
    } catch (err) {
      console.error('[BOOT] Failed to register Evolution module:', err);
    }
  });

  // P3: Smart Caching Layer — Verdict V4 Fast API + Cache Admin + Jobs
  app.register(async (fastify) => {
    console.log('[BOOT] Registering P3 Smart Caching Layer...');
    try {
      // V4 Fast API endpoint
      const { verdictV4Routes } = await import('./modules/verdict/routes/verdict_v4.routes.js');
      await verdictV4Routes(fastify);
      
      // Cache Admin routes
      const { verdictCacheAdminRoutes } = await import('./modules/verdict/routes/verdict_cache_admin.routes.js');
      await verdictCacheAdminRoutes(fastify);
      
      // Start Heavy Verdict warmup job (Block 7) — skip in MINIMAL_BOOT
      if (process.env.MINIMAL_BOOT !== '1') {
        const { heavyVerdictJob } = await import('./modules/verdict/jobs/heavy-verdict.job.js');
        heavyVerdictJob.start();
        
        // Start Heavy Verdict refresh job (Block 12: TTL Auto-Refresh)
        const { heavyVerdictRefreshJob } = await import('./modules/verdict/jobs/heavy-verdict.refresh.job.js');
        heavyVerdictRefreshJob.start();
      } else {
        console.log('[BOOT] MINIMAL_BOOT — Heavy Verdict jobs skipped');
      }
      
      console.log('[BOOT] P3 Smart Caching Layer registered (V4 API + Cache Admin + Warmup Job + Refresh Job)');
    } catch (err) {
      console.error('[BOOT] Failed to register P3 Smart Caching Layer:', err);
    }
  });

  // BLOCK B: Multi-Asset Ranking (Top Conviction)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering BLOCK B: Rankings API...');
    try {
      const { rankingsRoutes } = await import('./modules/market/routes/rankings.routes.js');
      await rankingsRoutes(fastify);
      console.log('[BOOT] BLOCK B: Rankings API registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Rankings API:', err);
    }
  });

  // Symbols API (Dynamic Asset Search)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Symbols API...');
    try {
      const { symbolsRoutes } = await import('./modules/market/routes/symbols.routes.js');
      await symbolsRoutes(fastify);
      console.log('[BOOT] Symbols API registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Symbols API:', err);
    }
  });

  // BLOCK F1: Forecast Series (Time-Series Forecast Persistence)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering BLOCK F1: Forecast Series...');
    try {
      const { getDb } = await import('./db/mongodb.js');
      const { registerForecastSeriesRoutes, registerForecastSnapshotJob, registerForecastOnlyRoutes } = await import('./modules/forecast-series/index.js');
      const { heavyComputeService } = await import('./modules/verdict/runtime/heavy-compute.service.js');
      
      const db = getDb();
      
      // Adapter function to convert heavyComputeService output to VerdictLike
      const getVerdictV4 = async (args: { symbol: string; horizon: '1D' | '7D' | '30D' }) => {
        const payload = await heavyComputeService.compute(args.symbol, args.horizon);
        if (!payload.verdict) return null;
        
        // Extract price data
        const fromPrice = payload.layers?.snapshot?.price || 0;
        
        return {
          symbol: args.symbol,
          horizon: args.horizon,
          fromPrice,
          expectedMovePct: payload.verdict.expectedMovePct || payload.verdict.expectedReturn || 0,
          confidence: payload.verdict.confidenceAdjusted || payload.verdict.confidence || 0.5,
          explain: {
            overlays: {
              volatilityPct: payload.layers?.features?.volatility_1d,
            },
            meta: {
              verdictId: `${args.symbol}-${args.horizon}-${Date.now()}`,
            },
          },
        };
      };
      
      // V3.2: Adapter for forecast-only routes (per layer)
      const getVerdictForLayer = async (args: { symbol: string; horizon: '1D' | '7D' | '30D'; layer?: string }) => {
        const payload = await heavyComputeService.compute(args.symbol, args.horizon);
        
        if (!payload.verdict) return null;
        
        // Get current price from snapshot
        const lastPrice = payload.layers?.snapshot?.price || 0;
        
        // Find candidate for requested horizon (has correct expectedReturn!)
        const candidates = payload.candidates || [];
        const horizonCandidate = candidates.find((c: any) => c.horizon === args.horizon);
        
        let expectedMovePct = 0;
        let confidence = 0.5;
        
        if (horizonCandidate) {
          // Use candidate's expectedReturn (it's already in decimal form, e.g. 0.098 = 9.8%)
          expectedMovePct = horizonCandidate.expectedReturn || 0;
          confidence = horizonCandidate.confidence || 0.5;
          
          console.log(`[getVerdictForLayer] ${args.symbol}/${args.horizon}: Using candidate expectedReturn=${expectedMovePct} (${(expectedMovePct * 100).toFixed(2)}%)`);
        } else {
          // Fallback to verdict data
          const rawReturn = payload.verdict.expectedReturn ?? 0;
          expectedMovePct = rawReturn;
          confidence = payload.verdict.confidence ?? 0.5;
          
          console.log(`[getVerdictForLayer] ${args.symbol}/${args.horizon}: FALLBACK verdict expectedReturn=${expectedMovePct}`);
        }
        
        return {
          fromPrice: lastPrice,
          expectedMovePct,
          confidence,
        };
      };
      
      // Register routes
      await registerForecastSeriesRoutes(fastify, { db, getVerdictV4 });
      
      // V3.4: Import snapshot creator for outcome tracking
      let createSnapshot: ((params: any) => Promise<string>) | undefined;
      try {
        const { getOutcomeTrackerService } = await import('./modules/forecast-series/outcome-tracking/index.js');
        const { getCurrentPrice } = await import('./modules/chart/services/price.service.js');
        
        const priceProvider = {
          getCurrentPrice: async (symbol: string) => getCurrentPrice(symbol),
          getHistoricalPrice: async (symbol: string, _timestamp: Date) => getCurrentPrice(symbol),
        };
        
        const outcomeService = getOutcomeTrackerService(db, priceProvider);
        createSnapshot = (params: any) => outcomeService.createSnapshot(params);
        console.log('[BOOT] V3.4: Snapshot creator initialized');
      } catch (snapshotErr: any) {
        console.warn('[BOOT] V3.4: Snapshot creator not available:', snapshotErr.message);
      }
      
      // V3.2: Register forecast-only routes (Brownian Bridge) + V3.4: Snapshot creation
      await registerForecastOnlyRoutes(fastify, { db, getVerdictForLayer, createSnapshot });
      
      // Register daily snapshot job (disabled by default, enable when ready)
      registerForecastSnapshotJob(fastify, {
        db,
        getVerdictV4,
        config: {
          enabled: process.env.FORECAST_SNAPSHOT_JOB === '1',
          runOnStart: false,
          intervalMs: 24 * 60 * 60 * 1000, // 24h
        },
      });
      
      console.log('[BOOT] BLOCK F1: Forecast Series registered (routes + job + forecast-only)');
    } catch (err) {
      console.error('[BOOT] Failed to register Forecast Series:', err);
    }
  });

  // V3.4: Outcome Tracking (WIN/LOSS tracking for forecasts)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering V3.4: Outcome Tracking...');
    try {
      const { getDb } = await import('./db/mongodb.js');
      const { 
        registerForecastOutcomeRoutes, 
        registerOutcomeTrackerJob,
      } = await import('./modules/forecast-series/index.js');
      const { getCurrentPrice } = await import('./modules/chart/services/price.service.js');
      
      const db = getDb();
      
      // Adapter for price provider — getCurrentPrice now has MongoDB fallback built-in
      const priceProvider = {
        getCurrentPrice: async (symbol: string) => getCurrentPrice(symbol),
        getHistoricalPrice: async (symbol: string, _targetDate: Date) => getCurrentPrice(symbol),
      };
      
      // Register outcome routes
      await registerForecastOutcomeRoutes(fastify, { db, priceProvider });
      
      // V3.10-STABLE: Register snapshots history routes (for Ghost Mode overlay)
      const { registerForecastSnapshotsHistoryRoutes } = await import('./modules/forecast-series/forecast-snapshots-history.routes.js');
      await registerForecastSnapshotsHistoryRoutes(fastify, { db });
      
      // Register outcome tracker job (checks pending snapshots)
      const outcomeJobEnabled = process.env.OUTCOME_TRACKER_JOB === '1';
      if (outcomeJobEnabled) {
        registerOutcomeTrackerJob(db, priceProvider, {
          enabled: true,
          intervalMs: 5 * 60 * 1000, // 5 minutes
        });
      }
      
      console.log('[BOOT] V3.4: Outcome Tracking + V3.10 Snapshots History registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Outcome Tracking:', err);
    }
  });

  // V3.5-V3.7: Quality + Drift Engine
  app.register(async (fastify) => {
    console.log('[BOOT] Registering V3.5-V3.7: Quality + Drift Engine...');
    try {
      const { getDb } = await import('./db/mongodb.js');
      const { 
        registerForecastQualityRoutes,
        registerForecastDriftRoutes,
      } = await import('./modules/forecast-series/index.js');
      
      const db = getDb();
      
      // V3.5-V3.6: Quality Badge API
      await registerForecastQualityRoutes(fastify, { db });
      
      // V3.7: Drift Detector API
      await registerForecastDriftRoutes(fastify, { db });
      
      console.log('[BOOT] V3.5-V3.7: Quality + Drift Engine registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Quality + Drift Engine:', err);
    }
  });

  // Forecast Performance Table (joins snapshots + outcomes for UI)
  app.register(async (fastify) => {
    console.log('[BOOT] Registering Forecast Performance Table...');
    try {
      const { getDb } = await import('./db/mongodb.js');
      const { registerForecastTableRoutes } = await import('./modules/forecast-series/forecast-table.routes.js');
      
      const db = getDb();
      registerForecastTableRoutes(fastify, db);
      
      console.log('[BOOT] Forecast Performance Table registered');
    } catch (err) {
      console.error('[BOOT] Failed to register Forecast Performance Table:', err);
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // LAYER 2: Connections Module Proxy
  // ═══════════════════════════════════════════════════════════════
  // Connections is a STANDALONE service (port 8003).
  // These routes proxy requests through main API for frontend access.
  // READ-ONLY - does NOT affect forecast pipeline.
  app.register(async (fastify) => {
    const connectionsEnabled = process.env.CONNECTIONS_ENABLED === 'true';
    if (!connectionsEnabled) {
      console.log('[BOOT] Connections Proxy DISABLED (CONNECTIONS_ENABLED != true)');
      return;
    }
    
    console.log('[BOOT] Registering Connections Proxy (Layer 2)...');
    try {
      const { registerConnectionsProxyRoutes, registerConnectionsAdminRoutes } = await import('./modules/connections-proxy/index.js');
      await fastify.register(registerConnectionsProxyRoutes, { prefix: '/api/connections' });
      await fastify.register(registerConnectionsAdminRoutes, { prefix: '/api/admin/connections' });
      console.log('[BOOT] Connections Proxy registered at /api/connections/*');
      console.log('[BOOT] Connections Admin registered at /api/admin/connections/*');
    } catch (err) {
      console.error('[BOOT] Failed to register Connections Proxy:', err);
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // LAYER 2: Narratives Module (Block 16-18) 
  // ═══════════════════════════════════════════════════════════════
  // Narrative Intelligence - tracks crypto narratives lifecycle
  // SEEDING → IGNITION → EXPANSION → DECAY
  app.register(async (fastify) => {
    const connectionsEnabled = process.env.CONNECTIONS_ENABLED === 'true';
    if (!connectionsEnabled) {
      console.log('[BOOT] Narratives Module DISABLED (CONNECTIONS_ENABLED != true)');
      return;
    }
    
    console.log('[BOOT] Registering Narratives Module (Block 16-18)...');
    try {
      const { getDb } = await import('./db/mongodb.js');
      const { registerNarrativeRoutes } = await import('./modules/narratives/narrative.routes.js');
      const db = getDb();
      await registerNarrativeRoutes(fastify, db);
      console.log('[BOOT] Narratives Module registered at /api/narratives/*');
    } catch (err) {
      console.error('[BOOT] Failed to register Narratives Module:', err);
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // V4 Exchange Auto-Learning Loop (PR1+)
  // ═══════════════════════════════════════════════════════════════
  app.register(async (fastify) => {
    const mlEnabled = process.env.EXCHANGE_ML_ENABLED === 'true';
    if (!mlEnabled) {
      console.log('[BOOT] Exchange ML V4 DISABLED (EXCHANGE_ML_ENABLED != true)');
      return;
    }
    
    console.log('[BOOT] Registering Exchange ML V4 Admin module...');
    try {
      const { exchangeMLAdminRoutes } = await import('./modules/exchange-ml/admin/index.js');
      await fastify.register(exchangeMLAdminRoutes);
      console.log('[BOOT] Exchange ML V4 Admin registered at /api/admin/exchange-ml/*');
      
      // Register Snapshot public routes (BLOCK 1)
      const { exchangeSnapshotPublicRoutes, exchangeSnapshotAdminRoutes } = await import('./modules/exchange-ml/snapshots/exchange_snapshot.routes.js');
      await fastify.register(exchangeSnapshotPublicRoutes);
      await fastify.register(exchangeSnapshotAdminRoutes);
      console.log('[BOOT] Exchange Snapshot routes registered at /api/market/exchange/snapshots/*');
      
      // Register Forecast Segment routes (BLOCK 4 - Legacy)
      const { forecastSegmentPublicRoutes, forecastSegmentAdminRoutes } = await import('./modules/exchange-ml/segments/forecast_segment.routes.js');
      await fastify.register(forecastSegmentPublicRoutes);
      await fastify.register(forecastSegmentAdminRoutes);
      console.log('[BOOT] Forecast Segment routes registered at /api/market/forecast-segments/*');
      
      // ═══════════════════════════════════════════════════════════════
      // BLOCK 5-7: Model Iteration Engine (NEW Segment System)
      // ═══════════════════════════════════════════════════════════════
      const { exchSegmentsPublicRoutes, exchSegmentsAdminRoutes } = await import('./modules/exchange-ml/iteration/exch_segments.routes.js');
      await fastify.register(exchSegmentsPublicRoutes);
      await fastify.register(exchSegmentsAdminRoutes);
      console.log('[BOOT] Exchange Segments (BLOCK 5) registered at /api/exchange/segments/*');
      
      // Auto-initialize indexes on startup
      const { getDb } = await import('./db/mongodb.js');
      const { getExchangeDatasetService } = await import('./modules/exchange-ml/dataset/index.js');
      const { getExchangeLabelScheduler } = await import('./modules/exchange-ml/jobs/index.js');
      const { getExchangeSnapshotService } = await import('./modules/exchange-ml/snapshots/exchange_snapshot.service.js');
      const { getForecastSegmentRepo } = await import('./modules/exchange-ml/segments/forecast_segment.repo.js');
      const { getHorizonCascadeService } = await import('./modules/exchange-ml/performance/horizon_cascade.service.js');
      const { getExchForecastSegmentService } = await import('./modules/exchange-ml/iteration/exch_forecast_segment.service.js');
      
      const db = getDb();
      await getExchangeDatasetService(db).ensureIndexes();
      await getExchangeLabelScheduler(db).ensureIndexes();
      await getExchangeSnapshotService(db).ensureIndexes();
      await getForecastSegmentRepo(db).ensureIndexes();
      await getHorizonCascadeService(db).ensureIndexes();
      await getExchForecastSegmentService(db).ensureIndexes();
      
      console.log('[BOOT] Exchange ML V4 indexes ensured (Snapshots + Segments + Cascade + Iteration)');
      
      // BLOCK 7: Start Horizon Roll Scheduler (Auto 30D roll on 7D resolution)
      if (process.env.EXCHANGE_HORIZON_ROLL_ENABLED === 'true' && process.env.MINIMAL_BOOT !== '1') {
        const { startHorizonRollScheduler } = await import('./modules/exchange-ml/iteration/exch_horizon_roll.scheduler.js');
        setTimeout(() => {
          startHorizonRollScheduler(db, {});
          console.log('[BOOT] Exchange Horizon Roll Scheduler started (BLOCK 7)');
        }, 10000);
      }
      
      // Auto-start services if dataset enabled
      if (process.env.EXCHANGE_DATASET_ENABLED === 'true' && process.env.MINIMAL_BOOT !== '1') {
        const { getExchangeFeatureBuilder } = await import('./modules/exchange-ml/dataset/index.js');
        const { getExchangeLabelWorker } = await import('./modules/exchange-ml/jobs/index.js');
        
        const scheduler = getExchangeLabelScheduler(db);
        const featureBuilder = getExchangeFeatureBuilder(db);
        
        const priceProvider = {
          getCurrentPrice: async (symbol: string) => {
            const features = await featureBuilder.buildFeatures(symbol);
            return features?.price ?? null;
          },
        };
        
        const worker = getExchangeLabelWorker(db, priceProvider);
        
        // Start services with delay to allow other modules to initialize
        setTimeout(() => {
          scheduler.start();
          worker.start();
          console.log('[BOOT] Exchange ML V4 scheduler and worker started');
        }, 5000);
      }
      
      // ═══════════════════════════════════════════════════════════════
      // Exchange ML Simulation Admin Routes
      // ═══════════════════════════════════════════════════════════════
      const { exchangeSimAdminRoutes } = await import('./modules/exchange-sim/routes/exchange_sim_admin.routes.js');
      await fastify.register(exchangeSimAdminRoutes);
      console.log('[BOOT] Exchange Simulation Admin routes registered at /api/admin/exchange-sim/*');
      
      // ═══════════════════════════════════════════════════════════════
      // Trade Performance Dashboard Routes (BLOCK 2 - v4.7.0)
      // ═══════════════════════════════════════════════════════════════
      try {
        const { registerExchangePerfRoutes } = await import('./modules/exchange-ml/perf/exchange_perf.routes.js');
        
        // Placeholder for getSimTrades - will be connected to sim storage
        const getSimTrades = async ({ days }: { days: number }) => {
          // TODO: Connect to actual simulation trade storage
          // For now, return empty array
          console.log(`[PerfRoutes] getSimTrades called for ${days} days (placeholder)`);
          return [];
        };
        
        await registerExchangePerfRoutes(fastify, { getSimTrades });
        console.log('[BOOT] Exchange Perf Dashboard routes registered at /api/admin/exchange-ml/perf/*');
      } catch (perfErr) {
        console.error('[BOOT] Failed to register Exchange Perf routes:', perfErr);
      }
      
      // ═══════════════════════════════════════════════════════════════
      // Exchange Monitor Routes (v4.8.0 - Capital Monitor Widget)
      // ═══════════════════════════════════════════════════════════════
      try {
        const { registerExchangeMonitorRoutes } = await import('./modules/exchange-ml/perf/exchange_monitor.routes.js');
        await registerExchangeMonitorRoutes(fastify);
        console.log('[BOOT] Exchange Monitor routes registered at /api/admin/exchange-ml/monitor/*');
      } catch (monitorErr) {
        console.error('[BOOT] Failed to register Exchange Monitor routes:', monitorErr);
      }
      
      // ═══════════════════════════════════════════════════════════════
      // Direction Model Admin Routes
      // ═══════════════════════════════════════════════════════════════
      try {
        const dirModule = await import('./modules/exchange-ml/dir/routes/dir.admin.routes.js');
        await fastify.register(dirModule.dirAdminRoutes);
        console.log('[BOOT] Direction Model Admin routes registered at /api/admin/exchange-dir/*');
      } catch (dirErr) {
        console.error('[BOOT] Failed to register Direction Admin routes:', dirErr);
      }
      
    } catch (err) {
      console.error('[BOOT] Failed to register Exchange ML V4 module:', err);
    }
  });

  return app;
}
