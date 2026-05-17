/**
 * Market Series Routes
 * =====================
 * 
 * PHASE 1: Liquidity & Alt Rotation Engine
 * 
 * API endpoints for market series data.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  getMarketSeries,
  getLatestMarketValue,
  getAllLatestMarketValues,
} from './market.service';
import {
  getMarketJobStatus,
  forceRunMarketJob,
  startMarketJob,
  stopMarketJob,
} from './market.job';
import { MARKET_SERIES_KEYS, MarketSeriesKey } from './market.model';

// Window string to ms conversion
const WINDOW_MAP: Record<string, number> = {
  '1h': 60 * 60 * 1000,
  '6h': 6 * 60 * 60 * 1000,
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
};

interface SeriesQuery {
  key: string;
  window?: string;
}

/**
 * GET /market/series - Get time series for a specific key
 */
async function getSeriesHandler(
  request: FastifyRequest<{ Querystring: SeriesQuery }>,
  reply: FastifyReply
) {
  const { key, window = '30d' } = request.query;

  // Validate key
  const validKeys = Object.values(MARKET_SERIES_KEYS);
  if (!validKeys.includes(key as MarketSeriesKey)) {
    return {
      ok: false,
      error: `Invalid key. Valid keys: ${validKeys.join(', ')}`,
    };
  }

  // Parse window
  const windowMs = WINDOW_MAP[window] || WINDOW_MAP['30d'];

  try {
    const series = await getMarketSeries(key as MarketSeriesKey, windowMs);
    return {
      ok: true,
      key,
      window,
      count: series.length,
      series,
    };
  } catch (error) {
    console.error('[Market Routes] Error fetching series:', error);
    return {
      ok: false,
      error: 'Failed to fetch series',
    };
  }
}

/**
 * GET /market/latest - Get all latest values
 */
async function getLatestHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const values = await getAllLatestMarketValues();
    const jobStatus = getMarketJobStatus();

    return {
      ok: true,
      values,
      job: jobStatus,
      timestamp: Date.now(),
    };
  } catch (error) {
    console.error('[Market Routes] Error fetching latest:', error);
    return {
      ok: false,
      error: 'Failed to fetch latest values',
    };
  }
}

/**
 * GET /market/keys - List available series keys
 */
async function getKeysHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  return {
    ok: true,
    keys: Object.values(MARKET_SERIES_KEYS),
    description: {
      PURE_ALT_CAP: 'Total altcoin market cap excluding BTC and stablecoins (USD)',
      STABLE_SUPPLY_TOTAL: 'Combined USDT + USDC supply (USD)',
      STABLE_DOMINANCE: 'Stablecoin share of total market cap (%)',
      ETHBTC_RATIO: 'ETH market cap / BTC market cap ratio',
      BTC_DOMINANCE_RAW: 'BTC share of total market cap (%)',
    },
  };
}

/**
 * GET /market/job/status - Get job status
 */
async function getJobStatusHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const status = getMarketJobStatus();
  return {
    ok: true,
    ...status,
  };
}

/**
 * POST /market/job/run - Force run job (admin)
 */
async function forceRunHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    await forceRunMarketJob();
    return {
      ok: true,
      message: 'Job executed',
      timestamp: Date.now(),
    };
  } catch (error) {
    return {
      ok: false,
      error: 'Failed to run job',
    };
  }
}

/**
 * POST /market/job/start - Start job (admin)
 */
async function startJobHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  startMarketJob();
  return {
    ok: true,
    message: 'Job started',
  };
}

/**
 * POST /market/job/stop - Stop job (admin)
 */
async function stopJobHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  stopMarketJob();
  return {
    ok: true,
    message: 'Job stopped',
  };
}

/**
 * Register market routes
 */
export async function marketRoutes(fastify: FastifyInstance): Promise<void> {
  // Public endpoints
  fastify.get('/series', getSeriesHandler);
  fastify.get('/latest', getLatestHandler);
  fastify.get('/keys', getKeysHandler);

  // Admin endpoints
  fastify.get('/job/status', getJobStatusHandler);
  fastify.post('/job/run', forceRunHandler);
  fastify.post('/job/start', startJobHandler);
  fastify.post('/job/stop', stopJobHandler);

  // Register liquidity sub-routes (PHASE 2.1)
  const { liquidityRoutes } = await import('./liquidity');
  await fastify.register(liquidityRoutes, { prefix: '/liquidity' });

  // Register altflow sub-routes (BLOCK 3.6)
  const { altflowRoutes } = await import('./altflow');
  await fastify.register(altflowRoutes, { prefix: '/altflow' });

  // Register pricing sub-routes (STEP 1: USD Valuation Layer)
  const { pricingRoutes } = await import('./pricing');
  await fastify.register(pricingRoutes, { prefix: '/pricing' });

  // Register assets sub-routes (PHASE 4: Token Explorer)
  const { assetsRoutes } = await import('./assets');
  await fastify.register(assetsRoutes, { prefix: '/assets' });

  // Register actors sub-routes (PHASE 5: Actors/Entities)
  const { actorsRoutes } = await import('./actors');
  await fastify.register(actorsRoutes, { prefix: '/actors' });

  // Register token deep routes (PHASE D: Token Consolidation)
  const { tokenRoutes } = await import('./tokens/tokens.routes');
  await fastify.register(tokenRoutes, { prefix: '/tokens' });

  console.log('[Market Routes] Registered');
}

export default marketRoutes;
