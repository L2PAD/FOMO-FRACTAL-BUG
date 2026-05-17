/**
 * Sentiment UI V2 Routes
 * =======================
 * 
 * BLOCK P1.1 + P1.2: Production-grade endpoints for Sentiment UI
 * 
 * Endpoints:
 * - GET /api/market/chart/sentiment-v2      - Chart with reliability adjustments
 * - GET /api/market/sentiment/performance-v2 - Performance history RAW vs ADJUSTED
 * - GET /api/market/sentiment/top-alts-v2    - Top alts with reliability filter
 */

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { getSentimentChartV2Service } from './sentiment-chart-v2.service.js';
import { getSentimentPerformanceV2Service } from './sentiment-performance-v2.service.js';
import { getSentimentTopAltsV2Service } from './sentiment-top-alts-v2.service.js';
import { getSentimentEquityV2Service } from './sentiment-equity-v2.service.js';
import type { Horizon } from './sentiment-chart-v2.types.js';

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

export async function registerSentimentUIV2Routes(fastify: FastifyInstance): Promise<void> {
  const chartService = getSentimentChartV2Service();
  const performanceService = getSentimentPerformanceV2Service();
  const topAltsService = getSentimentTopAltsV2Service();
  const equityService = getSentimentEquityV2Service();

  /**
   * GET /api/market/chart/sentiment-v2
   * 
   * Full chart data with reliability adjustments
   */
  fastify.get<{
    Querystring: ChartQuery;
  }>('/api/market/chart/sentiment-v2', async (request, reply) => {
    const { symbol = 'BTC', horizon = '7D' } = request.query;

    try {
      const validHorizon = validateHorizon(horizon);
      const result = await chartService.getChart({
        symbol: symbol.toUpperCase(),
        horizon: validHorizon,
      });

      return reply.send(result);
    } catch (err: any) {
      console.error('[SentimentChartV2] Error:', err.message);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  /**
   * GET /api/market/sentiment/performance-v2
   * 
   * Performance history with RAW vs ADJUSTED values
   */
  fastify.get<{
    Querystring: PerformanceQuery;
  }>('/api/market/sentiment/performance-v2', async (request, reply) => {
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
      console.error('[SentimentPerformanceV2] Error:', err.message);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  /**
   * GET /api/market/sentiment/top-alts-v2
   * 
   * Top altcoins with reliability-adjusted values
   */
  fastify.get<{
    Querystring: TopAltsQuery;
  }>('/api/market/sentiment/top-alts-v2', async (request, reply) => {
    const { horizon = '7D', limit = '20' } = request.query;

    try {
      const validHorizon = validateHorizon(horizon);
      const result = await topAltsService.getTopAlts(
        validHorizon,
        parseInt(limit, 10)
      );

      return reply.send(result);
    } catch (err: any) {
      console.error('[SentimentTopAltsV2] Error:', err.message);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  /**
   * GET /api/market/sentiment/equity-v2
   * 
   * Mini equity curve for paper performance
   */
  fastify.get<{
    Querystring: EquityQuery;
  }>('/api/market/sentiment/equity-v2', async (request, reply) => {
    const { symbol = 'BTC', period = '90d' } = request.query;

    try {
      const result = await equityService.getEquity(symbol.toUpperCase(), period);
      return reply.send(result);
    } catch (err: any) {
      console.error('[SentimentEquityV2] Error:', err.message);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  console.log('[Sentiment-UI-V2] Routes registered:');
  console.log('  - GET /api/market/chart/sentiment-v2');
  console.log('  - GET /api/market/sentiment/performance-v2');
  console.log('  - GET /api/market/sentiment/top-alts-v2');
  console.log('  - GET /api/market/sentiment/equity-v2');
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
