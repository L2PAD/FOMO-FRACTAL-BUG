/**
 * OnChain V2 — Routes
 * ====================
 * 
 * REST API endpoints for OnChain V2 module.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  OnchainWindow,
  OnchainHealthResponse,
  OnchainProviderStatus,
  deriveOnchainState,
} from '../core/contracts.js';
import { snapshotService } from '../core/snapshot/index.js';
import { metricsEngine } from '../core/metrics/index.js';
import { 
  getOnchainProvider, 
  getActiveProviderConfig,
  isProviderInitialized,
  resetOnchainProvider,
} from '../providers/index.js';
import { OnchainProviderHealthModel } from '../core/persistence/models.js';

// ═══════════════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════════════

async function healthHandler(
  request: FastifyRequest,
  reply: FastifyReply
): Promise<OnchainHealthResponse> {
  try {
    const provider = getOnchainProvider();
    const health = await provider.getHealth();
    
    // Update DB
    await OnchainProviderHealthModel.findOneAndUpdate(
      { providerId: health.providerId },
      health,
      { upsert: true }
    );
    
    return {
      ok: true,
      status: health.status,
      providerMode: health.providerMode,
      providers: [health],
      timestamp: Date.now(),
    };
  } catch (error) {
    console.error('[OnChain V2] Health check error:', error);
    return {
      ok: false,
      status: 'DOWN',
      providerMode: 'mock',
      providers: [],
      timestamp: Date.now(),
    };
  }
}

async function snapshotHandler(
  request: FastifyRequest<{
    Params: { symbol: string };
    Querystring: { t0?: string; window?: OnchainWindow };
  }>,
  reply: FastifyReply
) {
  try {
    const { symbol } = request.params;
    const t0 = request.query.t0 ? parseInt(request.query.t0) : undefined;
    const window = request.query.window || '1h';
    
    const result = await snapshotService.getSnapshot(symbol, t0, window);
    return result;
  } catch (error) {
    console.error('[OnChain V2] Snapshot error:', error);
    return {
      ok: false,
      snapshot: null,
      source: 'mock',
      confidence: 0,
      dataAvailable: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function latestHandler(
  request: FastifyRequest<{
    Params: { symbol: string };
    Querystring: { window?: OnchainWindow };
  }>,
  reply: FastifyReply
) {
  try {
    const { symbol } = request.params;
    const window = request.query.window || '1h';
    
    const result = await snapshotService.getLatest(symbol, window);
    return result;
  } catch (error) {
    console.error('[OnChain V2] Latest error:', error);
    return {
      ok: false,
      snapshot: null,
      source: 'mock',
      confidence: 0,
      dataAvailable: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function metricsHandler(
  request: FastifyRequest<{
    Params: { symbol: string };
    Querystring: { t0?: string; window?: OnchainWindow };
  }>,
  reply: FastifyReply
) {
  try {
    const { symbol } = request.params;
    const t0 = request.query.t0 ? parseInt(request.query.t0) : undefined;
    const window = request.query.window || '1h';
    
    const snapshotRes = await snapshotService.getSnapshot(symbol, t0, window);
    
    if (!snapshotRes.ok || !snapshotRes.snapshot) {
      return {
        ok: false,
        metrics: null,
        error: 'Failed to get snapshot',
      };
    }
    
    const metrics = metricsEngine.calculate(snapshotRes.snapshot);
    const state = deriveOnchainState(metrics);
    
    return {
      ok: true,
      metrics,
      state,
      source: snapshotRes.source,
    };
  } catch (error) {
    console.error('[OnChain V2] Metrics error:', error);
    return {
      ok: false,
      metrics: null,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function providerInfoHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const provider = getOnchainProvider();
    
    return {
      ok: true,
      provider: {
        id: provider.providerId,
        name: provider.providerName,
        mode: provider.providerMode,
        chains: provider.getSupportedChains(),
      },
    };
  } catch (error) {
    console.error('[OnChain V2] Provider info error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// RUNTIME HANDLER (Critical for observability)
// ═══════════════════════════════════════════════════════════════

interface RuntimeResponse {
  enabled: boolean;
  provider: 'mock' | 'rpc' | 'api';
  rpcConfigured: boolean;
  rpcHealthy: boolean;
  latestBlock: number | null;
  providerInitialized: boolean;
  now: number;
  notes: string[];
}

async function runtimeHandler(
  request: FastifyRequest,
  reply: FastifyReply
): Promise<RuntimeResponse> {
  const notes: string[] = [];
  const config = getActiveProviderConfig();
  
  // Check if RPC is configured
  const rpcConfigured = !!(
    config.rpc?.ethereum || 
    config.rpc?.arbitrum || 
    config.rpc?.optimism ||
    config.rpc?.base ||
    config.rpc?.polygon
  );
  
  let rpcHealthy = false;
  let latestBlock: number | null = null;
  
  // If RPC mode, check health
  if (config.mode === 'rpc') {
    if (!rpcConfigured) {
      notes.push('RPC_NOT_CONFIGURED');
    } else {
      try {
        const provider = getOnchainProvider();
        latestBlock = await provider.getLatestBlock('ethereum');
        rpcHealthy = true;
      } catch (error) {
        notes.push('RPC_HEALTH_CHECK_FAILED');
        rpcHealthy = false;
      }
    }
  } else if (config.mode === 'mock') {
    notes.push('USING_MOCK_PROVIDER');
    // Mock always healthy
    rpcHealthy = true;
    try {
      const provider = getOnchainProvider();
      latestBlock = await provider.getLatestBlock('ethereum');
    } catch {
      // Ignore
    }
  }
  
  return {
    enabled: true,
    provider: config.mode,
    rpcConfigured,
    rpcHealthy,
    latestBlock,
    providerInitialized: isProviderInitialized(),
    now: Date.now(),
    notes,
  };
}

// ═══════════════════════════════════════════════════════════════
// ADMIN: Reset Provider
// ═══════════════════════════════════════════════════════════════

async function resetProviderHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    resetOnchainProvider();
    return {
      ok: true,
      message: 'Provider reset successfully',
      timestamp: Date.now(),
    };
  } catch (error) {
    console.error('[OnChain V2] Reset error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function onchainV2Routes(fastify: FastifyInstance): Promise<void> {
  // Health & Runtime
  fastify.get('/health', healthHandler);
  fastify.get('/runtime', runtimeHandler);
  fastify.get('/provider', providerInfoHandler);
  
  // Admin
  fastify.post('/admin/reset-provider', resetProviderHandler);
  
  // Snapshot
  fastify.get('/snapshot/:symbol', snapshotHandler);
  fastify.get('/latest/:symbol', latestHandler);
  
  // Metrics
  fastify.get('/metrics/:symbol', metricsHandler);
  
  // Chart (user-facing)
  const { onchainV2ChartRoutes } = await import('./chart.routes.js');
  await fastify.register(onchainV2ChartRoutes);
  
  // Backfill (admin)
  const { onchainV2BackfillRoutes } = await import('./backfill.routes.js');
  await fastify.register(onchainV2BackfillRoutes);
  
  // Governance (sub-routes)
  const { onchainV2GovernanceRoutes } = await import('../governance/index.js');
  await fastify.register(onchainV2GovernanceRoutes, { prefix: '/admin/governance' });
  
  // RPC Pool Admin (sub-routes)
  const { rpcAdminRoutes } = await import('../rpc-pool/index.js');
  await fastify.register(rpcAdminRoutes, { prefix: '/admin' });
  
  // ERC20 Indexer (sub-routes)
  const { erc20IndexerRoutes } = await import('../ingestion/erc20/index.js');
  await fastify.register(erc20IndexerRoutes, { prefix: '/admin/indexer' });
  
  // Snapshot Builder (sub-routes)
  const { snapshotBuilderRoutes } = await import('../snapshot-builder/index.js');
  await fastify.register(snapshotBuilderRoutes, { prefix: '/admin/snapshot' });
  
  // DEX Ingestion (sub-routes)
  const { dexRoutes } = await import('../ingestion/dex/index.js');
  await fastify.register(dexRoutes, { prefix: '' });
  
  // Multi-Chain Indexer (BLOCK 2/3 - ERC20 + DEX)
  const { multiChainIndexerRoutes } = await import('../ingestion/multichain.routes.js');
  await fastify.register(multiChainIndexerRoutes, { prefix: '/admin/indexers' });
  
  // Rolling Stats / Governance (sub-routes)
  const { rollingRoutes } = await import('../governance/rolling.routes.js');
  await fastify.register(rollingRoutes, { prefix: '/governance' });
  
  // Drift / PSI (sub-routes)
  const { driftRoutes } = await import('../governance/drift.routes');
  await fastify.register(driftRoutes, { prefix: '/governance' });
  
  // Final Output (O9.5 - canonical endpoint)
  const { finalRoutes } = await import('../governance/final.routes');
  await fastify.register(finalRoutes, { prefix: '' });
  
  // Market Series (PHASE 1 - Liquidity Engine)
  const { marketRoutes } = await import('../market/market.routes');
  await fastify.register(marketRoutes, { prefix: '/market' });
  
  // Stablecoin Mint/Burn (BLOCK 5 - Supply Watcher)
  const { stableRoutes, startStableJobs } = await import('../stables/index.js');
  await fastify.register(stableRoutes, { prefix: '/stables' });
  
  // Chains (BLOCK 1 - Multi-Chain Foundation)
  const { chainsFastifyRoutes } = await import('../chains/chain.fastify.routes.js');
  await fastify.register(chainsFastifyRoutes, { prefix: '/chains' });
  
  // Bridge Intelligence (BLOCK 4 - L1↔L2 Migration)
  const { bridgeFastifyRoutes, bridgeScheduler, bridgeAggRoutes, startBridgeAggJob } = await import('../bridge/index.js');
  await fastify.register(bridgeFastifyRoutes, { prefix: '/bridge' });
  await fastify.register(bridgeAggRoutes, { prefix: '/bridge/aggregate' });

  // Start background jobs only when NOT in MINIMAL_BOOT
  if (process.env.MINIMAL_BOOT !== '1') {
    startStableJobs();
    bridgeScheduler.start();
    startBridgeAggJob();
    const { startMarketJob } = await import('../market/market.job');
    startMarketJob();
    const { startLiquidityJob } = await import('../market/liquidity/liquidity.job');
    startLiquidityJob();
    const { multiChainScheduler } = await import('../ingestion/multichain.scheduler.js');
    multiChainScheduler.start();
  } else {
    console.log('[OnChain V2] MINIMAL_BOOT — all background jobs skipped');
  }
  
  // ═══════════════════════════════════════════════════════════════
  // BLOCK 6 — Normalization Engine
  // ═══════════════════════════════════════════════════════════════
  const { buildNormalizationRoutes } = await import('../normalization/index.js');
  const { getLatestLiquidity } = await import('../market/liquidity/index.js');
  const { bridgeAggregationService } = await import('../bridge/index.js');
  const { stableAggregationService } = await import('../stables/index.js');
  
  const normalizationDeps = {
    marketLiquidity: {
      getLatest: async (_window: string) => getLatestLiquidity(),
    },
    bridgeAgg: {
      getLatest: (window: string) => bridgeAggregationService.getLatest(window),
    },
    stablesAgg: {
      getLatest: (window: string) => stableAggregationService.getLatest(window as any),
    },
  };
  
  await fastify.register(buildNormalizationRoutes(normalizationDeps), { prefix: '/normalization' });
  
  // ═══════════════════════════════════════════════════════════════
  // BLOCK 7 — LiquidityScore v2 (LARE v2)
  // ═══════════════════════════════════════════════════════════════
  const { LiquidityV2Service, buildLiquidityV2Routes, startLiquidityV2Job } = await import('../market/liquidity_v2/index.js');
  
  const liquidityV2Service = new LiquidityV2Service(normalizationDeps);
  await fastify.register(buildLiquidityV2Routes(liquidityV2Service), { prefix: '/lare-v2' });
  
  // Start LARE v2 job — skip in MINIMAL_BOOT
  if (process.env.MINIMAL_BOOT !== '1') {
    startLiquidityV2Job(liquidityV2Service);
  }
  
  // ═══════════════════════════════════════════════════════════════
  // P0 — Entity Labels (PHASE 5)
  // ═══════════════════════════════════════════════════════════════
  const { labelsRoutes, LabelsService } = await import('../labels/index.js');
  await fastify.register(labelsRoutes, { prefix: '/labels' });
  
  // ═══════════════════════════════════════════════════════════════
  // P0.8 — Entity Flow Aggregation Job (PHASE 5)
  // ═══════════════════════════════════════════════════════════════
  const { startEntityFlowJob } = await import('../market/actors/entityFlow.job.js');
  const labelsInstance = new LabelsService();
  startEntityFlowJob({ labels: labelsInstance });
  
  // ═══════════════════════════════════════════════════════════════
  // P0.9 — Actor Score Structural Job (Edge Score from EntityFlowModel)
  // ═══════════════════════════════════════════════════════════════
  const { startActorScoreJob } = await import('../market/actors/actorScore.job.js');
  startActorScoreJob(10 * 60 * 1000); // every 10 minutes
  
  // ═══════════════════════════════════════════════════════════════
  // PHASE 4 — Engine Decision API (token-first)
  // ═══════════════════════════════════════════════════════════════
  const { engineRoutes } = await import('../market/engine/engine.routes.js');
  await fastify.register(engineRoutes, { prefix: '/engine' });

  // ═══════════════════════════════════════════════════════════════
  // PHASE BT — Engine Backtest
  // ═══════════════════════════════════════════════════════════════
  const { engineBacktestRoutes } = await import('../market/engine_backtest/engine.backtest.routes.js');
  await fastify.register(engineBacktestRoutes, { prefix: '/engine' });

  // ═══════════════════════════════════════════════════════════════
  // PHASE F3 — OnChain Health Dashboard
  // ═══════════════════════════════════════════════════════════════
  const { onchainHealthRoutes } = await import('../market/health/onchain.health.routes.js');
  await fastify.register(onchainHealthRoutes, { prefix: '/system' });

  // ═══════════════════════════════════════════════════════════════
  // PHASE A — CEX Flow Intelligence
  // ═══════════════════════════════════════════════════════════════
  const { cexFlowRoutes } = await import('../market/cex/cexFlow.routes.js');
  await fastify.register(cexFlowRoutes, { prefix: '/cex-flow' });

  // ═══════════════════════════════════════════════════════════════
  // PHASE A1.2 — CEX Registry (Industrial)
  // ═══════════════════════════════════════════════════════════════
  const { cexRegistryRoutes } = await import('../cex_registry/cex_registry.routes.js');
  await fastify.register(cexRegistryRoutes, { prefix: '/cex/registry' });

  // ═══════════════════════════════════════════════════════════════
  // PHASE A3 — CEX Flow Buckets (Precomputed Aggregates)
  // ═══════════════════════════════════════════════════════════════
  const { cexBucketRoutes } = await import('../market/cex/buckets/cexBuckets.routes.js');
  await fastify.register(cexBucketRoutes, { prefix: '/cex-flow/buckets' });

  // ═══════════════════════════════════════════════════════════════
  // PHASE C — Wallets v3 (Deep Profile)
  // ═══════════════════════════════════════════════════════════════
  const { walletsV3Routes } = await import('../wallets_v3/wallets.routes.js');
  await fastify.register(walletsV3Routes, { prefix: '/wallets' });
  
  // ═══════════════════════════════════════════════════════════════
  // PHASE 5.3 — Feature Flags Status
  // ═══════════════════════════════════════════════════════════════
  fastify.get('/system/flags', async () => {
    const { ONCHAIN_FLAGS } = await import('../core/featureFlags.js');
    return {
      ok: true,
      flags: {
        FREEZE_MODE: ONCHAIN_FLAGS.FREEZE_MODE,
        MULTICHAIN_ENABLED: ONCHAIN_FLAGS.MULTICHAIN_ENABLED,
        POOL_AUTO_ACTIVATION: ONCHAIN_FLAGS.POOL_AUTO_ACTIVATION,
        DISCOVERY_WRITE: ONCHAIN_FLAGS.DISCOVERY_WRITE,
      },
    };
  });

  console.log('[OnChain V2] Routes registered');
}

console.log('[OnChain V2] Routes module loaded');
