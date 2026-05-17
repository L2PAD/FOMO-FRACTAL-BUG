import type { FastifyInstance } from 'fastify';
import axios from 'axios';
import { mongoose } from '../db/mongoose.js';
import { scheduler, getIndexerStatus } from '../jobs/scheduler.js';
import { env } from '../config/env.js';

/**
 * Health Routes
 */

export async function healthRoutes(app: FastifyInstance): Promise<void> {
  // Basic health check
  app.get('/health', async () => {
    return {
      ok: true,
      service: 'node-backend',
      ts: Date.now(),
      uptime: process.uptime(),
    };
  });

  // Detailed health check with DB status
  app.get('/health/detailed', async () => {
    const mongoStatus = mongoose.connection.readyState === 1 ? 'connected' : 'disconnected';
    const indexerStatus = await getIndexerStatus();

    return {
      ok: mongoStatus === 'connected',
      ts: Date.now(),
      uptime: process.uptime(),
      services: {
        mongodb: mongoStatus,
        indexer: indexerStatus,
      },
      jobs: scheduler.getStatus(),
      memory: {
        rss: Math.round(process.memoryUsage().rss / 1024 / 1024),
        heapUsed: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
      },
    };
  });

  // FULL health check - all 3 services
  app.get('/health/full', async () => {
    const result: Record<string, any> = {};

    // 1. Python Gateway
    try {
      const gatewayRes = await axios.get(`http://localhost:8001/health`, { timeout: 3000 });
      result.gateway = { status: 'ok', ...gatewayRes.data };
    } catch (e: any) {
      result.gateway = { status: 'down', error: e.message };
    }

    // 2. Node Backend (self)
    result.backend = { 
      status: 'ok', 
      service: 'node-backend',
      uptime: process.uptime(),
      mongo: mongoose.connection.readyState === 1 ? 'connected' : 'disconnected'
    };

    // 3. Twitter Parser V2
    const parserUrl = env.PARSER_URL || 'http://localhost:5001';
    try {
      const parserRes = await axios.get(`${parserUrl}/health`, { timeout: 3000 });
      result.parser = { status: 'ok', ...parserRes.data };
    } catch (e: any) {
      result.parser = { status: 'down', error: e.message };
    }

    const allOk = Object.values(result).every((s: any) => 
      s.status === 'ok' || s.status === 'running' || s.ok === true
    );

    return {
      status: allOk ? 'healthy' : 'degraded',
      services: result,
      timestamp: Date.now()
    };
  });

  // Indexer status endpoint
  app.get('/indexer/status', async () => {
    const status = await getIndexerStatus();
    return {
      ok: true,
      data: status,
    };
  });

  /**
   * /health/onchain — Aggregated On-chain Layer Health
   * Shows status of all critical on-chain subsystems:
   * ingestion, pricing, pools, signals, actors, engine
   */
  app.get('/health/onchain', async () => {
    const now = Date.now();
    const mongoOk = mongoose.connection.readyState === 1;
    const detailed = scheduler.getDetailedStatus();

    // Group jobs into logical subsystems
    const subsystems: Record<string, Record<string, any>> = {
      ingestion: {},
      signals: {},
      actors: {},
      scoring: {},
      snapshots: {},
    };

    // Map job names to subsystems
    const JOB_MAP: Record<string, [string, string]> = {
      'onchain-v2-dex-sync': ['ingestion', 'dex'],
      'onchain-v2-erc20-sync': ['ingestion', 'erc20'],
      'build-transfers': ['ingestion', 'transfers'],
      'build-signals': ['signals', 'build'],
      'build-signal-contexts': ['signals', 'contexts'],
      'build-actor-profiles': ['actors', 'profiles'],
      'build-actor-signals': ['actors', 'signals'],
      'build-scores': ['scoring', 'scores'],
      'build-decisions': ['scoring', 'decisions'],
      'onchain-v2-snapshot-tick': ['snapshots', 'tick'],
      'onchain-v2-rolling-drift': ['snapshots', 'drift'],
      'erc20-indexer': ['ingestion', 'erc20-legacy'],
    };

    for (const [jobName, info] of Object.entries(detailed)) {
      const mapping = JOB_MAP[jobName];
      if (mapping) {
        const [group, key] = mapping;
        subsystems[group][key] = {
          status: info.health,
          lastRun: info.lastRun,
          lagMs: info.lagMs,
          running: info.running,
          tickCount: info.tickCount,
          successCount: info.successCount,
          errorCount: info.errorCount,
          lastError: info.lastError,
        };
      }
    }

    // Determine overall status
    const allStatuses: string[] = [];
    for (const group of Object.values(subsystems)) {
      for (const job of Object.values(group)) {
        allStatuses.push(job.status);
      }
    }

    let overall: 'OK' | 'DEGRADED' | 'CRITICAL' = 'OK';
    if (allStatuses.some(s => s === 'critical')) overall = 'CRITICAL';
    else if (allStatuses.some(s => s === 'degraded' || s === 'idle')) overall = 'DEGRADED';

    return {
      ok: overall === 'OK',
      status: overall,
      mongo: mongoOk ? 'connected' : 'disconnected',
      timestamp: now,
      subsystems,
    };
  });

  /**
   * /system/jobs/status — Detailed heartbeat for ALL registered jobs
   * Block 2.1: Full job heartbeat with lag, errors, tick counts
   */
  app.get('/system/jobs/status', async () => {
    const detailed = scheduler.getDetailedStatus();
    const mongoOk = mongoose.connection.readyState === 1;
    
    const jobs = Object.entries(detailed).map(([name, info]) => ({
      name,
      ...info,
    }));

    const healthy = jobs.filter(j => j.health === 'ok').length;
    const degraded = jobs.filter(j => j.health === 'degraded').length;
    const critical = jobs.filter(j => j.health === 'critical').length;
    const idle = jobs.filter(j => j.health === 'idle').length;

    return {
      ok: critical === 0,
      mongo: mongoOk ? 'connected' : 'disconnected',
      timestamp: Date.now(),
      summary: { total: jobs.length, healthy, degraded, critical, idle },
      jobs,
    };
  });
}
