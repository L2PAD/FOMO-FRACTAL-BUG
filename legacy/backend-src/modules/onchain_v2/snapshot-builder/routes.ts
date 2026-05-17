/**
 * OnChain V2 — Snapshot Builder Routes
 * =====================================
 * 
 * Endpoints for building snapshots from indexed data.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { snapshotBuilder } from './service.js';
import { OnchainObservationModel } from '../core/persistence/models.js';
import type { OnchainWindow } from '../core/contracts.js';

// ═══════════════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════════════

/**
 * POST /tick — Build single snapshot
 */
async function tickHandler(
  request: FastifyRequest<{
    Body: {
      chainId: number;
      symbol: string;
      window: OnchainWindow;
      t0?: number;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { chainId, symbol, window, t0 } = request.body;
    
    if (!chainId || !symbol || !window) {
      return { ok: false, error: 'chainId, symbol, window required' };
    }
    
    const result = await snapshotBuilder.buildSnapshot(chainId, symbol, window, t0);
    
    return {
      ok: true,
      snapshot: {
        symbol: result.symbol,
        window: result.window,
        t0: result.t0,
        state: result.state,
        confidence: result.confidence,
        metrics: {
          activeAddresses: result.metrics.activeAddresses,
          txCount: result.metrics.txCount,
          transferCount: result.metrics.transferCount,
          largeTransfersCount: result.metrics.largeTransfersCount,
          distributionSkew: result.metrics.distributionSkew,
          exchangeNetFlow: result.metrics.exchangeNetFlow,
          completeness: result.metrics.completeness,
          // DEX metrics
          dexSwapCount: result.metrics.dexSwapCount,
          dexBuyCount: result.metrics.dexBuyCount,
          dexSellCount: result.metrics.dexSellCount,
          dexBuySellRatio: result.metrics.dexBuySellRatio,
          dexActivity: result.metrics.dexActivity,
          dexImbalance: result.metrics.dexImbalance,
          dexWhaleSwapCount: result.metrics.dexWhaleSwapCount,
        },
        saved: result.saved,
      },
    };
  } catch (error) {
    console.error('[SnapshotBuilder] Tick error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * POST /backfill-metrics — Backfill observations for window
 */
async function backfillMetricsHandler(
  request: FastifyRequest<{
    Body: {
      chainId: number;
      symbol: string;
      window: OnchainWindow;
      days?: number;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { chainId, symbol, window, days = 30 } = request.body;
    
    if (!chainId || !symbol || !window) {
      return { ok: false, error: 'chainId, symbol, window required' };
    }
    
    // Run in background
    snapshotBuilder.backfillObservations(chainId, symbol, window, days).catch(err => {
      console.error('[SnapshotBuilder] Backfill error:', err);
    });
    
    return {
      ok: true,
      message: `Backfill started: ${symbol} ${window} for ${days} days`,
    };
  } catch (error) {
    console.error('[SnapshotBuilder] Backfill error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * GET /latest — Get latest observation
 */
async function latestHandler(
  request: FastifyRequest<{
    Querystring: {
      symbol?: string;
      window?: OnchainWindow;
    };
  }>,
  reply: FastifyReply
) {
  try {
    const { symbol, window } = request.query;
    
    const query: any = {};
    if (symbol) query.symbol = symbol;
    if (window) query.window = window;
    
    const observation = await OnchainObservationModel.findOne(query)
      .sort({ createdAt: -1 })
      .lean();
    
    if (!observation) {
      return { ok: false, error: 'No observations found' };
    }
    
    return {
      ok: true,
      observation: {
        id: observation.id,
        symbol: observation.symbol,
        window: observation.window,
        t0: observation.t0,
        state: observation.state,
        snapshot: observation.snapshot,
        metrics: observation.metrics,
        diagnostics: observation.diagnostics,
        createdAt: observation.createdAt,
      },
    };
  } catch (error) {
    console.error('[SnapshotBuilder] Latest error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function snapshotBuilderRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.post('/tick', tickHandler);
  fastify.post('/backfill-metrics', backfillMetricsHandler);
  fastify.get('/latest', latestHandler);
  
  console.log('[OnChain V2] Snapshot Builder routes registered');
}

console.log('[OnChain V2] Snapshot Builder Routes module loaded');
