/**
 * OnChain V2 — Chain Fastify Routes
 * ===================================
 * 
 * Native Fastify routes for chain health monitoring.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { chainRegistry } from './chain.registry.js';
import { chainHealthService } from './chain.health.service.js';
import { MULTICHAIN_ENABLED } from './chain.constants.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function chainsFastifyRoutes(fastify: FastifyInstance): Promise<void> {
  
  // GET /chains — List all chains with health
  fastify.get('/', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const summary = await chainHealthService.getAllChainsHealth();
      return summary;
    } catch (error) {
      console.error('[Chains] Error getting all chains health:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  // GET /chains/config — Get chain configuration
  fastify.get('/config', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const allChains = chainRegistry.listAll();
      const activeChains = chainRegistry.listActive();
      
      return {
        ok: true,
        multiChainEnabled: MULTICHAIN_ENABLED,
        supportedChains: allChains.map(c => ({
          chainId: c.chainId,
          name: c.name,
          short: c.short,
          explorer: c.explorer,
          nativeSymbol: c.nativeSymbol,
          avgBlockTime: c.avgBlockTime,
          active: chainRegistry.isActive(c.chainId),
        })),
        activeChainIds: activeChains.map(c => c.chainId),
      };
    } catch (error) {
      console.error('[Chains] Error getting config:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  // GET /chains/:chainId/health — Get single chain health
  fastify.get<{
    Params: { chainId: string };
  }>('/:chainId/health', async (request, reply) => {
    try {
      const chainId = parseInt(request.params.chainId, 10);
      
      if (isNaN(chainId)) {
        reply.code(400);
        return { ok: false, error: 'Invalid chainId' };
      }

      if (!chainRegistry.isSupported(chainId)) {
        reply.code(404);
        return { ok: false, error: `Chain ${chainId} not supported` };
      }

      const health = await chainHealthService.getChainHealth(chainId);
      return { ok: true, ...health };
    } catch (error) {
      console.error('[Chains] Error getting chain health:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  // POST /chains/health-check — Trigger health check
  fastify.post('/health-check', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      await chainHealthService.runHealthCheck();
      const summary = await chainHealthService.getAllChainsHealth();
      return { ok: true, ...summary };
    } catch (error) {
      console.error('[Chains] Error running health check:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  // POST /chains/clear-cache — Clear health cache
  fastify.post('/clear-cache', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      chainHealthService.clearCache();
      return { ok: true, message: 'Cache cleared' };
    } catch (error) {
      console.error('[Chains] Error clearing cache:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  // GET /chains/job-readiness — Check if all jobs are chain-aware
  fastify.get('/job-readiness', async (_request: FastifyRequest, reply: FastifyReply) => {
    const { SUPPORTED_CHAINS } = await import('../chains/chain.constants.js');
    const mongoose = await import('mongoose');
    
    const availableChains = SUPPORTED_CHAINS.map(c => c.chainId);
    
    // Get enabled chains from DB
    let enabledChains: number[] = [1];
    try {
      const db = mongoose.default.connection.db;
      if (db) {
        const chains = await db.collection('chains')
          .find({ enabled: true }, { projection: { chainId: 1, _id: 0 } })
          .toArray();
        enabledChains = chains.map(c => c.chainId as number);
      }
    } catch {}
    
    return {
      ok: true,
      enabledChains,
      availableChains,
      chainCount: enabledChains.length,
      jobWrapper: 'runPerChain',
      refactoredJobs: [
        'WalletSnapshotJob',
        'TokenSeriesJob',
        'CexBucketJob',
        'ActorScoreJob',
        'EntityFlowJob',
        'AltFlowJob',
        'MarketSeriesJob',
        'LiquidityJob',
        'LiquidityV2Job',
        'BridgeAggJob',
        'PoolDiscoveryJob',
        'PoolLiquidityJob',
        'StableAggJob',
        'DexSyncJob',
      ],
      featureFlags: {
        MULTICHAIN_ENABLED: process.env.MULTICHAIN_ENABLED === 'true',
        ENABLE_ARB_INGESTION: process.env.ENABLE_ARB_INGESTION === 'true',
        ENABLE_ARB_ALTFLOW: process.env.ENABLE_ARB_ALTFLOW === 'true',
        ENABLE_ARB_ENGINE: process.env.ENABLE_ARB_ENGINE === 'true',
        ENABLE_OP_INGESTION: process.env.ENABLE_OP_INGESTION === 'true',
        ENABLE_OP_ALTFLOW: process.env.ENABLE_OP_ALTFLOW === 'true',
        ENABLE_OP_ENGINE: process.env.ENABLE_OP_ENGINE === 'true',
        ENABLE_BASE_INGESTION: process.env.ENABLE_BASE_INGESTION === 'true',
        ENABLE_BASE_ALTFLOW: process.env.ENABLE_BASE_ALTFLOW === 'true',
        ENABLE_BASE_ENGINE: process.env.ENABLE_BASE_ENGINE === 'true',
      },
      message: `${enabledChains.length} enabled / ${availableChains.length} available chains`,
    };
  });

  console.log('[OnChain V2] Chain Fastify Routes registered');
}

console.log('[OnChain V2] Chain Fastify Routes module loaded');
