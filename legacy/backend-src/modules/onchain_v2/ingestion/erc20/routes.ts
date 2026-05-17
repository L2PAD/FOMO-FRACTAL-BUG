/**
 * OnChain V2 — ERC20 Indexer Routes
 * ===================================
 * 
 * Admin endpoints for ERC20 indexer management.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { erc20Indexer } from './indexer.service.js';
import { rpcPool } from '../../rpc-pool/index.js';
import { ERC20LogModel, SyncStateModel, AddressLabelModel, TokenMetadataModel } from './models.js';
import type { RpcChainId } from '../../rpc-pool/models.js';

// ═══════════════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════════════

/**
 * GET /indexer/status — Get indexer status
 */
async function getStatusHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const status = await erc20Indexer.getStatus();
    
    return {
      ok: true,
      ...status,
    };
  } catch (error) {
    console.error('[ERC20Indexer] Get status error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * POST /indexer/sync — Trigger manual sync
 */
async function triggerSyncHandler(
  request: FastifyRequest<{
    Body: {
      chainId: RpcChainId;
      maxBlocksPerBatch?: number;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { chainId, maxBlocksPerBatch } = request.body;
    
    // Run sync in background
    erc20Indexer.sync({ chainId, maxBlocksPerBatch }).catch(err => {
      console.error('[ERC20Indexer] Sync error:', err);
    });
    
    return {
      ok: true,
      message: `Sync started for chain ${chainId}`,
    };
  } catch (error) {
    console.error('[ERC20Indexer] Trigger sync error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * POST /indexer/backfill — Run backfill for range (chunked with progress)
 */
async function backfillHandler(
  request: FastifyRequest<{
    Body: {
      chainId: number;
      mode?: '30d' | '7d' | 'custom';
      fromBlock?: number;
      toBlock?: number;
      tokenAddresses?: string[];
      chunkBlocks?: number;
      sleepMs?: number;
      maxMinutes?: number;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { 
      chainId, 
      mode = 'custom',
      fromBlock: customFrom,
      toBlock: customTo,
      tokenAddresses,
      chunkBlocks,
      sleepMs,
      maxMinutes,
    } = request.body;
    
    if (!chainId) {
      return { ok: false, error: 'chainId required' };
    }
    
    // Get latest block
    const latestBlock = await rpcPool.getBlockNumber(chainId);
    
    // Calculate block range based on mode
    let fromBlock: number;
    let toBlock: number;
    
    if (mode === '30d') {
      // ~30 days worth of blocks (assuming ~12s per block on ETH)
      const blocksPerDay = Math.floor(86400 / 12);
      fromBlock = latestBlock - (blocksPerDay * 30);
      toBlock = latestBlock - 10;
    } else if (mode === '7d') {
      const blocksPerDay = Math.floor(86400 / 12);
      fromBlock = latestBlock - (blocksPerDay * 7);
      toBlock = latestBlock - 10;
    } else {
      if (!customFrom || !customTo) {
        return { ok: false, error: 'fromBlock and toBlock required for custom mode' };
      }
      fromBlock = customFrom;
      toBlock = customTo;
    }
    
    const totalBlocks = toBlock - fromBlock;
    
    // Run backfill in background
    erc20Indexer.backfill({ 
      chainId, 
      fromBlock, 
      toBlock, 
      tokenAddresses,
      chunkBlocks,
      sleepMs,
      maxMinutes,
    }).catch(err => {
      console.error('[ERC20Indexer] Backfill error:', err);
    });
    
    return {
      ok: true,
      message: `Backfill started: ${totalBlocks.toLocaleString()} blocks (${fromBlock} → ${toBlock}) on chain ${chainId}`,
      fromBlock,
      toBlock,
      totalBlocks,
      estimatedMinutes: Math.ceil(totalBlocks / 1000), // ~1000 blocks/min
    };
  } catch (error) {
    console.error('[ERC20Indexer] Backfill error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * GET /indexer/backfill/status — Get backfill progress
 */
async function backfillStatusHandler(
  request: FastifyRequest<{
    Querystring: { chainId?: string };
  }>,
  reply: FastifyReply
) {
  try {
    const chainId = parseInt(request.query.chainId || '1');
    const status = await erc20Indexer.getBackfillStatus(chainId);
    
    if (!status) {
      return {
        ok: true,
        status: null,
        message: 'No backfill in progress for this chain',
      };
    }
    
    return {
      ok: true,
      status,
    };
  } catch (error) {
    console.error('[ERC20Indexer] Backfill status error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * POST /indexer/reset — Reset sync state (dangerous!)
 */
async function resetHandler(
  request: FastifyRequest<{
    Body: {
      chainId: RpcChainId;
      confirm: boolean;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { chainId, confirm } = request.body;
    
    if (!confirm) {
      return { ok: false, error: 'Confirm reset by setting confirm=true' };
    }
    
    await erc20Indexer.reset(chainId);
    
    return {
      ok: true,
      message: `Chain ${chainId} reset complete`,
    };
  } catch (error) {
    console.error('[ERC20Indexer] Reset error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * GET /indexer/logs — Get recent logs
 */
async function getLogsHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      limit?: string;
      token?: string;
      from?: string;
      to?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { chainId, limit = '50', token, from, to } = request.query;
    
    const filter: Record<string, unknown> = {};
    if (chainId) filter.chainId = parseInt(chainId);
    if (token) filter.tokenAddress = token.toLowerCase();
    if (from) filter.from = from.toLowerCase();
    if (to) filter.to = to.toLowerCase();
    
    const logs = await ERC20LogModel.find(filter)
      .sort({ blockNumber: -1 })
      .limit(parseInt(limit))
      .lean();
    
    return {
      ok: true,
      count: logs.length,
      logs: logs.map(l => ({
        blockNumber: l.blockNumber,
        txHash: l.transactionHash,
        logIndex: l.logIndex,
        token: l.tokenAddress,
        from: l.from,
        to: l.to,
        value: l.value,
        fromLabel: l.fromLabel,
        toLabel: l.toLabel,
      })),
    };
  } catch (error) {
    console.error('[ERC20Indexer] Get logs error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * POST /indexer/labels — Add address label
 */
async function addLabelHandler(
  request: FastifyRequest<{
    Body: {
      chainId: RpcChainId;
      address: string;
      type: string;
      name: string;
      subtype?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { chainId, address, type, name, subtype } = request.body;
    
    await AddressLabelModel.findOneAndUpdate(
      { chainId, address: address.toLowerCase() },
      {
        chainId,
        address: address.toLowerCase(),
        type,
        name,
        subtype,
        source: 'admin',
        updatedAt: Date.now(),
      },
      { upsert: true }
    );
    
    // Clear cache
    erc20Indexer.clearLabelCache();
    
    return {
      ok: true,
      message: `Label added for ${address}`,
    };
  } catch (error) {
    console.error('[ERC20Indexer] Add label error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * GET /indexer/labels — Get labels
 */
async function getLabelsHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      type?: string;
      limit?: string;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { chainId, type, limit = '100' } = request.query;
    
    const filter: Record<string, unknown> = {};
    if (chainId) filter.chainId = parseInt(chainId);
    if (type) filter.type = type;
    
    const labels = await AddressLabelModel.find(filter)
      .limit(parseInt(limit))
      .lean();
    
    return {
      ok: true,
      count: labels.length,
      labels,
    };
  } catch (error) {
    console.error('[ERC20Indexer] Get labels error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * GET /indexer/stats — Get aggregate stats
 */
async function getStatsHandler(
  request: FastifyRequest<{
    Querystring: {
      chainId?: string;
      window?: string;  // '1h', '24h', '7d'
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { chainId, window = '24h' } = request.query;
    
    const windowMs = {
      '1h': 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000,
      '7d': 7 * 24 * 60 * 60 * 1000,
    }[window] || 24 * 60 * 60 * 1000;
    
    const cutoff = Date.now() - windowMs;
    
    const filter: Record<string, unknown> = {
      indexedAt: { $gte: cutoff },
    };
    if (chainId) filter.chainId = parseInt(chainId);
    
    const [totalLogs, uniqueTokens, exchangeTransfers] = await Promise.all([
      ERC20LogModel.countDocuments(filter),
      ERC20LogModel.distinct('tokenAddress', filter).then(arr => arr.length),
      ERC20LogModel.countDocuments({
        ...filter,
        $or: [
          { fromLabel: { $regex: /^exchange:/ } },
          { toLabel: { $regex: /^exchange:/ } },
        ],
      }),
    ]);
    
    return {
      ok: true,
      window,
      stats: {
        totalLogs,
        uniqueTokens,
        exchangeTransfers,
        exchangePercentage: totalLogs > 0 
          ? Math.round((exchangeTransfers / totalLogs) * 100) 
          : 0,
      },
    };
  } catch (error) {
    console.error('[ERC20Indexer] Get stats error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function erc20IndexerRoutes(fastify: FastifyInstance): Promise<void> {
  // Status & Control
  fastify.get('/status', getStatusHandler);
  fastify.post('/sync', triggerSyncHandler);
  fastify.post('/backfill', backfillHandler);
  fastify.get('/backfill/status', backfillStatusHandler);
  fastify.post('/reset', resetHandler);
  
  // Data access
  fastify.get('/logs', getLogsHandler);
  fastify.get('/stats', getStatsHandler);
  
  // Labels
  fastify.get('/labels', getLabelsHandler);
  fastify.post('/labels', addLabelHandler);
  
  console.log('[OnChain V2] ERC20 Indexer routes registered');
}

console.log('[OnChain V2] ERC20 Indexer Routes module loaded');
