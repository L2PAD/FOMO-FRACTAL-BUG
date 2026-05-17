/**
 * Sentiment Aggregate Routes
 * ==========================
 * 
 * BLOCK 4: Public API для sentiment aggregates
 * BLOCK 9: Shadow Mode integration (24H only)
 * 
 * Endpoints:
 * - GET /api/sentiment/aggregate - Latest aggregate для symbol/window
 * - GET /api/sentiment/aggregate/series - Time series для графика
 * - GET /api/sentiment/aggregate/all - All symbols summary
 */

import type { FastifyInstance } from 'fastify';
import { sentimentAggregationService } from '../services/sentiment-aggregation.service.js';
import { SentimentAggregateModel } from '../storage/sentiment-aggregate.model.js';
import { SENTIMENT_TOP20 } from '../config/top20-symbols.js';
import { SentimentBinaryInferenceService } from '../binary/sentiment.binary.inference.service.js';
import { getSentimentShadowService } from '../shadow/sentiment.shadow.service.js';

// Helper to get ML decision and optionally record shadow (24H only)
async function getMLDecision(aggregate: any, window: '24H' | '7D' | '30D', recordShadow = false) {
  try {
    const ml = await SentimentBinaryInferenceService.infer({
      window,
      sampleLike: {
        symbol: aggregate.symbol,
        asOf: aggregate.asOf || new Date(),
        bias: aggregate.bias ?? 0,
        score: aggregate.score ?? 0.5,
        weightedScore: aggregate.weightedScore ?? aggregate.score ?? 0.5,
        weightedConfidence: aggregate.weightedConfidence ?? aggregate.confidence ?? 0.5,
        eventsCount: aggregate.eventsCount ?? 0,
        authorScoreMean: aggregate.authorScoreMean ?? 0.5,
        influenceMean: aggregate.influenceMean ?? 0.5,
        botProbMean: aggregate.botProbMean ?? 0.5,
      },
    });

    // BLOCK 9: Record shadow decision for 24H (fire and forget)
    if (recordShadow && window === '24H' && aggregate.symbol && aggregate.asOf) {
      const bias = aggregate.bias ?? 0;
      const ruleAction = bias > 0.1 ? 'LONG' : bias < -0.1 ? 'SHORT' : 'NEUTRAL';
      
      getSentimentShadowService().recordShadowDecision({
        symbol: aggregate.symbol,
        asOf: aggregate.asOf,
        ruleAction,
        ruleConfidence: Math.abs(bias),
        ruleBias: bias,
        score: aggregate.score ?? 0.5,
        weightedScore: aggregate.weightedScore ?? aggregate.score ?? 0.5,
        weightedConfidence: aggregate.weightedConfidence ?? aggregate.confidence ?? 0.5,
        eventsCount: aggregate.eventsCount ?? 0,
        authorScoreMean: aggregate.authorScoreMean ?? 0.5,
        influenceMean: aggregate.influenceMean ?? 0.5,
        botProbMean: aggregate.botProbMean ?? 0.5,
      }).catch(err => {
        // Silent fail - shadow recording should not affect API response
        console.warn(`[Shadow] Failed to record for ${aggregate.symbol}:`, err.message);
      });
    }

    return {
      action: ml.action,
      confidence: Math.max(0, Math.min(1, ml.confidence)),
      pUp: Math.max(0, Math.min(1, ml.pUp)),
      pDown: Math.max(0, Math.min(1, ml.pDown)),
      modelId: ml.meta.modelId,
    };
  } catch (e) {
    // Don't break API if ML fails
    return undefined;
  }
}

