/**
 * Sentiment ML Performance Routes
 * =================================
 * 
 * BLOCK 8: Admin API for ML performance tracking.
 * 
 * Endpoints:
 * - GET /equity — Mini equity curve from samples
 * - GET /metrics — Overall ML metrics
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { SentimentDirSampleModel } from '../dataset/sentiment-dir-sample.model.js';
import { SentimentWindow } from '../contracts/sentiment-ml.types.js';

interface EquityQuery {
  symbol?: string;
  window?: string;
  days?: string;
}

async function sentimentMlPerfRoutes(app: FastifyInstance): Promise<void> {
  /**
   * GET /equity — Mini equity curve
   * 
   * Simulates simple strategy:
   * - ML action = LONG → take position, earn forward return
   * - ML action = SHORT → take short, earn -forward return
   * - ML action = NEUTRAL → no trade
   */
  app.get('/equity', async (req: FastifyRequest<{ Querystring: EquityQuery }>) => {
    const { symbol, window: win = '24H', days: daysStr = '90' } = req.query;
    const window = (win.toUpperCase() || '24H') as SentimentWindow;
    const days = Math.min(parseInt(daysStr, 10), 180);

    const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

    // Build query
    const query: any = {
      window,
      asOf: { $gte: since },
      'ml.action': { $exists: true },
    };
    
    if (symbol) {
      query.symbol = symbol.toUpperCase();
    }

    const samples = await SentimentDirSampleModel.find(query)
      .sort({ asOf: 1 })
      .lean();

    if (!samples.length) {
      return {
        ok: true,
        symbol: symbol || 'ALL',
        window,
        days,
        totalSamples: 0,
        trades: 0,
        points: [],
        metrics: {
          finalEquity: 1,
          maxDrawdown: 0,
          sharpeProxy: 0,
          winRate: 0,
        },
      };
    }

    // Simulate equity
    let equity = 1;
    let peak = 1;
    let maxDrawdown = 0;
    let trades = 0;
    let wins = 0;
    const returns: number[] = [];

    const points: Array<{ t: string; equity: number; dd: number; action?: string }> = [];

    for (const s of samples) {
      const ml = s.ml as { action: string; pUp: number; confidence: number } | undefined;
      const ret = (s.returnPct ?? 0) as number;

      if (!ml?.action || ml.action === 'NEUTRAL') {
        // No trade, equity unchanged
        const dd = (equity - peak) / peak;
        points.push({
          t: (s.asOf as Date).toISOString(),
          equity,
          dd,
          action: 'NEUTRAL',
        });
        continue;
      }

      // Calculate trade return
      let tradeReturn = 0;
      if (ml.action === 'LONG') {
        tradeReturn = ret;
      } else if (ml.action === 'SHORT') {
        tradeReturn = -ret;
      }

      // Update equity (multiplicative)
      equity *= (1 + tradeReturn);
      trades++;
      returns.push(tradeReturn);

      if (tradeReturn > 0) wins++;

      // Update peak and drawdown
      peak = Math.max(peak, equity);
      const dd = (equity - peak) / peak;
      maxDrawdown = Math.min(maxDrawdown, dd);

      points.push({
        t: (s.asOf as Date).toISOString(),
        equity,
        dd,
        action: ml.action,
      });
    }

    // Calculate metrics
    const avgReturn = returns.length > 0 
      ? returns.reduce((a, b) => a + b, 0) / returns.length 
      : 0;
    
    const variance = returns.length > 1
      ? returns.reduce((sum, r) => sum + (r - avgReturn) ** 2, 0) / (returns.length - 1)
      : 0;
    
    const stdDev = Math.sqrt(variance);
    const sharpeProxy = stdDev > 0 ? avgReturn / stdDev : 0;
    const winRate = trades > 0 ? wins / trades : 0;

    return {
      ok: true,
      symbol: symbol || 'ALL',
      window,
      days,
      totalSamples: samples.length,
      trades,
      points,
      metrics: {
        finalEquity: equity,
        maxDrawdown: Math.abs(maxDrawdown),
        sharpeProxy,
        winRate,
        avgReturn,
      },
    };
  });

  /**
   * GET /metrics — Overall ML metrics summary
   */
  app.get('/metrics', async (req: FastifyRequest<{ Querystring: { window?: string } }>) => {
    const window = (req.query.window?.toUpperCase() || '24H') as SentimentWindow;

    // Get all samples with ML
    const samples = await SentimentDirSampleModel.find({
      window,
      'ml.action': { $exists: true },
    }).lean();

    if (!samples.length) {
      return {
        ok: true,
        window,
        totalSamples: 0,
        metrics: null,
      };
    }

    // Calculate metrics
    let longTrades = 0, shortTrades = 0, neutralTrades = 0;
    let longWins = 0, shortWins = 0;
    let longReturn = 0, shortReturn = 0;

    for (const s of samples) {
      const ml = s.ml as { action: string } | undefined;
      const ret = (s.returnPct ?? 0) as number;

      if (!ml) continue;

      if (ml.action === 'LONG') {
        longTrades++;
        longReturn += ret;
        if (ret > 0) longWins++;
      } else if (ml.action === 'SHORT') {
        shortTrades++;
        shortReturn -= ret; // Short profits when price drops
        if (ret < 0) shortWins++;
      } else {
        neutralTrades++;
      }
    }

    return {
      ok: true,
      window,
      totalSamples: samples.length,
      metrics: {
        long: {
          trades: longTrades,
          wins: longWins,
          winRate: longTrades > 0 ? longWins / longTrades : 0,
          totalReturn: longReturn,
          avgReturn: longTrades > 0 ? longReturn / longTrades : 0,
        },
        short: {
          trades: shortTrades,
          wins: shortWins,
          winRate: shortTrades > 0 ? shortWins / shortTrades : 0,
          totalReturn: shortReturn,
          avgReturn: shortTrades > 0 ? shortReturn / shortTrades : 0,
        },
        neutral: {
          trades: neutralTrades,
        },
        combined: {
          totalTrades: longTrades + shortTrades,
          winRate: (longTrades + shortTrades) > 0 
            ? (longWins + shortWins) / (longTrades + shortTrades) 
            : 0,
          totalReturn: longReturn + shortReturn,
        },
      },
    };
  });

  console.log('[Sentiment-ML] Performance routes registered');
}

// Export wrapped in fastify-plugin
export default fp(sentimentMlPerfRoutes, {
  name: 'sentiment-ml-perf-routes',
  fastify: '4.x',
});

export { sentimentMlPerfRoutes };
