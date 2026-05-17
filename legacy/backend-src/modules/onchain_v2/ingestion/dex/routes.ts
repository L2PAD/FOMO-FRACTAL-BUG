/**
 * OnChain V2 — DEX Routes
 * ========================
 * 
 * API endpoints for DEX ingestion status and control.
 */

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { getDexIngestionService } from './dex_ingestion.service.js';
import { runDexSyncJob, getLastDexSyncResult, isDexSyncRunning } from './dex_sync.job.js';
import { dexBackfillService } from './dexBackfill.service.js';
import { poolMetaResolver } from './poolMeta.resolver.js';
import type { RpcChainId } from '../../rpc-pool/models.js';

export async function dexRoutes(app: FastifyInstance) {
  /**
   * GET /api/v10/onchain-v2/dex/status
   * Get DEX ingestion status
   */
  app.get('/dex/status', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const chainId = (req.query as any).chainId ? parseInt((req.query as any).chainId) as RpcChainId : 1;
      const service = getDexIngestionService(chainId);
      const status = await service.getStatus();
      const lastRun = getLastDexSyncResult();
      
      return {
        ok: true,
        ...status,
        lastRun,
        isRunning: isDexSyncRunning(),
      };
    } catch (err) {
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });

  /**
   * POST /api/v10/onchain-v2/dex/sync
   * Trigger manual DEX sync
   */
  app.post('/dex/sync', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const chainId = (req.body as any)?.chainId ? parseInt((req.body as any).chainId) as RpcChainId : 1;
      
      if (isDexSyncRunning()) {
        return reply.status(409).send({
          ok: false,
          error: 'Sync already running',
        });
      }

      // Run sync in background
      runDexSyncJob(chainId).catch(err => {
        console.error('[DexRoutes] Background sync error:', err);
      });

      return {
        ok: true,
        message: `DEX sync started for chain ${chainId}`,
      };
    } catch (err) {
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });

  /**
   * GET /api/v10/onchain-v2/dex/stats
   * Get DEX swap statistics
   */
  app.get('/dex/stats', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const query = req.query as any;
      const chainId = query.chainId ? parseInt(query.chainId) as RpcChainId : 1;
      const windowMs = query.windowMs ? parseInt(query.windowMs) : 3600000; // 1h default
      const pool = query.pool;

      const service = getDexIngestionService(chainId);
      const stats = await service.getSwapStats({ pool, windowMs });

      return {
        ok: true,
        chainId,
        windowMs,
        pool: pool || 'all',
        ...stats,
      };
    } catch (err) {
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });

  /**
   * POST /api/v10/onchain-v2/dex/backfill
   * Start DEX backfill for a block range
   */
  app.post('/dex/backfill', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = req.body as any;
      const chainId = body.chainId ? parseInt(body.chainId) as RpcChainId : 1;
      const blocks = body.blocks || 5000;

      const service = getDexIngestionService(chainId);
      
      if (!service.isEnabled()) {
        return reply.status(400).send({
          ok: false,
          error: 'DEX ingestion is disabled',
        });
      }

      // Run backfill in background
      (async () => {
        try {
          const result = await service.ingestRecent({ lookbackBlocks: blocks });
          console.log(`[DexRoutes] Backfill completed: ${result.swapsInserted} swaps`);
        } catch (err) {
          console.error('[DexRoutes] Backfill error:', err);
        }
      })();

      return {
        ok: true,
        message: `DEX backfill started: ${blocks} blocks for chain ${chainId}`,
      };
    } catch (err) {
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // TOKEN BACKFILL ENDPOINTS (PHASE 3.5.5)
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /api/v10/onchain-v2/dex/backfill/status
   * Get backfill status (how many swaps need token patching)
   */
  app.get('/dex/backfill/status', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const chainId = (req.query as any).chainId ? parseInt((req.query as any).chainId) as RpcChainId : 1;
      const status = await dexBackfillService.getStatus(chainId);
      const resolverStats = poolMetaResolver.getStats();
      
      return {
        ok: true,
        ...status,
        poolResolver: resolverStats,
      };
    } catch (err) {
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });

  /**
   * POST /api/v10/onchain-v2/dex/backfill/pools
   * Backfill pool metadata from RPC
   */
  app.post('/dex/backfill/pools', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = req.body as any;
      const chainId = body?.chainId ? parseInt(body.chainId) as RpcChainId : 1;
      const limit = body?.limit ? parseInt(body.limit) : 500;
      
      const result = await dexBackfillService.backfillPools(chainId, limit);
      
      return {
        ok: true,
        ...result,
      };
    } catch (err) {
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });

  /**
   * POST /api/v10/onchain-v2/dex/backfill/swaps
   * Patch swaps with token0/token1 from pool metadata
   */
  app.post('/dex/backfill/swaps', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = req.body as any;
      const chainId = body?.chainId ? parseInt(body.chainId) as RpcChainId : 1;
      const batchSize = body?.batchSize ? parseInt(body.batchSize) : 5000;
      
      const result = await dexBackfillService.backfillSwaps(chainId, batchSize);
      
      return {
        ok: true,
        ...result,
      };
    } catch (err) {
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });

  /**
   * POST /api/v10/onchain-v2/dex/backfill/full
   * Run complete backfill pipeline (pools → swaps)
   */
  app.post('/dex/backfill/full', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const body = req.body as any;
      const chainId = body?.chainId ? parseInt(body.chainId) as RpcChainId : 1;
      
      // Run in background
      (async () => {
        try {
          console.log(`[DexBackfill] Starting full backfill for chain ${chainId}...`);
          const result = await dexBackfillService.runFullBackfill(chainId);
          console.log(`[DexBackfill] Full backfill complete:`, result.finalStatus);
        } catch (err) {
          console.error('[DexBackfill] Full backfill error:', err);
        }
      })();

      return {
        ok: true,
        message: `Full DEX backfill started for chain ${chainId}`,
      };
    } catch (err) {
      return reply.status(500).send({
        ok: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  });

  console.log('[OnChain V2] DEX routes registered');
}