export async function registerSentimentAggregateRoutes(app: FastifyInstance): Promise<void> {

  /**
   * GET /aggregate - Latest aggregate for symbol and window
   */
  app.get('/aggregate', async (request, reply) => {
    try {
      const query = request.query as { symbol?: string; window?: string };
      const symbol = query.symbol?.toUpperCase() || 'BTC';
      const window = (query.window?.toUpperCase() || '7D') as '24H' | '7D' | '30D';

      if (!['24H', '7D', '30D'].includes(window)) {
        return reply.status(400).send({
          ok: false,
          error: 'Invalid window. Use 24H, 7D, or 30D',
        });
      }

      const data = await sentimentAggregationService.getLatest(symbol, window);

      if (!data) {
        return reply.send({
          ok: false,
          message: `No data for ${symbol}/${window}`,
        });
      }

      // Add ML decision
      const mlDecision = await getMLDecision(data, window);

      return reply.send({
        ok: true,
        data: {
          ...data,
          mlDecision,
        },
      });
    } catch (error: any) {
      return reply.status(500).send({
        ok: false,
        error: error.message,
      });
    }
  });

  /**
   * GET /aggregate/series - Time series for chart
   */
  app.get('/aggregate/series', async (request, reply) => {
    try {
      const query = request.query as { symbol?: string; window?: string; days?: string };
      const symbol = query.symbol?.toUpperCase() || 'BTC';
      const window = (query.window?.toUpperCase() || '7D') as '24H' | '7D' | '30D';
      const days = Math.min(parseInt(query.days || '30', 10), 90);

      if (!['24H', '7D', '30D'].includes(window)) {
        return reply.status(400).send({
          ok: false,
          error: 'Invalid window. Use 24H, 7D, or 30D',
        });
      }

      const points = await sentimentAggregationService.getSeries(symbol, window, days);

      return reply.send({
        ok: true,
        symbol,
        window,
        days,
        points,
      });
    } catch (error: any) {
      return reply.status(500).send({
        ok: false,
        error: error.message,
      });
    }
  });

  /**
   * GET /aggregate/all - Summary for all TOP20 symbols
   */
  app.get('/aggregate/all', async (request, reply) => {
    try {
      const query = request.query as { window?: string };
      const window = (query.window?.toUpperCase() || '7D') as '24H' | '7D' | '30D';

      if (!['24H', '7D', '30D'].includes(window)) {
        return reply.status(400).send({
          ok: false,
          error: 'Invalid window. Use 24H, 7D, or 30D',
        });
      }

      // Get latest for all symbols with ML decision
      const results = await Promise.all(
        SENTIMENT_TOP20.map(async symbol => {
          const agg = await sentimentAggregationService.getLatest(symbol, window);
          const baseData = agg || {
            symbol,
            window,
            score: 0.5,
            bias: 0,
            confidence: 0,
            eventsCount: 0,
            direction: 'NEUTRAL',
            expectedReturnPct: 0,
          };
          
          // Add ML decision (record shadow for 24H when we have real data)
          const shouldRecordShadow = window === '24H' && agg !== null;
          const mlDecision = await getMLDecision(baseData, window, shouldRecordShadow);
          
          return {
            ...baseData,
            mlDecision,
          };
        })
      );

      // Sort by absolute bias (strongest signals first)
      const sorted = results.sort((a, b) => Math.abs(b.bias) - Math.abs(a.bias));

      return reply.send({
        ok: true,
        window,
        count: sorted.length,
        data: sorted,
      });
    } catch (error: any) {
      return reply.status(500).send({
        ok: false,
        error: error.message,
      });
    }
  });

  /**
   * GET /aggregate/stats - Overall stats
   */
  app.get('/aggregate/stats', async (request, reply) => {
    try {
      // Count aggregates
      const total = await SentimentAggregateModel.countDocuments();
      
      // By window
      const byWindow = await SentimentAggregateModel.aggregate([
        { $group: { _id: '$window', count: { $sum: 1 } } },
      ]);

      // Latest per symbol
      const latestBySymbol = await SentimentAggregateModel.aggregate([
        { $sort: { asOf: -1 } },
        { $group: { 
          _id: { symbol: '$symbol', window: '$window' },
          latest: { $first: '$asOf' },
          score: { $first: '$score' },
          bias: { $first: '$bias' },
        }},
        { $sort: { '_id.symbol': 1, '_id.window': 1 } },
      ]);

      return reply.send({
        ok: true,
        data: {
          total,
          byWindow: Object.fromEntries(byWindow.map(w => [w._id, w.count])),
          top20Symbols: SENTIMENT_TOP20,
          latestCount: latestBySymbol.length,
        },
      });
    } catch (error: any) {
      return reply.status(500).send({
        ok: false,
        error: error.message,
      });
    }
  });

  console.log('[Sentiment-ML] Aggregate routes registered at /api/sentiment/aggregate/*');
}
