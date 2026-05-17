/**
 * LiquidityScore Routes
 * ======================
 * 
 * PHASE 2.1 + 2.3: API endpoints for Alt Liquidity
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  getLatestLiquidity,
  getLiquiditySeries,
  getLiquidityHealth,
  tickLiquidity,
} from './liquidity.service';
import {
  getLiquidityJobStatus,
  forceRunLiquidityJob,
  startLiquidityJob,
  stopLiquidityJob,
} from './liquidity.job';
import { AddressLabelModel } from '../../ingestion/erc20/models';
import { CEX_LABELS } from './cex-labels.seed';

interface SeriesQuery {
  window?: string;
}

/**
 * GET /liquidity/latest - Get latest liquidity score
 */
async function getLatestHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const result = await getLatestLiquidity();
    return result;
  } catch (error) {
    console.error('[Liquidity Routes] Error fetching latest:', error);
    return {
      ok: false,
      error: 'Failed to compute liquidity score',
    };
  }
}

/**
 * GET /liquidity/series - Get liquidity series
 */
async function getSeriesHandler(
  request: FastifyRequest<{ Querystring: SeriesQuery }>,
  reply: FastifyReply
) {
  const { window = '30d' } = request.query;

  try {
    const result = await getLiquiditySeries(window);
    return result;
  } catch (error) {
    console.error('[Liquidity Routes] Error fetching series:', error);
    return {
      ok: false,
      error: 'Failed to fetch liquidity series',
    };
  }
}

/**
 * GET /liquidity/health - Health check
 */
async function getHealthHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const health = await getLiquidityHealth();
    const jobStatus = getLiquidityJobStatus();

    return {
      ok: health.ok,
      health,
      job: jobStatus,
    };
  } catch (error) {
    return {
      ok: false,
      error: 'Failed to check health',
    };
  }
}

/**
 * POST /liquidity/job/run - Force run tick
 */
async function forceRunHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    await forceRunLiquidityJob();
    const latest = await getLatestLiquidity();
    return {
      ok: true,
      message: 'Tick executed',
      result: {
        score: latest.score,
        regime: latest.regime,
        confidence: latest.confidence,
      },
    };
  } catch (error) {
    return {
      ok: false,
      error: 'Failed to run tick',
    };
  }
}

/**
 * GET /liquidity/job/status - Job status
 */
async function getJobStatusHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const status = getLiquidityJobStatus();
  return {
    ok: true,
    ...status,
  };
}

/**
 * POST /liquidity/job/start - Start job
 */
async function startJobHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  startLiquidityJob();
  return { ok: true, message: 'Job started' };
}

/**
 * POST /liquidity/job/stop - Stop job
 */
async function stopJobHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  stopLiquidityJob();
  return { ok: true, message: 'Job stopped' };
}

/**
 * GET /liquidity/flow - Get current flow data (Phase 2.2 debug)
 */
async function getFlowHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const { getFlowAggregation } = await import('./flow.service');
    const flow = await getFlowAggregation(24 * 60 * 60 * 1000);
    return {
      ok: true,
      ...flow,
    };
  } catch (error) {
    console.error('[Liquidity Routes] Error fetching flow:', error);
    return {
      ok: false,
      error: 'Failed to fetch flow data',
    };
  }
}

/**
 * POST /liquidity/labels/seed - Seed CEX labels (Phase 2.3)
 */
async function seedLabelsHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    let inserted = 0;
    let updated = 0;

    for (const label of CEX_LABELS) {
      const result = await AddressLabelModel.updateOne(
        { chainId: 1, address: label.address.toLowerCase() },
        {
          $set: {
            chainId: 1,
            address: label.address.toLowerCase(),
            type: 'exchange',
            name: label.name,
            subtype: label.subtype,
            source: label.source,
            confidence: 1.0,
            updatedAt: Date.now(),
          },
        },
        { upsert: true }
      );

      if (result.upsertedCount) inserted++;
      else if (result.modifiedCount) updated++;
    }

    return {
      ok: true,
      message: 'CEX labels seeded successfully',
      total: CEX_LABELS.length,
      inserted,
      updated,
    };
  } catch (error) {
    console.error('[Liquidity Routes] Error seeding labels:', error);
    return {
      ok: false,
      error: 'Failed to seed labels',
    };
  }
}

/**
 * GET /liquidity/labels - Get current exchange labels
 */
async function getLabelsHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const labels = await AddressLabelModel.find(
      { type: 'exchange' },
      { _id: 0, address: 1, name: 1, subtype: 1, source: 1, confidence: 1 }
    ).lean();

    const byExchange: Record<string, number> = {};
    for (const l of labels) {
      byExchange[l.name] = (byExchange[l.name] || 0) + 1;
    }

    return {
      ok: true,
      count: labels.length,
      byExchange,
      labels,
    };
  } catch (error) {
    console.error('[Liquidity Routes] Error fetching labels:', error);
    return {
      ok: false,
      error: 'Failed to fetch labels',
    };
  }
}

/**
 * Register liquidity routes
 */
export async function liquidityRoutes(fastify: FastifyInstance): Promise<void> {
  // Public endpoints
  fastify.get('/latest', getLatestHandler);
  fastify.get('/series', getSeriesHandler);
  fastify.get('/health', getHealthHandler);
  fastify.get('/flow', getFlowHandler);  // Phase 2.2 debug endpoint

  // Admin endpoints
  fastify.get('/job/status', getJobStatusHandler);
  fastify.post('/job/run', forceRunHandler);
  fastify.post('/job/start', startJobHandler);
  fastify.post('/job/stop', stopJobHandler);

  // CEX Labels (Phase 2.3)
  fastify.post('/labels/seed', seedLabelsHandler);
  fastify.get('/labels', getLabelsHandler);

  console.log('[Liquidity Routes] Registered');
}

export default liquidityRoutes;
