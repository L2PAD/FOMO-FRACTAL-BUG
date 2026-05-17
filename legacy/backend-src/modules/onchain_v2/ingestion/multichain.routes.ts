/**
 * OnChain V2 — Multi-Chain Indexer Routes
 * =========================================
 * 
 * API endpoints for multi-chain indexer status and control.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { multiChainScheduler } from './multichain.scheduler.js';
import { chainRegistry, getActiveChainIds } from '../chains/index.js';
import { erc20Indexer } from './erc20/index.js';
import { dexIngestionService, getDexIngestionService } from './dex/index.js';
import { SyncStateModel } from './erc20/models.js';
import { DexPoolModel } from './dex/models.js';
import { rpcPool } from '../rpc-pool/index.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function multiChainIndexerRoutes(fastify: FastifyInstance): Promise<void> {
  
  // GET /indexers/status — Get all indexers status
  fastify.get('/status', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const schedulerStatus = multiChainScheduler.getStatus();
      const activeChains = getActiveChainIds();
      
      // Get per-chain status
      const chainsStatus = [];
      
      for (const chainId of activeChains) {
        const chain = chainRegistry.getShort(chainId);
        
        // Get latest block
        let latestBlock = 0;
        try {
          latestBlock = await rpcPool.getBlockNumber(chainId);
        } catch {
          // RPC may be down
        }
        
        // Get ERC20 sync state
        const erc20State = await SyncStateModel.findOne({ key: `erc20_${chainId}` }).lean();
        
        // Get DEX sync state
        const dexState = await SyncStateModel.findOne({ key: `dex_uniswap_v3_${chainId}` }).lean();
        
        // STEP 4: Get active pool count from registry
        const activePools = await DexPoolModel.countDocuments({
          chainId,
          enabled: true,
          status: { $in: ['ACTIVE', 'DEGRADED'] },
        });
        
        chainsStatus.push({
          chainId,
          chain,
          latestBlock,
          erc20: {
            lastBlock: erc20State?.lastBlock || 0,
            blocksBehind: Math.max(0, latestBlock - (erc20State?.lastBlock || 0)),
            totalIndexed: erc20State?.totalLogsIndexed || 0,
            status: erc20State?.status || 'idle',
            lastSyncAt: erc20State?.lastSyncAt || 0,
            lastError: erc20State?.lastError,
          },
          dex: {
            lastBlock: dexState?.lastBlock || 0,
            blocksBehind: Math.max(0, latestBlock - (dexState?.lastBlock || 0)),
            totalIndexed: dexState?.totalLogsIndexed || 0,
            status: dexState?.status || 'idle',
            lastSyncAt: dexState?.lastSyncAt || 0,
            lastError: dexState?.lastError,
            activePools, // STEP 4: Pool count from registry
          },
        });
      }

      return {
        ok: true,
        scheduler: {
          running: schedulerStatus.running,
          lastTick: schedulerStatus.lastTick,
          tickCount: schedulerStatus.tickCount,
        },
        multiChainEnabled: chainRegistry.isMultiChainEnabled(),
        activeChains: activeChains.length,
        chains: chainsStatus,
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[IndexerRoutes] Error getting status:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  // GET /indexers/status/:chainId — Get single chain status
  fastify.get<{
    Params: { chainId: string };
  }>('/status/:chainId', async (request, reply) => {
    try {
      const chainId = parseInt(request.params.chainId, 10);
      
      if (isNaN(chainId) || !chainRegistry.isSupported(chainId)) {
        reply.code(400);
        return { ok: false, error: 'Invalid or unsupported chainId' };
      }

      const chain = chainRegistry.getShort(chainId);
      
      // Get latest block
      let latestBlock = 0;
      try {
        latestBlock = await rpcPool.getBlockNumber(chainId);
      } catch {
        // RPC may be down
      }
      
      // Get sync states
      const erc20State = await SyncStateModel.findOne({ key: `erc20_${chainId}` }).lean();
      const dexState = await SyncStateModel.findOne({ key: `dex_uniswap_v3_${chainId}` }).lean();

      return {
        ok: true,
        chainId,
        chain,
        latestBlock,
        erc20: {
          lastBlock: erc20State?.lastBlock || 0,
          blocksBehind: Math.max(0, latestBlock - (erc20State?.lastBlock || 0)),
          totalIndexed: erc20State?.totalLogsIndexed || 0,
          status: erc20State?.status || 'idle',
          lastSyncAt: erc20State?.lastSyncAt || 0,
          lastError: erc20State?.lastError,
        },
        dex: {
          lastBlock: dexState?.lastBlock || 0,
          blocksBehind: Math.max(0, latestBlock - (dexState?.lastBlock || 0)),
          totalIndexed: dexState?.totalLogsIndexed || 0,
          status: dexState?.status || 'idle',
          lastSyncAt: dexState?.lastSyncAt || 0,
          lastError: dexState?.lastError,
        },
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[IndexerRoutes] Error getting chain status:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  // POST /indexers/force-tick — Force immediate indexer tick
  fastify.post('/force-tick', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      await multiChainScheduler.forceTick();
      const status = multiChainScheduler.getStatus();
      
      return {
        ok: true,
        message: 'Force tick completed',
        tickCount: status.tickCount,
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[IndexerRoutes] Error forcing tick:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  // POST /indexers/start — Start scheduler
  fastify.post('/start', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      multiChainScheduler.start();
      return {
        ok: true,
        message: 'Scheduler started',
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[IndexerRoutes] Error starting scheduler:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  // POST /indexers/stop — Stop scheduler
  fastify.post('/stop', async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      multiChainScheduler.stop();
      return {
        ok: true,
        message: 'Scheduler stopped',
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('[IndexerRoutes] Error stopping scheduler:', error);
      return { 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  });

  console.log('[OnChain V2] Multi-Chain Indexer Routes registered');
}

console.log('[OnChain V2] Multi-Chain Indexer Routes module loaded');
