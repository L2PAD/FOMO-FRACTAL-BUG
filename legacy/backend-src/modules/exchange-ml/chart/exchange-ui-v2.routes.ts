/**
 * Exchange UI V2 Routes
 * =======================
 * 
 * BLOCK E1-E5: Production-grade endpoints for Exchange UI
 * Symmetric with Sentiment UI V2 Routes
 * 
 * Endpoints:
 * - GET /api/market/chart/exchange-v2         - Chart with reliability adjustments
 * - GET /api/market/exchange/performance-v2   - Performance history RAW vs ADJUSTED
 * - GET /api/market/exchange/top-alts-v2      - Top alts with reliability filter
 * - GET /api/market/exchange/equity-v2        - Mini equity curve
 */

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { getExchangeChartV2Service } from './exchange-chart-v2.service.js';
import { getExchangeChartV3Service } from './exchange-chart-v3.service.js';
import { getExchangePerformanceV2Service } from './exchange-performance-v2.service.js';
import { getExchangeTopAltsV2Service } from './exchange-top-alts-v2.service.js';
import { getExchangeEquityV2Service } from './exchange-equity-v2.service.js';
import type { Horizon } from './exchange-chart-v2.types.js';

interface ChartQuery {
  symbol?: string;
  horizon?: string;
}

interface PerformanceQuery {
  symbol?: string;
  horizon?: string;
  limit?: string;
}

interface TopAltsQuery {
  horizon?: string;
  limit?: string;
}

interface EquityQuery {
  symbol?: string;
  period?: string;
}

export async function registerExchangeUIV2Routes(fastify: FastifyInstance): Promise<void> {
  const chartService = getExchangeChartV2Service();
  const chartV3Service = getExchangeChartV3Service();
  const performanceService = getExchangePerformanceV2Service();
  const topAltsService = getExchangeTopAltsV2Service();
  const equityService = getExchangeEquityV2Service();

  /**
   * GET /api/market/chart/exchange-v2
   * 
   * Full chart data with reliability adjustments
   */
  fastify.get<{
    Querystring: ChartQuery;
  }>('/api/market/chart/exchange-v2', async (request, reply) => {
    const { symbol = 'BTC', horizon = '7D' } = request.query;

    try {
      const validHorizon = validateHorizon(horizon);
      const result = await chartService.getChart({
        symbol: symbol.toUpperCase(),
        horizon: validHorizon,
      });

      return reply.send(result);
    } catch (err: any) {
      console.error('[ExchangeChartV2] Error:', err.message);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  /**
   * GET /api/market/exchange/performance-v2
   * 
   * Performance history with RAW vs ADJUSTED values
   */
  fastify.get<{
    Querystring: PerformanceQuery;
  }>('/api/market/exchange/performance-v2', async (request, reply) => {
    const { symbol = 'BTC', horizon = '7D', limit = '30' } = request.query;

    try {
      const validHorizon = validateHorizon(horizon);
      const result = await performanceService.getPerformance(
        symbol.toUpperCase(),
        validHorizon,
        parseInt(limit, 10)
      );

      return reply.send(result);
    } catch (err: any) {
      console.error('[ExchangePerformanceV2] Error:', err.message);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  /**
   * GET /api/market/exchange/top-alts-v2
   * 
   * Top altcoins with reliability-adjusted values
   */
  fastify.get<{
    Querystring: TopAltsQuery;
  }>('/api/market/exchange/top-alts-v2', async (request, reply) => {
    const { horizon = '7D', limit = '20' } = request.query;

    try {
      const validHorizon = validateHorizon(horizon);
      const result = await topAltsService.getTopAlts(
        validHorizon,
        parseInt(limit, 10)
      );

      return reply.send(result);
    } catch (err: any) {
      console.error('[ExchangeTopAltsV2] Error:', err.message);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  /**
   * GET /api/market/exchange/equity-v2
   * 
   * Mini equity curve for paper performance
   */
  fastify.get<{
    Querystring: EquityQuery;
  }>('/api/market/exchange/equity-v2', async (request, reply) => {
    const { symbol = 'BTC', period = '90d' } = request.query;

    try {
      const result = await equityService.getEquity(symbol.toUpperCase(), period);
      return reply.send(result);
    } catch (err: any) {
      console.error('[ExchangeEquityV2] Error:', err.message);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  /**
   * GET /api/market/chart/exchange-v3
   * Rolling Forecast Curve — real forecast points, no simulations
   */
  fastify.get<{
    Querystring: { asset?: string; horizon?: string; lookback?: string };
  }>('/api/market/chart/exchange-v3', async (request, reply) => {
    const { asset = 'BTC', horizon = '7D' } = request.query;
    const h = horizon.toUpperCase();
    const validHorizon = h === '30D' ? '30D' : h === '1D' ? '1D' : '7D';

    try {
      const result = await chartV3Service.getChart({
        asset: asset.toUpperCase(),
        horizon: validHorizon as '7D' | '30D',
      });
      return reply.send(result);
    } catch (err: any) {
      console.error('[ExchangeChartV3] Error:', err.message);
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  /**
   * GET /api/market/chart/forecast-evolution
   * AI Reasoning Visualization — how model opinion changed over time
   */
  fastify.get<{
    Querystring: { asset?: string; horizon?: string };
  }>('/api/market/chart/forecast-evolution', async (request, reply) => {
    const { asset = 'BTC', horizon = '7' } = request.query;
    const horizonDays = parseInt(horizon, 10) || 7;

    try {
      const { ForecastEvolutionService } = await import('./forecast-evolution.service.js');
      const service = ForecastEvolutionService.getInstance();
      const result = await service.getEvolution(asset.toUpperCase(), horizonDays);
      return reply.send(result);
    } catch (err: any) {
      console.error('[ForecastEvolution] Error:', err.message);
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  console.log('[Exchange-UI-V2] Routes registered:');
  console.log('  - GET /api/market/chart/exchange-v2');
  console.log('  - GET /api/market/chart/exchange-v3');
  console.log('  - GET /api/market/chart/forecast-evolution');
  console.log('  - GET /api/market/exchange/performance-v2');
  console.log('  - GET /api/market/exchange/top-alts-v2');
  console.log('  - GET /api/market/exchange/equity-v2');
}

function validateHorizon(horizon: string): Horizon {
  const valid: Horizon[] = ['24H', '7D', '30D'];
  const upper = horizon.toUpperCase() as Horizon;
  
  // Map common variants
  if (horizon === '1D') return '24H';
  
  if (valid.includes(upper)) {
    return upper;
  }
  
  return '7D'; // Default
}
