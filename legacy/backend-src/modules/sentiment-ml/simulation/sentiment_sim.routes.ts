/**
 * Sentiment Simulation Admin Routes
 * ===================================
 * 
 * BLOCK 7+8: Admin API for running simulations with CHOP Gate.
 * 
 * Endpoints:
 * - POST /run — Run simulation
 * - POST /grid — Run grid search for CHOP calibration
 * - GET /report — Get last report
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getSentimentSimulationRunner } from './sentiment_sim.runner.js';
import type { SimWindow, SimMode, SentimentSimConfig } from './sentiment_sim.types.js';
import type { ChopConfig } from '../risk/chop.types.js';

// Store last report in memory
let lastReport: any = null;
let gridResults: any[] = [];

async function sentimentSimRoutes(app: FastifyInstance): Promise<void> {
  const runner = getSentimentSimulationRunner();

  /**
   * POST /run — Run walk-forward simulation
   */
  app.post('/run', async (req: FastifyRequest<{ 
    Body: { 
      days?: number; 
      window?: string; 
      mode?: string;
      feeBps?: number;
      slippageBps?: number;
      chopGate?: boolean;
      minBias?: number;
      regimeFilter?: boolean;
      transitionScaling?: boolean;
      chopV1?: boolean;
      chopConfig?: Partial<ChopConfig>;
    } 
  }>) => {
    const body = req.body || {};
    
    const config: SentimentSimConfig = {
      days: Number(body.days) || 90,
      window: (body.window?.toUpperCase() || '24H') as SimWindow,
      mode: (body.mode?.toUpperCase() || 'RULE') as SimMode,
      startCapital: 1.0,
      feeBps: Number(body.feeBps) || 5,
      slippageBps: Number(body.slippageBps) || 3,
      chopGate: Boolean(body.chopGate) || false,
      minBias: Number(body.minBias) || 0,
      regimeFilter: Boolean(body.regimeFilter) || false,
      transitionScaling: Boolean(body.transitionScaling) || false,
      chopV1: Boolean(body.chopV1) || false,
      chopConfig: body.chopConfig,
    };

    console.log(`[Sim] Running ${config.days}D simulation for ${config.window} ${config.mode}`);
    console.log(`[Sim] Filters: chopGate=${config.chopGate}, chopV1=${config.chopV1}, regimeFilter=${config.regimeFilter}`);
    
    const report = await runner.run(config);
    lastReport = report;

    return {
      ok: true,
      status: report.status,
      config: report.config,
      metrics: {
        trades: report.metrics.trades,
        wins: report.metrics.wins,
        losses: report.metrics.losses,
        winRate: report.metrics.winRate,
        expectancy: report.metrics.expectancy,
        maxDD: report.metrics.maxDD,
        sharpeLike: report.metrics.sharpeLike,
        equityFinal: report.metrics.equityFinal,
        totalReturnPct: report.metrics.totalReturnPct,
      },
      formatted: {
        winRate: `${(report.metrics.winRate * 100).toFixed(1)}%`,
        expectancy: `${(report.metrics.expectancy * 100).toFixed(3)}%`,
        maxDD: `${(report.metrics.maxDD * 100).toFixed(1)}%`,
        sharpe: report.metrics.sharpeLike.toFixed(3),
        totalReturn: `${(report.metrics.totalReturnPct * 100).toFixed(2)}%`,
        equity: report.metrics.equityFinal.toFixed(4),
      },
      failReasons: report.failReasons,
      tradesCount: report.trades.length,
      equityCurvePoints: report.equityCurve.length,
      regime: report.regime,
      // Proactive regime stats
      proactiveRegimeStats: config.regimeFilter ? {
        chopSkipped: report.trades.filter((t: any) => t.regime === 'CHOP').length === 0 
          ? 'N/A (CHOP trades filtered)' 
          : undefined,
        transitionTrades: report.trades.filter((t: any) => t.regime === 'TRANSITION').length,
        trendTrades: report.trades.filter((t: any) => t.regime === 'TREND').length,
        avgTransitionSize: report.trades.filter((t: any) => t.sizeMultiplier === 0.5).length,
      } : undefined,
      monteCarlo: report.monteCarlo ? {
        iterations: report.monteCarlo.iterations,
        equityP5: report.monteCarlo.equityDistribution.p5.toFixed(4),
        equityMedian: report.monteCarlo.equityDistribution.median.toFixed(4),
        equityP95: report.monteCarlo.equityDistribution.p95.toFixed(4),
        maxDDMedian: `${(report.monteCarlo.maxDDDistribution.median * 100).toFixed(1)}%`,
        maxDDP95: `${(report.monteCarlo.maxDDDistribution.p95 * 100).toFixed(1)}%`,
        probabilityOfProfit: `${(report.monteCarlo.probabilityOfProfit * 100).toFixed(1)}%`,
        riskOfRuin: `${(report.monteCarlo.riskOfRuin * 100).toFixed(1)}%`,
      } : null,
      // CHOP V1 stats
      chopStats: report.chopStats,
    };
  });

  /**
   * POST /grid — Run grid search for CHOP calibration
   */
  app.post('/grid', async (req: FastifyRequest<{
    Body: {
      days?: number;
      window?: string;
      atrFloors?: number[];
      rangeFloors?: number[];
      slopeFloors?: number[];
    }
  }>) => {
    const body = req.body || {};
    
    const days = Number(body.days) || 180;
    const window = (body.window?.toUpperCase() || '24H') as SimWindow;
    
    // Default grid values
    const atrFloors = body.atrFloors || [0.20, 0.25, 0.30];
    const rangeFloors = body.rangeFloors || [0.04, 0.06, 0.08];
    const slopeFloors = body.slopeFloors || [0.0015, 0.002, 0.003];
    
    console.log(`[GridSearch] Starting ${days}D ${window} grid search`);
    console.log(`[GridSearch] Grid: ATR=${atrFloors}, Range=${rangeFloors}, Slope=${slopeFloors}`);
    
    const results: any[] = [];
    let iteration = 0;
    const totalIterations = atrFloors.length * rangeFloors.length * slopeFloors.length;
    
    // Run baseline first
    const baselineConfig: SentimentSimConfig = {
      days,
      window,
      mode: 'RULE',
      startCapital: 1.0,
      feeBps: 5,
      slippageBps: 3,
      chopGate: false,
      minBias: 0,
      regimeFilter: false,
      transitionScaling: false,
      chopV1: false,
    };
    
    const baseline = await runner.run(baselineConfig);
    results.push({
      name: 'BASELINE',
      chopConfig: null,
      trades: baseline.metrics.trades,
      winRate: baseline.metrics.winRate,
      returnPct: baseline.metrics.totalReturnPct,
      maxDD: baseline.metrics.maxDD,
      sharpe: baseline.metrics.sharpeLike,
      expectancy: baseline.metrics.expectancy,
    });
    
    // Run grid
    for (const atr of atrFloors) {
      for (const range of rangeFloors) {
        for (const slope of slopeFloors) {
          iteration++;
          console.log(`[GridSearch] Running ${iteration}/${totalIterations}: ATR=${atr}, Range=${range}, Slope=${slope}`);
          
          const config: SentimentSimConfig = {
            days,
            window,
            mode: 'RULE',
            startCapital: 1.0,
            feeBps: 5,
            slippageBps: 3,
            chopGate: false,
            minBias: 0,
            regimeFilter: false,
            transitionScaling: false,
            chopV1: true,
            chopConfig: {
              atrPercentileFloor: atr,
              rangeFloor: range,
              slopeFloor: slope,
            },
          };
          
          const report = await runner.run(config);
          
          results.push({
            name: `ATR${atr}_R${range}_S${slope}`,
            chopConfig: { atr, range, slope },
            trades: report.metrics.trades,
            winRate: report.metrics.winRate,
            returnPct: report.metrics.totalReturnPct,
            maxDD: report.metrics.maxDD,
            sharpe: report.metrics.sharpeLike,
            expectancy: report.metrics.expectancy,
            chopSkipped: report.chopStats?.skipped || 0,
          });
        }
      }
    }
    
    // Sort by Sharpe (primary), then Return
    const sorted = [...results].sort((a, b) => {
      if (a.name === 'BASELINE') return -1;
      if (b.name === 'BASELINE') return 1;
      const sharpeComp = b.sharpe - a.sharpe;
      if (Math.abs(sharpeComp) > 0.01) return sharpeComp;
      return b.returnPct - a.returnPct;
    });
    
    // Find best config
    const best = sorted.find(r => r.name !== 'BASELINE' && r.trades >= 15);
    
    gridResults = sorted;
    
    return {
      ok: true,
      grid: {
        days,
        window,
        atrFloors,
        rangeFloors,
        slopeFloors,
        totalConfigs: totalIterations + 1,
      },
      baseline: results[0],
      best: best || null,
      results: sorted.map(r => ({
        ...r,
        formatted: {
          winRate: `${(r.winRate * 100).toFixed(1)}%`,
          returnPct: `${(r.returnPct * 100).toFixed(2)}%`,
          maxDD: `${(r.maxDD * 100).toFixed(1)}%`,
          sharpe: r.sharpe.toFixed(3),
        },
      })),
    };
  });

  /**
   * GET /grid/results — Get last grid search results
   */
  app.get('/grid/results', async () => {
    return {
      ok: true,
      count: gridResults.length,
      results: gridResults,
    };
  });

  /**
   * GET /report — Get full last report
   */
  app.get('/report', async () => {
    if (!lastReport) {
      return { ok: false, error: 'No simulation run yet' };
    }

    return {
      ok: true,
      report: lastReport,
    };
  });

  /**
   * GET /equity — Get equity curve from last report
   */
  app.get('/equity', async () => {
    if (!lastReport) {
      return { ok: false, error: 'No simulation run yet' };
    }

    return {
      ok: true,
      config: lastReport.config,
      points: lastReport.equityCurve.length,
      data: lastReport.equityCurve,
    };
  });

  /**
   * GET /trades — Get trades from last report
   */
  app.get('/trades', async (req: FastifyRequest<{ Querystring: { limit?: string } }>) => {
    if (!lastReport) {
      return { ok: false, error: 'No simulation run yet' };
    }

    const limit = Math.min(Number(req.query.limit) || 100, 500);

    return {
      ok: true,
      config: lastReport.config,
      count: lastReport.trades.length,
      trades: lastReport.trades.slice(0, limit).map((t: any) => ({
        date: t.date,
        symbol: t.symbol,
        direction: t.direction,
        bias: t.bias,
        returnPct: t.returnPct,
        capitalAfter: t.capitalAfter,
      })),
    };
  });

  /**
   * GET /regime — Get regime breakdown from last report
   */
  app.get('/regime', async () => {
    if (!lastReport) {
      return { ok: false, error: 'No simulation run yet' };
    }

    return {
      ok: true,
      config: lastReport.config,
      regime: lastReport.regime,
    };
  });

  /**
   * GET /montecarlo — Get Monte Carlo results from last report
   */
  app.get('/montecarlo', async () => {
    if (!lastReport) {
      return { ok: false, error: 'No simulation run yet' };
    }

    return {
      ok: true,
      config: lastReport.config,
      monteCarlo: lastReport.monteCarlo,
    };
  });

  /**
   * GET /targets — Get simulation targets
   */
  app.get('/targets', async () => {
    return {
      ok: true,
      targets: {
        minWinRate: '50%',
        minExpectancy: '0%',
        minSharpe: '0.25',
        maxDD: '20%',
      },
    };
  });

  console.log('[Sentiment-ML] Simulation admin routes registered (BLOCK 7)');
}

// Export wrapped in fastify-plugin
export default fp(sentimentSimRoutes, {
  name: 'sentiment-sim-routes',
  fastify: '4.x',
});

export { sentimentSimRoutes };
