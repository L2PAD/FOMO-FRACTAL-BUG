/**
 * Exchange Simulation Admin Routes
 * ================================
 * 
 * Endpoints:
 *   GET  /api/admin/exchange-sim/status  - Get simulation status
 *   POST /api/admin/exchange-sim/run     - Trigger simulation run
 *   POST /api/admin/exchange-sim/kill    - Kill running simulation
 *   GET  /api/admin/exchange-sim/reports - Get historical reports
 *   GET  /api/admin/exchange-sim/report/:id - Get specific report
 */

import { FastifyInstance, FastifyPluginOptions } from 'fastify';
import { runExchangeSimulation, getSimulationStatus } from '../index.js';
import { connectSimDb, disconnectSimDb, getSimDb } from '../core/sim_db.js';
import { createSimReporter } from '../reporters/sim_reporter.js';
import { loadSimConfigFromEnv } from '../core/sim_config.js';

let isRunning = false;
let currentRunPromise: Promise<any> | null = null;

export async function exchangeSimAdminRoutes(
  fastify: FastifyInstance,
  _opts: FastifyPluginOptions
): Promise<void> {
  
  /**
   * GET /api/admin/exchange-sim/status
   * Returns current simulation configuration and status
   */
  fastify.get('/api/admin/exchange-sim/status', async (_request, _reply) => {
    try {
      const status = await getSimulationStatus();
      
      return {
        ok: true,
        data: {
          ...status,
          isRunning,
        },
      };
    } catch (error: any) {
      return { ok: false, error: error.message };
    }
  });
  
  /**
   * POST /api/admin/exchange-sim/run
   * Triggers a new simulation run (non-blocking)
   * 
   * Query params:
   *   mode - baseline | retrain_only | lifecycle
   *   days - number of days to simulate
   */
  fastify.post('/api/admin/exchange-sim/run', async (request, _reply) => {
    if (isRunning) {
      return { ok: false, error: 'Simulation already running' };
    }
    
    // Apply query param overrides
    const query = request.query as { mode?: string; days?: string };
    if (query.mode) {
      process.env.EXCHANGE_SIM_MODE = query.mode;
    }
    if (query.days) {
      process.env.EXCHANGE_SIM_DAYS = query.days;
    }
    
    const config = loadSimConfigFromEnv();
    if (!config.enabled) {
      return { ok: false, error: 'Simulation disabled. Set EXCHANGE_SIM_ENABLED=true' };
    }
    
    // Start simulation in background
    isRunning = true;
    
    currentRunPromise = runExchangeSimulation()
      .then((result) => {
        console.log('[SimAdmin] Simulation completed:', result.success ? 'SUCCESS' : 'FAILED');
        return result;
      })
      .catch((error) => {
        console.error('[SimAdmin] Simulation error:', error);
        return { success: false, error: error.message };
      })
      .finally(() => {
        isRunning = false;
        currentRunPromise = null;
      });
    
    return {
      ok: true,
      data: {
        message: 'Simulation started',
        config: {
          symbols: config.symbols,
          days: config.days,
          mode: config.mode,
        },
      },
    };
  });
  
  /**
   * POST /api/admin/exchange-sim/kill
   * Kills the currently running simulation
   */
  fastify.post('/api/admin/exchange-sim/kill', async (_request, _reply) => {
    if (!isRunning) {
      return { ok: false, error: 'No simulation running' };
    }
    
    try {
      // Set kill switch in database
      const config = loadSimConfigFromEnv();
      const mongoUri = process.env.MONGO_URL || 'mongodb://localhost:27017';
      const baseDbName = process.env.DB_NAME || 'fomo';
      
      const simDb = await connectSimDb({
        mongoUri,
        baseDbName,
        dbSuffix: config.dbSuffix,
      });
      
      await simDb.collection('sim_flags').updateOne(
        { key: config.killSwitchKey },
        { $set: { value: true, setAt: new Date() } },
        { upsert: true }
      );
      
      await disconnectSimDb();
      
      return { ok: true, data: { message: 'Kill signal sent' } };
    } catch (error: any) {
      return { ok: false, error: error.message };
    }
  });
  
  /**
   * GET /api/admin/exchange-sim/reports
   * Returns list of historical simulation reports
   */
  fastify.get('/api/admin/exchange-sim/reports', async (request, _reply) => {
    const query = request.query as { limit?: string };
    const limit = parseInt(query.limit || '10', 10);
    
    try {
      const config = loadSimConfigFromEnv();
      const mongoUri = process.env.MONGO_URL || 'mongodb://localhost:27017';
      const baseDbName = process.env.DB_NAME || 'fomo';
      
      const simDb = await connectSimDb({
        mongoUri,
        baseDbName,
        dbSuffix: config.dbSuffix,
      });
      
      const reporter = createSimReporter(simDb);
      const reports = await reporter.getReports(limit);
      
      await disconnectSimDb();
      
      // Return summary only (not full reports)
      const summaries = reports.map(r => ({
        id: (r as any)._id?.toString(),
        status: r.status,
        startedAt: r.startedAt,
        completedAt: r.completedAt,
        days: r.metrics.totalDays,
        symbols: r.metrics.totalSymbols,
        accuracy1D: r.metrics.accuracy['1D'].rate,
        accuracy7D: r.metrics.accuracy['7D'].rate,
        accuracy30D: r.metrics.accuracy['30D'].rate,
        issues: r.issues.length,
      }));
      
      return { ok: true, data: summaries };
    } catch (error: any) {
      return { ok: false, error: error.message };
    }
  });
  
  /**
   * GET /api/admin/exchange-sim/report/:id
   * Returns full report by ID
   */
  fastify.get('/api/admin/exchange-sim/report/:id', async (request, _reply) => {
    const params = request.params as { id: string };
    
    try {
      const config = loadSimConfigFromEnv();
      const mongoUri = process.env.MONGO_URL || 'mongodb://localhost:27017';
      const baseDbName = process.env.DB_NAME || 'fomo';
      
      const simDb = await connectSimDb({
        mongoUri,
        baseDbName,
        dbSuffix: config.dbSuffix,
      });
      
      const { ObjectId } = await import('mongodb');
      const report = await simDb.collection('sim_reports').findOne({
        _id: new ObjectId(params.id),
      });
      
      await disconnectSimDb();
      
      if (!report) {
        return { ok: false, error: 'Report not found' };
      }
      
      // Remove MongoDB _id
      const { _id, ...cleanReport } = report;
      
      return { ok: true, data: cleanReport };
    } catch (error: any) {
      return { ok: false, error: error.message };
    }
  });
  
  /**
   * POST /api/admin/exchange-sim/clear
   * Clears all simulation data (use with caution!)
   */
  fastify.post('/api/admin/exchange-sim/clear', async (_request, _reply) => {
    if (isRunning) {
      return { ok: false, error: 'Cannot clear while simulation is running' };
    }
    
    try {
      const config = loadSimConfigFromEnv();
      const mongoUri = process.env.MONGO_URL || 'mongodb://localhost:27017';
      const baseDbName = process.env.DB_NAME || 'fomo';
      
      const simDb = await connectSimDb({
        mongoUri,
        baseDbName,
        dbSuffix: config.dbSuffix,
      });
      
      // Drop simulation collections
      const collections = ['sim_price_cache', 'sim_audit_log', 'sim_reports', 'sim_flags'];
      for (const col of collections) {
        try {
          await simDb.collection(col).drop();
        } catch {
          // Collection may not exist
        }
      }
      
      await disconnectSimDb();
      
      return { ok: true, data: { message: 'Simulation data cleared' } };
    } catch (error: any) {
      return { ok: false, error: error.message };
    }
  });
  
  console.log('[ExchangeSim] Admin routes registered (/api/admin/exchange-sim/*)');
}

export default exchangeSimAdminRoutes;
