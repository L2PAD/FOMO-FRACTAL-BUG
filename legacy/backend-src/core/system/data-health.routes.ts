/**
 * DATA HEALTH CHECK ENDPOINT
 * ==========================
 * 
 * Critical monitoring: Are modules actually feeding Meta Brain?
 * 
 * This is NOT "are services running?"
 * This is "do we have decision-ready data?"
 */

import { FastifyInstance } from 'fastify';
import mongoose from 'mongoose';

interface ModuleHealth {
  hasData: boolean;
  count: number;
  latestTimestamp: Date | null;
  ageHours: number | null;
  status: 'HEALTHY' | 'STALE' | 'MISSING';
}

interface DataHealthReport {
  ok: boolean;
  timestamp: Date;
  modules: {
    exchange: ModuleHealth;
    fractal: ModuleHealth;
    sentiment: ModuleHealth;
    onchain: ModuleHealth;
  };
  metaBrainStatus: 'OPERATIONAL' | 'DEGRADED' | 'CRITICAL';
  warnings: string[];
}

async function checkModuleHealth(
  collectionName: string,
  maxAgeHours: number = 24
): Promise<ModuleHealth> {
  const db = mongoose.connection.db;
  if (!db) {
    return {
      hasData: false,
      count: 0,
      latestTimestamp: null,
      ageHours: null,
      status: 'MISSING',
    };
  }

  const count = await db.collection(collectionName).countDocuments();

  if (count === 0) {
    return {
      hasData: false,
      count: 0,
      latestTimestamp: null,
      ageHours: null,
      status: 'MISSING',
    };
  }

  const latest = await db
    .collection(collectionName)
    .find({})
    .sort({ timestamp: -1, createdAt: -1 })
    .limit(1)
    .toArray();

  const latestTimestamp = latest[0]?.timestamp || latest[0]?.createdAt || null;
  const ageHours = latestTimestamp
    ? (Date.now() - new Date(latestTimestamp).getTime()) / 3600000
    : null;

  let status: 'HEALTHY' | 'STALE' | 'MISSING' = 'HEALTHY';
  if (ageHours === null) {
    status = 'MISSING';
  } else if (ageHours > maxAgeHours) {
    status = 'STALE';
  }

  return {
    hasData: count > 0,
    count,
    latestTimestamp,
    ageHours,
    status,
  };
}

export async function dataHealthRoutes(fastify: FastifyInstance) {
  /**
   * GET /api/system/data-health
   * 
   * Returns health status of all data sources feeding Meta Brain
   */
  fastify.get('/data-health', async (_request, reply) => {
    const warnings: string[] = [];

    // Check each module
    const exchange = await checkModuleHealth('exchange_prediction_snapshots', 12);
    const fractal = await checkModuleHealth('fractal_prediction_snapshots', 48);
    const sentiment = await checkModuleHealth('sentiment_aggregates', 24);
    const onchain = await checkModuleHealth('onchain_lite_snapshots', 24);

    // Determine overall Meta Brain status
    let metaBrainStatus: 'OPERATIONAL' | 'DEGRADED' | 'CRITICAL' = 'OPERATIONAL';

    const healthyCount = [exchange, fractal, sentiment, onchain].filter(
      m => m.status === 'HEALTHY'
    ).length;

    if (healthyCount < 2) {
      metaBrainStatus = 'CRITICAL';
      warnings.push('Less than 2 modules have healthy data - Meta Brain is severely degraded');
    } else if (healthyCount < 3) {
      metaBrainStatus = 'DEGRADED';
      warnings.push('Only 2 modules have healthy data - Meta Brain is operating with reduced accuracy');
    }

    // Module-specific warnings
    if (exchange.status === 'MISSING') {
      warnings.push('⚠️  Exchange snapshots MISSING - Exchange module not feeding Meta Brain');
    } else if (exchange.status === 'STALE') {
      warnings.push(`⚠️  Exchange snapshots STALE (${exchange.ageHours?.toFixed(1)}h old)`);
    }

    if (fractal.status === 'MISSING') {
      warnings.push('⚠️  Fractal snapshots MISSING - Fractal module not feeding Meta Brain');
    } else if (fractal.status === 'STALE') {
      warnings.push(`⚠️  Fractal snapshots STALE (${fractal.ageHours?.toFixed(1)}h old)`);
    }

    if (sentiment.status === 'MISSING') {
      warnings.push('⚠️  Sentiment aggregates MISSING - Sentiment module not feeding Meta Brain');
    } else if (sentiment.status === 'STALE') {
      warnings.push(`⚠️  Sentiment aggregates STALE (${sentiment.ageHours?.toFixed(1)}h old)`);
    }

    if (onchain.status === 'MISSING') {
      warnings.push('⚠️  OnChain snapshots MISSING - OnChain module not feeding Meta Brain');
    } else if (onchain.status === 'STALE') {
      warnings.push(`⚠️  OnChain snapshots STALE (${onchain.ageHours?.toFixed(1)}h old)`);
    }

    const report: DataHealthReport = {
      ok: metaBrainStatus !== 'CRITICAL',
      timestamp: new Date(),
      modules: {
        exchange,
        fractal,
        sentiment,
        onchain,
      },
      metaBrainStatus,
      warnings,
    };

    return reply.send(report);
  });

  /**
   * GET /api/system/data-health/summary
   * 
   * Minimal health check (for monitoring dashboards)
   */
  fastify.get('/data-health/summary', async (_request, reply) => {
    const db = mongoose.connection.db;
    if (!db) {
      return reply.send({
        ok: false,
        status: 'CRITICAL',
        message: 'MongoDB not connected',
      });
    }

    const counts = {
      exchange: await db.collection('exchange_prediction_snapshots').countDocuments(),
      fractal: await db.collection('fractal_prediction_snapshots').countDocuments(),
      sentiment: await db.collection('sentiment_aggregates').countDocuments(),
      onchain: await db.collection('onchain_lite_snapshots').countDocuments(),
    };

    const healthyCount = Object.values(counts).filter(c => c > 0).length;

    let status: 'OPERATIONAL' | 'DEGRADED' | 'CRITICAL' = 'OPERATIONAL';
    if (healthyCount < 2) status = 'CRITICAL';
    else if (healthyCount < 3) status = 'DEGRADED';

    return reply.send({
      ok: status !== 'CRITICAL',
      status,
      healthyModules: healthyCount,
      totalModules: 4,
      counts,
    });
  });

  console.log('[DataHealth] Routes registered at /api/system/data-health');
}

export default dataHealthRoutes;
