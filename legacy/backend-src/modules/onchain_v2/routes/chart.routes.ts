/**
 * OnChain V2 — Chart Routes
 * ==========================
 * 
 * User-facing chart endpoint for 30d institutional window.
 * Returns timeseries data for visualization.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { 
  OnchainObservationModel,
  OnchainSnapshotModel,
} from '../core/persistence/models.js';
import { 
  OnchainMetrics, 
  OnchainState,
  deriveOnchainState,
  ONCHAIN_THRESHOLDS,
} from '../core/contracts.js';
import { governanceService } from '../governance/index.js';
import { getOnchainProvider, getActiveProviderConfig } from '../providers/index.js';
import { snapshotService } from '../core/snapshot/index.js';
import { metricsEngine } from '../core/metrics/index.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface ChartDataPoint {
  t: number;
  score: number;
  confidence: number;
  exchangePressure: number;
  flowScore: number;
  whaleActivity: number;
  networkHeat: number;
  state: OnchainState;
}

interface ChartLatest {
  t: number;
  score: number;
  confidence: number;
  state: OnchainState;
  drivers: string[];
  flags: string[];
}

interface ChartResponse {
  ok: boolean;
  symbol: string;
  window: string;
  policy: {
    id: string;
    version: string;
    name: string;
  } | null;
  series: ChartDataPoint[];
  latest: ChartLatest | null;
  provider: string;
  generatedAt: number;
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function calculateScore(metrics: OnchainMetrics, weights: Record<string, number>): number {
  const score = 
    (metrics.exchangePressure * (weights.exchangePressureWeight || 0.35)) +
    (metrics.flowScore * (weights.flowScoreWeight || 0.25)) +
    (metrics.whaleActivity * (weights.whaleActivityWeight || 0.20)) +
    (metrics.networkHeat * (weights.networkHeatWeight || 0.10)) +
    (metrics.velocity * (weights.velocityWeight || 0.05)) +
    (metrics.distributionSkew * (weights.distributionSkewWeight || 0.05));
  
  // Normalize to 0..1 range (metrics are in -1..1 or 0..1)
  return Math.max(0, Math.min(1, (score + 1) / 2));
}

function generateFlags(
  metrics: OnchainMetrics | null, 
  providerMode: string,
  dataAge: number
): string[] {
  const flags: string[] = [];
  
  if (!metrics) {
    flags.push('NO_DATA');
    return flags;
  }
  
  if (providerMode === 'mock') {
    flags.push('MOCK_DATA');
  }
  
  if (metrics.confidence < ONCHAIN_THRESHOLDS.MIN_USABLE_CONFIDENCE) {
    flags.push('LOW_CONFIDENCE');
  }
  
  // Data older than 1 hour
  if (dataAge > 3600_000) {
    flags.push('STALE');
  }
  
  if (flags.length === 0) {
    flags.push('OK');
  }
  
  return flags;
}

function generateDrivers(metrics: OnchainMetrics): string[] {
  const drivers: string[] = [];
  
  // Flow direction
  if (metrics.flowScore > 0.2) {
    drivers.push('Net outflows detected');
  } else if (metrics.flowScore < -0.2) {
    drivers.push('Net inflows detected');
  }
  
  // Exchange pressure
  if (metrics.exchangePressure > 0.3) {
    drivers.push('High exchange deposits');
  } else if (metrics.exchangePressure < -0.3) {
    drivers.push('Exchange withdrawals elevated');
  } else {
    drivers.push('Low exchange pressure');
  }
  
  // Whale activity
  if (metrics.whaleActivity > 0.5) {
    drivers.push('Whale activity elevated');
  }
  
  // Network heat
  if (metrics.networkHeat > 0.6) {
    drivers.push('High network activity');
  }
  
  return drivers.slice(0, 3);
}

// ═══════════════════════════════════════════════════════════════
// CHART HANDLER
// ═══════════════════════════════════════════════════════════════

async function chartHandler(
  request: FastifyRequest<{
    Params: { symbol: string };
    Querystring: { window?: string };
  }>,
  reply: FastifyReply
): Promise<ChartResponse> {
  const { symbol } = request.params;
  const window = request.query.window || '30d';
  const normalizedSymbol = symbol.toUpperCase().replace('-', '');
  
  // Get active policy
  const policy = await governanceService.getActivePolicy();
  const weights = policy?.weights || {
    exchangePressureWeight: 0.35,
    flowScoreWeight: 0.25,
    whaleActivityWeight: 0.20,
    networkHeatWeight: 0.10,
    velocityWeight: 0.05,
    distributionSkewWeight: 0.05,
  };
  
  // Calculate time range
  const windowDays = parseInt(window) || 30;
  const now = Date.now();
  const fromTime = now - (windowDays * 24 * 60 * 60 * 1000);
  
  // Get provider config
  const config = getActiveProviderConfig();
  
  // Try to get historical observations
  const observations = await OnchainObservationModel.find({
    symbol: normalizedSymbol,
    t0: { $gte: fromTime },
  }).sort({ t0: 1 }).limit(720); // Max ~1 point per hour for 30 days
  
  let series: ChartDataPoint[] = [];
  let latest: ChartLatest | null = null;
  
  if (observations.length > 0) {
    // Build series from historical data
    series = observations.map(obs => {
      const metrics = obs.metrics as OnchainMetrics;
      const score = calculateScore(metrics, weights);
      
      return {
        t: obs.t0,
        score,
        confidence: metrics.confidence,
        exchangePressure: metrics.exchangePressure,
        flowScore: metrics.flowScore,
        whaleActivity: metrics.whaleActivity,
        networkHeat: metrics.networkHeat,
        state: obs.state as OnchainState,
      };
    });
    
    // Get latest
    const lastObs = observations[observations.length - 1];
    const lastMetrics = lastObs.metrics as OnchainMetrics;
    const lastScore = calculateScore(lastMetrics, weights);
    const dataAge = now - lastObs.t0;
    
    latest = {
      t: lastObs.t0,
      score: lastScore,
      confidence: lastMetrics.confidence,
      state: lastObs.state as OnchainState,
      drivers: generateDrivers(lastMetrics),
      flags: generateFlags(lastMetrics, config.mode, dataAge),
    };
  } else {
    // No historical data - try to generate current snapshot
    try {
      const snapshotRes = await snapshotService.getSnapshot(normalizedSymbol, now, '1h');
      
      if (snapshotRes.ok && snapshotRes.snapshot) {
        const metrics = metricsEngine.calculate(snapshotRes.snapshot);
        const score = calculateScore(metrics, weights);
        const state = deriveOnchainState(metrics);
        
        // Single point for now
        series = [{
          t: now,
          score,
          confidence: metrics.confidence,
          exchangePressure: metrics.exchangePressure,
          flowScore: metrics.flowScore,
          whaleActivity: metrics.whaleActivity,
          networkHeat: metrics.networkHeat,
          state,
        }];
        
        latest = {
          t: now,
          score,
          confidence: metrics.confidence,
          state,
          drivers: generateDrivers(metrics),
          flags: generateFlags(metrics, config.mode, 0),
        };
      }
    } catch (error) {
      console.error('[OnChain V2] Chart: Failed to get snapshot:', error);
    }
  }
  
  // If still no data
  if (!latest) {
    latest = {
      t: now,
      score: 0,
      confidence: 0,
      state: 'NO_DATA',
      drivers: [],
      flags: ['NO_DATA'],
    };
  }
  
  return {
    ok: true,
    symbol: normalizedSymbol,
    window,
    policy: policy ? {
      id: policy.id,
      version: policy.version,
      name: policy.name,
    } : null,
    series,
    latest,
    provider: config.mode,
    generatedAt: now,
  };
}

// ═══════════════════════════════════════════════════════════════
// LATEST HANDLER (simplified)
// ═══════════════════════════════════════════════════════════════

async function latestContextHandler(
  request: FastifyRequest<{
    Params: { symbol: string };
  }>,
  reply: FastifyReply
) {
  const { symbol } = request.params;
  const normalizedSymbol = symbol.toUpperCase().replace('-', '');
  
  const policy = await governanceService.getActivePolicy();
  const weights = policy?.weights || {};
  const config = getActiveProviderConfig();
  const now = Date.now();
  
  try {
    const snapshotRes = await snapshotService.getSnapshot(normalizedSymbol, now, '1h');
    
    if (!snapshotRes.ok || !snapshotRes.snapshot) {
      return {
        ok: true,
        symbol: normalizedSymbol,
        data: null,
        flags: ['NO_DATA'],
        provider: config.mode,
      };
    }
    
    const metrics = metricsEngine.calculate(snapshotRes.snapshot);
    const score = calculateScore(metrics, weights);
    const state = deriveOnchainState(metrics);
    
    return {
      ok: true,
      symbol: normalizedSymbol,
      data: {
        score,
        confidence: metrics.confidence,
        state,
        exchangePressure: metrics.exchangePressure,
        flowScore: metrics.flowScore,
        whaleActivity: metrics.whaleActivity,
        networkHeat: metrics.networkHeat,
        drivers: generateDrivers(metrics),
      },
      flags: generateFlags(metrics, config.mode, 0),
      provider: config.mode,
      policyVersion: policy?.version || null,
      timestamp: now,
    };
  } catch (error) {
    console.error('[OnChain V2] Latest context error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function onchainV2ChartRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get('/chart/:symbol', chartHandler);
  fastify.get('/context/:symbol', latestContextHandler);
  
  console.log('[OnChain V2] Chart routes registered');
}

console.log('[OnChain V2] Chart Routes module loaded');
