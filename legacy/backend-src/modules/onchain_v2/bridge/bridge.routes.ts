/**
 * OnChain V2 — Bridge Routes (Fastify)
 * ======================================
 * 
 * API endpoints for Bridge Intelligence health and configuration.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { getBridgeTracks, getAllContractRoles, getSupportedBridges, getL2ChainId } from './bridge.registry.js';
import { bridgeHealthService, BRIDGE_ENABLED, BridgeHealthDeps } from './bridge.health.service.js';
import { STATIC_BRIDGE_ADDRESSES } from './bridge.resolver.js';
import { chainRegistry, MULTICHAIN_ENABLED } from '../chains/index.js';
import { bridgeIndexer } from './bridge.indexer.js';
import { bridgeScheduler } from './bridge.scheduler.js';
import { BridgeEventModel } from './bridge.model.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE DEPS
// ═══════════════════════════════════════════════════════════════

function getBridgeDeps(): BridgeHealthDeps {
  return {
    env: process.env,
    staticMap: STATIC_BRIDGE_ADDRESSES,
    chains: {
      getActiveChainIds: () => chainRegistry.getActiveIds(),
      isActive: (chainId: number) => chainRegistry.isActive(chainId),
    },
    flags: {
      bridgeEnabled: BRIDGE_ENABLED,
      multiChainEnabled: MULTICHAIN_ENABLED,
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function bridgeFastifyRoutes(fastify: FastifyInstance): Promise<void> {

  // GET /bridge/config — Registry and configuration
  fastify.get('/config', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const tracks = getBridgeTracks();
      const roles = getAllContractRoles();
      const bridges = getSupportedBridges();

      return {
        ok: true,
        bridgeEnabled: BRIDGE_ENABLED,
        multiChainEnabled: MULTICHAIN_ENABLED,
        supportedBridges: bridges.map(b => ({
          name: b,
          l1ChainId: 1,
          l2ChainId: getL2ChainId(b),
        })),
        tracks: tracks.map(t => ({
          id: t.id,
          bridge: t.bridge,
          direction: t.direction,
          watchSide: t.watchSide,
          watchChainId: t.watchChainId,
          contractRoles: t.contractRoles,
          eventHints: t.eventHints,
        })),
        requiredEnvRoles: roles,
        staticAddresses: STATIC_BRIDGE_ADDRESSES,
      };
    } catch (error) {
      console.error('[Bridge] Error getting config:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // GET /bridge/health — Full health status
  fastify.get('/health', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const deps = getBridgeDeps();
      const health = await bridgeHealthService.getHealth(deps);
      return health;
    } catch (error) {
      console.error('[Bridge] Error getting health:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // GET /bridge/chains — Tracks grouped by chain
  fastify.get('/chains', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const tracks = getBridgeTracks();
      const byChain: Record<number, Array<{
        id: string;
        bridge: string;
        direction: string;
        watchSide: string;
        roles: string[];
      }>> = {};

      for (const t of tracks) {
        if (!byChain[t.watchChainId]) {
          byChain[t.watchChainId] = [];
        }
        byChain[t.watchChainId].push({
          id: t.id,
          bridge: t.bridge,
          direction: t.direction,
          watchSide: t.watchSide,
          roles: t.contractRoles,
        });
      }

      return {
        ok: true,
        byChain,
      };
    } catch (error) {
      console.error('[Bridge] Error getting chains:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // GET /bridge/readiness — Quick readiness check
  fastify.get('/readiness', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const deps = getBridgeDeps();
      const result = await bridgeHealthService.isReadyForIngestion(deps);
      return {
        ok: true,
        ...result,
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[Bridge] Error checking readiness:', error);
      return {
        ok: false,
        ready: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // POST /bridge/clear-cache — Clear health cache
  fastify.post('/clear-cache', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      bridgeHealthService.clearCache();
      return {
        ok: true,
        message: 'Cache cleared',
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[Bridge] Error clearing cache:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // INDEXER ENDPOINTS
  // ═══════════════════════════════════════════════════════════════

  // GET /bridge/indexer/status — Get indexer status
  fastify.get('/indexer/status', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const schedulerStatus = bridgeScheduler.getStatus();
      const trackStatus = await bridgeIndexer.getStatus();
      
      return {
        ok: true,
        scheduler: schedulerStatus,
        tracks: trackStatus,
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[Bridge] Error getting indexer status:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // POST /bridge/indexer/force-tick — Force immediate indexing
  fastify.post('/indexer/force-tick', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const result = await bridgeScheduler.forceTick();
      return {
        ok: true,
        result,
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[Bridge] Error forcing tick:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // POST /bridge/indexer/start — Start scheduler
  fastify.post('/indexer/start', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      bridgeScheduler.start();
      return {
        ok: true,
        message: 'Scheduler started',
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[Bridge] Error starting scheduler:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // POST /bridge/indexer/stop — Stop scheduler
  fastify.post('/indexer/stop', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      bridgeScheduler.stop();
      return {
        ok: true,
        message: 'Scheduler stopped',
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[Bridge] Error stopping scheduler:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // EVENT STATS ENDPOINTS
  // ═══════════════════════════════════════════════════════════════

  // GET /bridge/events/stats — Get event statistics
  fastify.get('/events/stats', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const now = Date.now();
      const day = 24 * 60 * 60 * 1000;
      
      const [total, last24h, byDirection, byBridge, whales] = await Promise.all([
        BridgeEventModel.countDocuments(),
        BridgeEventModel.countDocuments({ timestamp: { $gte: now - day } }),
        BridgeEventModel.aggregate([
          { $group: { _id: '$direction', count: { $sum: 1 } } }
        ]),
        BridgeEventModel.aggregate([
          { $group: { _id: '$bridge', count: { $sum: 1 } } }
        ]),
        BridgeEventModel.countDocuments({ isWhale: true }),
      ]);

      return {
        ok: true,
        stats: {
          total,
          last24h,
          whales,
          byDirection: Object.fromEntries(byDirection.map(d => [d._id, d.count])),
          byBridge: Object.fromEntries(byBridge.map(d => [d._id, d.count])),
        },
        timestamp: now,
      };
    } catch (error) {
      console.error('[Bridge] Error getting event stats:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  // GET /bridge/events/recent — Get recent events
  fastify.get<{
    Querystring: { limit?: string; direction?: string; bridge?: string };
  }>('/events/recent', async (request, reply) => {
    try {
      const limit = Math.min(parseInt(request.query.limit || '20', 10), 100);
      const filter: any = {};
      
      if (request.query.direction) {
        filter.direction = request.query.direction;
      }
      if (request.query.bridge) {
        filter.bridge = request.query.bridge;
      }

      const events = await BridgeEventModel
        .find(filter)
        .sort({ timestamp: -1 })
        .limit(limit)
        .select('-__v')
        .lean();

      return {
        ok: true,
        count: events.length,
        events: events.map(e => ({
          ...e,
          _id: undefined,
        })),
      };
    } catch (error) {
      console.error('[Bridge] Error getting recent events:', error);
      return {
        ok: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  });

  console.log('[OnChain V2] Bridge Fastify Routes registered');
}

console.log('[OnChain V2] Bridge Routes module loaded');
