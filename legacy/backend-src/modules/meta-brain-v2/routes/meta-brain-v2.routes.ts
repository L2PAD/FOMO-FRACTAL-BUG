/**
 * META BRAIN V2 — ROUTES
 * =======================
 * 
 * Phase 1 endpoints:
 *   GET /api/meta-brain-v2/signals         — raw signals from all providers
 *   GET /api/meta-brain-v2/signals/aligned — time-aligned signals
 *   GET /api/meta-brain-v2/status          — provider health status
 * 
 * Phase 2 endpoints:
 *   POST /api/meta-brain-v2/run            — full pipeline: aggregate + stability → verdict
 *   GET  /api/meta-brain-v2/state          — current persisted state
 * 
 * Does NOT touch existing Meta Brain v1 routes.
 */

import { FastifyInstance } from 'fastify';
import { collectSignals } from '../services/signal-collector.service.js';
import { alignSignals } from '../services/signal_alignment.service.js';
import { DEFAULT_TIME_POLICY } from '../config/time_alignment.policy.js';
import { getProviders, getProviderKeys } from '../registry/providers.registry.js';
import { Horizon } from '../contracts/signal.contract.js';
import { aggregate } from '../aggregator/signal_aggregator.js';
import { applyStability } from '../stability/stability_layer.js';
import { getState } from '../stability/meta_brain_state.service.js';
import { saveRun } from '../runs/meta_brain_runs.repo.js';
import { getPerformanceSummary } from '../performance/performance.service.js';
import { evaluatePerformance } from '../performance/performance_evaluator.job.js';
import { startExchangeKeepalive, manualRefresh } from '../services/exchange_keepalive.scheduler.js';
import { evaluateDrift } from '../drift/drift_evaluator.service.js';
import { getAllDriftStates, getDriftHistory } from '../drift/drift.repo.js';
import { getCalibrationSummary } from '../calibration/calibration.service.js';
import { runCalibrationJob } from '../calibration/calibration.job.js';
import { resolvePolicy, getAllPolicies } from '../policy/policy_resolver.js';
import { getMarketRegime } from '../weights/market_regime.provider.js';
import { runMetaRunEvaluator } from '../runs/meta_run_evaluator.job.js';
import { getCorrelationMatrix, computeCorrelationMatrix } from '../correlation/correlation.service.js';
import { buildMetaForecast, generateForecastSeries } from '../services/meta_forecast.service.js';
import { horizonKeyFromDays } from '../config/expectedMoves.config.js';
import { startRunEvaluatorScheduler } from '../runs/run_evaluator.scheduler.js';
import { getDatasetStats, getDatasetRuns } from '../runs/dataset.repo.js';
import { saveForecastSnapshot, getRecentSnapshots, buildForecastCurve } from '../services/forecast_snapshots.repo.js';
import { buildForecastTable } from '../services/forecast_table.service.js';
import { getAllModules, updateModule, initModuleFlags, getActiveModules } from '../services/module_controller.service.js';

function horizonFromDays(days: number): Horizon {
  if (days <= 1) return '1D';
  if (days <= 7) return '7D';
  return '30D';
}

/** Detect direction conflicts between modules */
function findConflicts(signals: Array<{ module: string; normalizedScore: number }>): Array<{ a: string; b: string; type: string }> {
  const conflicts: Array<{ a: string; b: string; type: string }> = [];
  for (let i = 0; i < signals.length; i++) {
    for (let j = i + 1; j < signals.length; j++) {
      const sA = signals[i], sB = signals[j];
      // Opposite signs with meaningful magnitude
      if (sA.normalizedScore * sB.normalizedScore < -0.01) {
        conflicts.push({ a: sA.module, b: sB.module, type: 'direction_conflict' });
      }
    }
  }
  return conflicts;
}

/** In-memory cache of latest influence data per asset (updated on each /run) */
const latestInfluence: Record<string, {
  contributors: Array<{ module: string; weight: number; signal: number; impact: number; pctImpact: number }>;
  verdict: string;
  score: number;
  confidence: number;
  activeModules: string[];
  droppedModules: Array<{ module: string; reason: string }>;
  regime: string;
  updatedTs: number;
}> = {};

async function metaBrainV2Routes(fastify: FastifyInstance) {

  /**
   * GET /signals — Raw signals from all providers (before alignment)
   */
  fastify.get('/signals', async (request, reply) => {
    const query = request.query as { asset?: string; horizon?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizon || '7', 10);

    const result = await collectSignals(asset, horizonDays);

    return reply.send({
      ok: true,
      asset,
      horizonDays,
      durationMs: result.durationMs,
      signals: result.signals,
      dropped: result.dropped,
    });
  });

  /**
   * GET /signals/aligned — Time-aligned signals with anchor
   */
  fastify.get('/signals/aligned', async (request, reply) => {
    const query = request.query as { asset?: string; horizon?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizon || '7', 10);
    const horizon = horizonFromDays(horizonDays);

    const collected = await collectSignals(asset, horizonDays);
    const aligned = alignSignals(
      collected.signals,
      collected.dropped,
      horizon,
      DEFAULT_TIME_POLICY
    );

    return reply.send({
      ok: true,
      asset,
      horizonDays,
      durationMs: collected.durationMs,
      ...aligned,
    });
  });

  /**
   * GET /status — Provider health overview
   */
  fastify.get('/status', async (_request, reply) => {
    const allProviders = getProviders();
    const providers = allProviders.map(p => ({
      key: p.key,
      version: p.version,
    }));

    return reply.send({
      ok: true,
      version: 'meta-brain-v2-phase3',
      providersCount: providers.length,
      providers,
      policy: {
        anchorMode: DEFAULT_TIME_POLICY.anchorMode,
        ttl: DEFAULT_TIME_POLICY.ttlMsByModule,
        maxSkew: DEFAULT_TIME_POLICY.maxSkewMsByModule,
        fallback: DEFAULT_TIME_POLICY.fallback,
      },
    });
  });

  /**
   * GET /providers — Active provider list (for debugging & UI)
   */
  fastify.get('/providers', async (_request, reply) => {
    const allProviders = getProviders();
    return reply.send({
      ok: true,
      count: allProviders.length,
      providers: allProviders.map(p => ({
        key: p.key,
        version: p.version,
      })),
      keys: getProviderKeys(),
    });
  });

  // ═══════════════════════════════════════════════════════════
  // PHASE 2: Aggregation + Stability Pipeline
  // ═══════════════════════════════════════════════════════════

  /**
   * POST /run — Full Meta Brain pipeline
   * Body: { asset?: string, horizonDays?: number }
   */
  fastify.post('/run', async (request, reply) => {
    const body = (request.body || {}) as { asset?: string; horizonDays?: number };
    const asset = (body.asset || 'BTC').toUpperCase();
    const horizonDays = body.horizonDays ?? 7;

    const t0 = Date.now();

    // Stage 1: Aggregate (collect → align → normalize → gate → weight → rawScore)
    const agg = await aggregate(asset, horizonDays);

    // Stage 2: Stability (hysteresis + cooldown)
    const stability = await applyStability(agg);

    // Stage 3: Save run for performance tracking (fire-and-forget)
    const runId = `run_${asset}_${horizonDays}D_${new Date(t0).toISOString().slice(0,13)}`;
    saveRun({
      runId,
      asset,
      horizonDays,
      anchorTs: agg.alignment.anchorTs,
      createdAt: t0,
      signals: agg.signals.map(s => {
        const aligned = agg.alignment.aligned.find(a => a.module === s.module);
        return {
          moduleId: s.module,
          direction: aligned?.direction ?? 'NEUTRAL',
          score: aligned?.score ?? 0,
          confidence: aligned?.confidence ?? 0,
          weight: s.weight,
          normalizedScore: s.normalizedScore,
          weightedScore: s.weightedScore,
          health: aligned?.health ?? 'OK',
          asOfTs: aligned?.asOfTs ?? t0,
        };
      }),
      droppedModules: agg.gatedModules.concat(
        agg.alignment.dropped.map(d => ({ module: d.module, reason: d.reason }))
      ),
      metaRawScore: agg.rawScore,
      metaFinalVerdict: stability.finalVerdict,
      metaConfidence: agg.rawConfidence,
      regime: agg.regime,
      weights: agg.weights,
    }).catch(err => console.error('[MetaBrain-V2] Failed to save run:', err?.message));

    // CRITICAL: Save prediction outcome for accuracy tracking (P0 Truth Layer)
    const { saveOutcome } = await import('../outcomes/meta_brain_outcomes.repo.js');
    const horizonKey = horizonDays === 1 ? '24H' : horizonDays === 7 ? '7D' : '30D';
    
    // Get current price (entry price for outcome calculation)
    const entryPrice = agg.alignment.aligned.find(a => a.module === 'exchange')?.price 
      ?? agg.alignment.aligned.find(a => a.price)?.price 
      ?? 0;
    
    saveOutcome({
      asset,
      horizon: horizonKey as '24H' | '7D' | '30D',
      predictedAt: new Date(t0),
      
      direction: stability.finalVerdict,
      confidence: agg.rawConfidence,
      
      regime: agg.regime,
      modulesUsed: agg.signals.map(s => s.module),
      moduleScores: {
        exchange: agg.signals.find(s => s.module === 'exchange')?.normalizedScore,
        fractal: agg.signals.find(s => s.module === 'fractal')?.normalizedScore,
        sentiment: agg.signals.find(s => s.module === 'sentiment')?.normalizedScore,
        onchain: agg.signals.find(s => s.module === 'onchain')?.normalizedScore,
      },
      
      entryPrice,
      targetPrice: undefined, // TODO: Calculate target from expected moves
      bandLow: undefined,
      bandHigh: undefined,
      
      resolved: false,
      
      meta: {
        version: 'meta-brain-v2-phase5',
        policy: agg.policy.regime,
      },
    }).catch(err => console.error('[MetaBrain-V2] Failed to save outcome:', err?.message));

    // Cache influence data for GET /influence endpoint
    const contributors = agg.signals
      .map(s => {
        const totalAbsImpact = agg.signals.reduce((sum, x) => sum + Math.abs(x.weightedScore), 0);
        return {
          module: s.module,
          weight: s.weight,
          signal: s.normalizedScore,
          impact: s.weightedScore,
          pctImpact: totalAbsImpact > 0 ? Math.abs(s.weightedScore) / totalAbsImpact : 0,
        };
      })
      .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));

    latestInfluence[asset] = {
      contributors,
      verdict: stability.finalVerdict,
      score: stability.finalScore,
      confidence: agg.rawConfidence,
      activeModules: agg.signals.map(s => s.module),
      droppedModules: [
        ...agg.alignment.dropped.map(d => ({ module: d.module, reason: d.reason })),
        ...agg.gatedModules.map(g => ({ module: g.module, reason: g.reason })),
      ],
      regime: agg.regime,
      updatedTs: Date.now(),
    };

    return reply.send({
      ok: true,
      version: 'meta-brain-v2-phase5',
      asset,
      horizonDays,

      // Final verdict (after stability)
      verdict: {
        direction: stability.finalVerdict,
        score: stability.finalScore,
        rawDirection: stability.rawVerdict,
        rawScore: stability.rawScore,
        confidence: agg.rawConfidence,
        metaConfidence: agg.metaConfidence.metaConfidence,
      },

      // Meta Confidence breakdown
      metaConfidence: agg.metaConfidence,

      // Stability info
      stability: {
        applied: stability.stabilityApplied,
        verdictChanged: stability.verdictChanged,
        reason: stability.reason,
        cooldownActive: stability.cooldownActive,
        cooldownUntilTs: stability.cooldownUntilTs,
        cooldownMs: stability.cooldownMs,
        previousVerdict: stability.previousVerdict,
        thresholdsUsed: stability.thresholdsUsed,
      },

      // Active policy
      policy: {
        regime: agg.policy.regime,
        thresholds: agg.policy.thresholds,
        cooldown: agg.policy.cooldown,
        weights: agg.policy.weights,
        gates: agg.policy.gates,
        confidenceCoefficients: agg.policy.confidence,
      },

      // Regime
      regime: agg.regime,
      regimeDetail: {
        sourceRegime: agg.regimeDetail.sourceRegime,
        source: agg.regimeDetail.source,
        riskLevel: agg.regimeDetail.riskLevel,
        confidenceMultiplier: agg.regimeDetail.confidenceMultiplier,
      },

      // Coverage
      metaStatus: agg.metaStatus,
      coverage: agg.coverage,

      // Module Registry: active vs dropped
      activeModules: agg.signals.map(s => s.module),
      droppedModules: [
        ...agg.alignment.dropped.map(d => ({ module: d.module, reason: d.reason })),
        ...agg.gatedModules.map(g => ({ module: g.module, reason: g.reason })),
      ],

      // Per-signal breakdown (with weight decomposition)
      signals: agg.signals,

      // Effective weights (after regime + reliability + drift + renorm)
      weights: agg.weights,

      // Explainability: contributors sorted by impact
      explain: {
        contributors: agg.signals
          .map(s => ({
            module: s.module,
            weight: s.weight,
            signal: s.normalizedScore,
            impact: s.weightedScore,
          }))
          .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact)),
        conflicts: findConflicts(agg.signals),
      },

      // Calibration per signal
      calibration: agg.calibrationInfo,

      // Drift info
      drift: agg.driftInfo,

      // Gated modules
      gatedModules: agg.gatedModules,

      // Alignment detail
      alignment: {
        anchorTs: agg.alignment.anchorTs,
        anchorDate: new Date(agg.alignment.anchorTs).toISOString(),
        aligned: agg.alignment.aligned.map(s => ({
          module: s.module,
          direction: s.direction,
          score: s.score,
          confidence: s.confidence,
          asOfTs: s.asOfTs,
          asOfDate: new Date(s.asOfTs).toISOString(),
          health: s.health,
        })),
        dropped: agg.alignment.dropped,
      },

      // Timing
      durationMs: Date.now() - t0,

      // Forecast targets (from Meta Forecast Engine)
      forecast: (() => {
        const forecastSignals = agg.signals.map(s => {
          const aligned = agg.alignment.aligned.find(a => a.module === s.module);
          return {
            module: s.module,
            direction: (aligned?.direction ?? 'NEUTRAL') as 'LONG' | 'SHORT' | 'NEUTRAL',
            confidence: aligned?.confidence ?? 0,
            weight: s.weight,
          };
        });
        const coverageRatio = agg.coverage.total > 0 ? agg.coverage.active / agg.coverage.total : 0;
        // Need currentPrice — approximate from alignment or use 0
        const lastSignalPrice = agg.alignment.aligned.find(s => s.targetPrice)?.targetPrice ?? 0;
        return buildMetaForecast({
          asset,
          currentPrice: lastSignalPrice,
          coverageRatio,
          signals: forecastSignals,
        });
      })(),
    });
  });

  /**
   * GET /state — Current persisted state for asset + horizon
   */
  fastify.get('/state', async (request, reply) => {
    const query = request.query as { asset?: string; horizon?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizon || '7', 10);

    const state = await getState(asset, horizonDays);

    if (!state) {
      return reply.send({
        ok: true,
        asset,
        horizonDays,
        state: null,
        message: 'No prior state — run POST /run first',
      });
    }

    return reply.send({
      ok: true,
      asset,
      horizonDays,
      state: {
        ...state,
        lastUpdatedDate: new Date(state.lastUpdatedTs).toISOString(),
        cooldownUntilDate: state.cooldownUntilTs
          ? new Date(state.cooldownUntilTs).toISOString()
          : null,
      },
    });
  });

  // ═══════════════════════════════════════════════════════════
  // PHASE 7.1: Signal Influence Tracking
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /influence — Latest decision contributors (impact per module)
   * Used by Core Panel's "Decision Drivers" block.
   * If no /run has been done yet, returns a computed snapshot from current signals.
   */
  fastify.get('/influence', async (request, reply) => {
    const query = request.query as { asset?: string };
    const asset = (query.asset || 'BTC').toUpperCase();

    const cached = latestInfluence[asset];
    if (cached) {
      return reply.send({
        ok: true,
        asset,
        ...cached,
        ageMs: Date.now() - cached.updatedTs,
      });
    }

    // No cached run — compute a lightweight influence from current signals
    try {
      const agg = await aggregate(asset, 7);
      const totalAbsImpact = agg.signals.reduce((sum, x) => sum + Math.abs(x.weightedScore), 0);
      const contributors = agg.signals
        .map(s => ({
          module: s.module,
          weight: s.weight,
          signal: s.normalizedScore,
          impact: s.weightedScore,
          pctImpact: totalAbsImpact > 0 ? Math.abs(s.weightedScore) / totalAbsImpact : 0,
        }))
        .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));

      return reply.send({
        ok: true,
        asset,
        contributors,
        verdict: agg.rawVerdict,
        score: agg.rawScore,
        confidence: agg.rawConfidence,
        activeModules: agg.signals.map(s => s.module),
        droppedModules: [
          ...agg.alignment.dropped.map(d => ({ module: d.module, reason: d.reason })),
          ...agg.gatedModules.map(g => ({ module: g.module, reason: g.reason })),
        ],
        regime: agg.regime,
        updatedTs: Date.now(),
        ageMs: 0,
      });
    } catch {
      return reply.send({ ok: false, contributors: [], message: 'No data available' });
    }
  });

  // ═══════════════════════════════════════════════════════════
  // PHASE 3: Performance Tracking
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /performance — Module accuracy metrics
   */
  fastify.get('/performance', async (request, reply) => {
    const query = request.query as { asset?: string; horizon?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizon || '7', 10);

    const modules = await getPerformanceSummary(asset, horizonDays);

    return reply.send({
      ok: true,
      asset,
      horizonDays,
      modules,
    });
  });

  /**
   * POST /performance/eval — Manually trigger performance evaluation
   */
  fastify.post('/performance/eval', async (request, reply) => {
    const body = (request.body || {}) as { asset?: string; horizonDays?: number; limit?: number };
    const asset = (body.asset || 'BTC').toUpperCase();
    const horizonDays = body.horizonDays ?? 7;
    const limit = body.limit ?? 200;

    const result = await evaluatePerformance(asset, horizonDays, limit);

    return reply.send({
      ok: true,
      asset,
      horizonDays,
      ...result,
    });
  });

  // ═══════════════════════════════════════════════════════════
  // EXCHANGE KEEPALIVE
  // ═══════════════════════════════════════════════════════════

  /**
   * POST /exchange/refresh — Manually refresh stale exchange snapshots
   */
  fastify.post('/exchange/refresh', async (_request, reply) => {
    const result = await manualRefresh();
    return reply.send({ ok: true, ...result });
  });

  // Start exchange keepalive scheduler
  startExchangeKeepalive();

  // ═══════════════════════════════════════════════════════════
  // PHASE 3.1: Drift Detector
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /drift — Current drift state for all modules
   */
  fastify.get('/drift', async (request, reply) => {
    const query = request.query as { asset?: string; horizon?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizon || '7', 10);

    const states = await getAllDriftStates(asset, horizonDays);
    return reply.send({ ok: true, asset, horizonDays, modules: states });
  });

  /**
   * GET /drift/history — Drift history for a module over N days
   */
  fastify.get('/drift/history', async (request, reply) => {
    const query = request.query as { moduleId?: string; asset?: string; horizon?: string; days?: string };
    const moduleId = query.moduleId || 'exchange';
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizon || '7', 10);
    const days = parseInt(query.days || '30', 10);

    const history = await getDriftHistory(moduleId, asset, horizonDays, days);
    return reply.send({ ok: true, moduleId, asset, horizonDays, days, history });
  });

  /**
   * POST /drift/eval — Manually trigger drift evaluation
   */
  fastify.post('/drift/eval', async (request, reply) => {
    const body = (request.body || {}) as { asset?: string; horizonDays?: number; limit?: number };
    const asset = (body.asset || 'BTC').toUpperCase();
    const horizonDays = body.horizonDays ?? 7;
    const limit = body.limit ?? 60;

    const result = await evaluateDrift(asset, horizonDays, limit);
    return reply.send({ ok: true, asset, horizonDays, ...result });
  });

  console.log('[MetaBrain-V2] Phase 3.1 routes: /drift, /drift/history, /drift/eval');

  // ═══════════════════════════════════════════════════════════
  // PHASE 4: Confidence Calibration
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /calibration — Calibration buckets per module
   */
  fastify.get('/calibration', async (request, reply) => {
    const query = request.query as { asset?: string; horizon?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizon || '7', 10);

    const modules = await getCalibrationSummary(asset, horizonDays);
    return reply.send({ ok: true, asset, horizonDays, modules });
  });

  /**
   * POST /calibration/eval — Trigger calibration job
   */
  fastify.post('/calibration/eval', async (request, reply) => {
    const body = (request.body || {}) as { asset?: string; horizonDays?: number };
    const asset = (body.asset || 'BTC').toUpperCase();
    const horizonDays = body.horizonDays ?? 7;

    const result = await runCalibrationJob(asset, horizonDays);
    return reply.send({ ok: true, asset, horizonDays, ...result });
  });

  console.log('[MetaBrain-V2] Phase 4 routes: /calibration, /calibration/eval');

  // ═══════════════════════════════════════════════════════════
  // PHASE 5: Policy Endpoints + ML Dataset Builder + Correlation
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /policy — Active policy for current regime
   */
  fastify.get('/policy', async (request, reply) => {
    const query = request.query as { asset?: string };
    const asset = (query.asset || 'BTC').toUpperCase();

    const regimeResult = await getMarketRegime(asset);
    const policy = resolvePolicy(regimeResult.metaRegime);

    return reply.send({
      ok: true,
      asset,
      regime: regimeResult.metaRegime,
      policy,
      regimeSource: regimeResult.source,
    });
  });

  /**
   * GET /policy/all — All available policies (for admin/audit)
   */
  fastify.get('/policy/all', async (_request, reply) => {
    const policies = getAllPolicies();
    return reply.send({
      ok: true,
      regimes: Object.keys(policies),
      policies,
    });
  });

  /**
   * POST /run-evaluator/eval — Trigger ML dataset builder
   * Evaluates matured runs: backfills futureReturn, futureDirection, hit
   */
  fastify.post('/run-evaluator/eval', async (request, reply) => {
    const body = (request.body || {}) as { asset?: string; horizonDays?: number; limit?: number };
    const asset = (body.asset || 'BTC').toUpperCase();
    const horizonDays = body.horizonDays ?? 7;
    const limit = body.limit ?? 200;

    const result = await runMetaRunEvaluator(asset, horizonDays, limit);
    return reply.send({ ok: true, asset, horizonDays, ...result });
  });

  /**
   * GET /correlation — Current correlation matrix
   */
  fastify.get('/correlation', async (request, reply) => {
    const query = request.query as { asset?: string; horizon?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizon || '7', 10);

    const matrix = await getCorrelationMatrix(asset, horizonDays);
    return reply.send({ ok: true, asset, horizonDays, ...matrix });
  });

  /**
   * POST /correlation/eval — Trigger correlation matrix rebuild
   */
  fastify.post('/correlation/eval', async (request, reply) => {
    const body = (request.body || {}) as { asset?: string; horizonDays?: number; limit?: number };
    const asset = (body.asset || 'BTC').toUpperCase();
    const horizonDays = body.horizonDays ?? 7;
    const limit = body.limit ?? 100;

    const result = await computeCorrelationMatrix(asset, horizonDays, limit);
    return reply.send({ ok: true, asset, horizonDays, ...result });
  });

  console.log('[MetaBrain-V2] Phase 5 routes: /policy, /policy/all, /run-evaluator/eval, /correlation, /correlation/eval');

  // ═══════════════════════════════════════════════════════════
  // PHASE 5.1: ML DATASET ENDPOINTS + SCHEDULER
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /dataset/stats — ML dataset statistics (hit rate, coverage, by horizon/verdict)
   */
  fastify.get('/dataset/stats', async (request, reply) => {
    const query = request.query as { asset?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const stats = await getDatasetStats(asset);
    return reply.send({ ok: true, asset, ...stats });
  });

  /**
   * GET /dataset/runs — Paginated evaluated runs
   */
  fastify.get('/dataset/runs', async (request, reply) => {
    const query = request.query as { asset?: string; horizon?: string; limit?: string; skip?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = query.horizon ? parseInt(query.horizon, 10) : undefined;
    const limit = Math.min(parseInt(query.limit || '50', 10), 200);
    const skip = parseInt(query.skip || '0', 10);

    const result = await getDatasetRuns(asset, horizonDays, limit, skip);
    return reply.send({ ok: true, asset, ...result });
  });

  /**
   * POST /dataset/eval — Force evaluation of all horizons (manual trigger)
   */
  fastify.post('/dataset/eval', async (request, reply) => {
    const body = (request.body || {}) as { asset?: string; limit?: number };
    const asset = (body.asset || 'BTC').toUpperCase();
    const limit = body.limit ?? 200;

    const results: Record<string, any> = {};
    for (const h of [1, 7, 30]) {
      results[`${h}d`] = await runMetaRunEvaluator(asset, h, limit);
    }
    return reply.send({ ok: true, asset, results });
  });

  // Start ML dataset evaluator scheduler — skip in MINIMAL_BOOT
  if (process.env.MINIMAL_BOOT !== '1') {
    startRunEvaluatorScheduler();
  } else {
    console.log('[MetaBrain-V2] MINIMAL_BOOT — RunEvalScheduler skipped');
  }

  console.log('[MetaBrain-V2] Phase 5.1 routes: /dataset/stats, /dataset/runs, /dataset/eval');

  // ═══════════════════════════════════════════════════════════
  // PHASE 6: FORECAST ENDPOINT (for UI chart)
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /forecast — BTC price history + Meta Brain forecast curve
   * Used by MetaBrainChart frontend component.
   *
   * Returns:
   *   - history: OHLC candles (from market/candles proxy)
   *   - forecast: projected price path based on verdict + confidence
   *   - forecastBand: upper/lower confidence corridor
   *   - priceNow, verdict, metaConfidence, regime
   */
  fastify.get('/forecast', async (request, reply) => {
    const query = request.query as { asset?: string; horizonDays?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizonDays || '7', 10);

    try {
      // 1. Run Meta Brain pipeline for DISPLAY horizon
      const agg = await aggregate(asset, horizonDays);
      const stability = await applyStability(agg);

      const verdict = stability.finalVerdict;
      const metaConf = agg.metaConfidence.metaConfidence;

      // 2. Also run 7D pipeline for SIGNAL extraction (best coverage)
      // This ensures we always have directional signals for the forecast engine
      let signalAgg = agg;
      if (horizonDays !== 7) {
        try { signalAgg = await aggregate(asset, 7); } catch { signalAgg = agg; }
      }

      // 3. Fetch full candle history for "actual" series
      let actual: Array<{ t: string; v: number }> = [];
      let priceNow = 0;
      try {
        const candleResp = await fetch(`http://localhost:8003/api/ui/candles?asset=${asset}&years=2`, { signal: AbortSignal.timeout(8000) });
        const candleData = await candleResp.json() as any;
        if (candleData.ok && candleData.candles?.length) {
          actual = candleData.candles.map((c: any) => ({
            t: c.t,
            v: c.c ?? c.close ?? 0,
          }));
          priceNow = actual[actual.length - 1].v;
        }
      } catch { /* actual will be empty */ }

      // 4. Build forecast using signals from best pipeline (7D or current)
      const forecastSignals = signalAgg.signals.map(s => {
        const aligned = signalAgg.alignment.aligned.find(a => a.module === s.module);
        return {
          module: s.module,
          direction: (aligned?.direction ?? 'NEUTRAL') as 'LONG' | 'SHORT' | 'NEUTRAL',
          confidence: aligned?.confidence ?? 0,
          weight: s.weight,
        };
      });

      const coverageRatio = signalAgg.coverage.total > 0
        ? signalAgg.coverage.active / signalAgg.coverage.total
        : 0;

      const forecastBundle = buildMetaForecast({
        asset,
        currentPrice: priceNow,
        coverageRatio,
        signals: forecastSignals,
      });

      // CRITICAL: If final verdict is NEUTRAL, forecast must be FLAT.
      // The forecast service uses raw signals which may have directional bias,
      // but the stability/gating engine overrode to NEUTRAL — respect that.
      if (verdict === 'NEUTRAL') {
        for (const key of ['1d', '7d', '30d'] as const) {
          forecastBundle.items[key].expReturn = 0;
          forecastBundle.items[key].target = priceNow;
        }
      }

      // 5. Generate forecast series for chart — ONLY for selected horizon
      const hKey = horizonKeyFromDays(horizonDays);
      const target = forecastBundle.items[hKey]?.target ?? priceNow;
      const predicted = generateForecastSeries(priceNow, target, horizonDays);

      // 6. Module signals (from display horizon)
      const moduleSignals = agg.signals.map(s => {
        const aligned = agg.alignment.aligned.find(a => a.module === s.module);
        return {
          module: s.module,
          direction: aligned?.direction ?? 'NEUTRAL',
          impact: Math.round(s.weightedScore * 1000) / 1000,
          weight: Math.round(s.weight * 1000) / 1000,
          confidence: aligned?.confidence ?? 0,
        };
      });

      // Save forecast snapshot (fire-and-forget, throttled to 1/hour)
      // Uses the verdict-adjusted targets (NEUTRAL = flat)
      saveForecastSnapshot({
        ts: Date.now(),
        date: new Date().toISOString().split('T')[0],
        asset,
        priceNow,
        verdict,
        metaConfidence: metaConf,
        regime: agg.regime,
        forecast: {
          '1d': { target: forecastBundle.items['1d'].target, expReturn: forecastBundle.items['1d'].expReturn },
          '7d': { target: forecastBundle.items['7d'].target, expReturn: forecastBundle.items['7d'].expReturn },
          '30d': { target: forecastBundle.items['30d'].target, expReturn: forecastBundle.items['30d'].expReturn },
        },
      }).catch(() => {});

      return reply.send({
        ok: true,
        asset,
        priceNow,
        asOf: forecastBundle.asOf,
        charts: {
          actual,
          predicted,
        },
        forecast: forecastBundle,
        verdict,
        rawScore: agg.rawScore,
        metaConfidence: metaConf,
        regime: agg.regime,
        stability: {
          applied: stability.stabilityApplied,
          cooldownActive: stability.cooldownActive,
          previousVerdict: stability.previousVerdict,
        },
        coverage: agg.coverage,
        moduleSignals,
        metaConfidenceDetail: agg.metaConfidence,
      });
    } catch (error: any) {
      console.error('[MetaBrain-V2] Forecast error:', error.message);
      return reply.code(500).send({ ok: false, error: error.message });
    }
  });

  console.log('[MetaBrain-V2] Phase 6 routes: /forecast');

  // ═══════════════════════════════════════════════════════════
  // PHASE 6.1: ROLLING FORECAST CURVE
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /forecast-curve — Rolling forecast curve from stored snapshots
   *
   * Returns curve points built from real daily forecast snapshots.
   * Each snapshot contributes 3 points: t+1d, t+7d, t+30d.
   * Points are deduplicated by date and sorted.
   *
   * Also returns markers for the latest forecast (1D/7D/30D labels).
   */
  fastify.get('/forecast-curve', async (request, reply) => {
    const query = request.query as { asset?: string; horizonDays?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizonDays || '7', 10);
    const hKey = horizonDays <= 1 ? '1d' : horizonDays <= 7 ? '7d' : '30d';

    try {
      // 1. Get stored snapshots
      const snapshots = await getRecentSnapshots(asset, 60);

      // 2. Fetch current price
      let priceNow = 0;
      try {
        const candleResp = await fetch(`http://localhost:8003/api/ui/candles?asset=${asset}&years=2`, { signal: AbortSignal.timeout(8000) });
        const candleData = await candleResp.json() as any;
        if (candleData.ok && candleData.candles?.length) {
          priceNow = candleData.candles[candleData.candles.length - 1].c ?? 0;
        }
      } catch {}

      // 3. If no snapshots, run pipeline once to create the first
      if (snapshots.length === 0) {
        const agg = await aggregate(asset, 7);
        const stability = await applyStability(agg);
        const verdict = stability.finalVerdict;

        let signalAgg = agg;
        try { signalAgg = await aggregate(asset, 7); } catch { signalAgg = agg; }

        const forecastSignals = signalAgg.signals.map(s => {
          const aligned = signalAgg.alignment.aligned.find(a => a.module === s.module);
          return {
            module: s.module,
            direction: (aligned?.direction ?? 'NEUTRAL') as 'LONG' | 'SHORT' | 'NEUTRAL',
            confidence: aligned?.confidence ?? 0,
            weight: s.weight,
          };
        });

        const coverageRatio = signalAgg.coverage.total > 0
          ? signalAgg.coverage.active / signalAgg.coverage.total : 0;

        const forecastBundle = buildMetaForecast({
          asset, currentPrice: priceNow, coverageRatio, signals: forecastSignals,
        });

        // NEUTRAL = flat
        if (verdict === 'NEUTRAL') {
          for (const k of ['1d', '7d', '30d'] as const) {
            forecastBundle.items[k].expReturn = 0;
            forecastBundle.items[k].target = priceNow;
          }
        }

        const snap = {
          ts: Date.now(),
          date: new Date().toISOString().split('T')[0],
          asset,
          priceNow,
          verdict,
          metaConfidence: agg.metaConfidence.metaConfidence,
          regime: agg.regime,
          forecast: {
            '1d': { target: forecastBundle.items['1d'].target, expReturn: forecastBundle.items['1d'].expReturn },
            '7d': { target: forecastBundle.items['7d'].target, expReturn: forecastBundle.items['7d'].expReturn },
            '30d': { target: forecastBundle.items['30d'].target, expReturn: forecastBundle.items['30d'].expReturn },
          },
        };
        await saveForecastSnapshot(snap);
        snapshots.push(snap);

        // ── META V2 SHADOW: trigger Python V2 engine in background ──
        try {
          const v2Resp = await fetch(`http://localhost:8001/api/meta/v2/run?asset=${asset}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          });
          if (v2Resp.ok) {
            const v2Data = await v2Resp.json() as any;
            // Attach V2 result to snapshot for audit trail
            const v2Fields = {
              v2_direction: v2Data.v2_direction,
              v2_confidence: v2Data.v2_confidence,
              v2_score: v2Data.v2_score,
              v2_targets: v2Data.v2_targets,
              v2_mode: v2Data.v2_mode,
            };

            // Phase 4: Limited Live — use V2 if confidence meets guard
            const META_V2_PCT = 0.10;
            const useV2 = Math.random() < META_V2_PCT
              && v2Data.v2_confidence >= 0.35
              && v2Data.v2_direction !== 'NEUTRAL';

            if (useV2) {
              // Promote V2 to live
              const v2Verdict = v2Data.v2_direction as string;
              const v2Targets = v2Data.v2_targets;
              snap.verdict = v2Verdict;
              snap.forecast = {
                '1d': v2Targets['1d'],
                '7d': v2Targets['7d'],
                '30d': v2Targets['30d'],
              };
              snap.metaConfidence = v2Data.v2_confidence;
              await saveForecastSnapshot(snap); // overwrite with V2
              v2Fields['v2_promoted'] = true;
            } else {
              v2Fields['v2_promoted'] = false;
            }

            // Save audit
            const auditCol = fastify.mongo.db!.collection('meta_brain_v2_audit');
            await auditCol.insertOne({
              ts: Date.now(),
              date: snap.date,
              asset,
              v1_verdict: verdict,
              ...v2Fields,
              used_v2: useV2,
            });
          }
        } catch (e) {
          // V2 shadow is non-critical — don't break V1 pipeline
          console.warn('[MetaBrain-V2] Shadow V2 call failed:', (e as Error).message);
        }
      }

      // 4. Build REAL forecast points — only from actual snapshots
      // For 1D horizon: NO curve points (frontend shows arrow + % instead)
      // For 7D horizon: only 7D target (NO 1D marker)
      // For 30D horizon: only 7D + 30D targets
      const forecastPoints: Array<{ t: string; v: number; label: string }> = [];

      if (horizonDays > 1) {
        for (const snap of snapshots) {
          const baseMs = new Date(snap.date + 'T00:00:00Z').getTime();

          const entries: Array<{ offsetDays: number; key: string; label: string }> = [
            { offsetDays: 7, key: '7d', label: '7D' },
            { offsetDays: 30, key: '30d', label: '30D' },
          ];

          for (const e of entries) {
            if (e.offsetDays > horizonDays) continue;
            const target = snap.forecast[e.key as '7d' | '30d']?.target;
            if (target == null) continue;

            const pointMs = baseMs + e.offsetDays * 86400000;
            const pointDate = new Date(pointMs).toISOString().split('T')[0];

            forecastPoints.push({ t: pointDate, v: Math.round(target * 100) / 100, label: e.label });
          }
        }
      }

      // Deduplicate by date (keep latest snapshot's value)
      const pointMap = new Map<string, { t: string; v: number; label: string }>();
      for (const p of forecastPoints) {
        pointMap.set(p.t, p);
      }

      // Add anchor point (NOW = current price)
      const latestSnap = snapshots[snapshots.length - 1];
      const nowDate = latestSnap?.date || new Date().toISOString().split('T')[0];
      if (!pointMap.has(nowDate)) {
        pointMap.set(nowDate, { t: nowDate, v: priceNow, label: 'NOW' });
      }

      // Sort by date
      const curve = Array.from(pointMap.values())
        .sort((a, b) => a.t.localeCompare(b.t));

      // Markers = non-anchor points from latest snapshot only
      const markers = curve.filter(p => p.label !== 'NOW' && p.t > nowDate);

      return reply.send({
        ok: true,
        asset,
        horizonDays,
        priceNow,
        snapshotCount: snapshots.length,
        verdict: latestSnap?.verdict ?? 'NEUTRAL',
        metaConfidence: latestSnap?.metaConfidence ?? 0,
        regime: latestSnap?.regime ?? 'UNKNOWN',
        // For 1D: frontend uses forecastReturn to show arrow+%
        forecastReturn: latestSnap?.forecast?.['1d']?.expReturn ?? 0,
        curve,
        markers,
        latestForecast: latestSnap?.forecast ?? null,
      });
    } catch (error: any) {
      console.error('[MetaBrain-V2] Forecast-curve error:', error.message);
      return reply.code(500).send({ ok: false, error: error.message });
    }
  });

  console.log('[MetaBrain-V2] Phase 6.1 routes: /forecast-curve');

  // ═══════════════════════════════════════════════════════════
  // PHASE 6.2: FORECAST TABLE
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /forecast-table — Prediction table for Meta Brain
   *
   * Returns rows for the prediction table with day labels,
   * targets, confidence, and status (Hit/Miss/Pending).
   * Row count depends on horizonDays: 1D=3, 7D=9, 30D=32.
   */
  fastify.get('/forecast-table', async (request, reply) => {
    const query = request.query as { asset?: string; horizonDays?: string };
    const asset = (query.asset || 'BTC').toUpperCase();
    const horizonDays = parseInt(query.horizonDays || '7', 10);

    try {
      // Fetch candle data for price history
      let candles: Array<{ t: string; c: number }> = [];
      try {
        const candleResp = await fetch(
          `http://localhost:8003/api/ui/candles?asset=${asset}&years=2`,
          { signal: AbortSignal.timeout(8000) }
        );
        const candleData = await candleResp.json() as any;
        if (candleData.ok && candleData.candles) {
          candles = candleData.candles.map((c: any) => ({
            t: c.t,
            c: c.c,
          }));
        }
      } catch {}

      // Get current price
      const currentPrice = candles.length > 0 ? candles[candles.length - 1].c : 0;

      const table = await buildForecastTable(asset, horizonDays, candles, currentPrice);

      return reply.send({
        ok: true,
        asset,
        horizonDays,
        ...table,
      });
    } catch (error: any) {
      console.error('[MetaBrain-V2] Forecast-table error:', error.message);
      return reply.code(500).send({ ok: false, error: error.message });
    }
  });

  console.log('[MetaBrain-V2] Phase 6.2 routes: /forecast-table');

  // ═══════════════════════════════════════════════════════════
  // PHASE 7: MODULE REGISTRY + FEATURE FLAGS
  // ═══════════════════════════════════════════════════════════

  // Initialize default module flags on startup
  initModuleFlags().catch(err => console.error('[ModuleController] Init error:', err?.message));

  /**
   * GET /modules — All module flags (for admin UI)
   */
  fastify.get('/modules', async (_request, reply) => {
    const modules = await getAllModules();
    return reply.send({ ok: true, modules });
  });

  /**
   * POST /modules/update — Update module settings
   * Body: { module: string, enabled?: boolean, mode?: string, weightOverride?: number|null, maxSnapshotAgeHours?: number }
   */
  fastify.post('/modules/update', async (request, reply) => {
    const body = (request.body || {}) as {
      module?: string;
      enabled?: boolean;
      mode?: string;
      weightOverride?: number | null;
      maxSnapshotAgeHours?: number;
    };

    if (!body.module) {
      return reply.code(400).send({ ok: false, error: 'module name required' });
    }

    const updated = await updateModule(body.module, {
      enabled: body.enabled,
      mode: body.mode as any,
      weightOverride: body.weightOverride,
      maxSnapshotAgeHours: body.maxSnapshotAgeHours,
    });

    if (!updated) {
      return reply.code(404).send({ ok: false, error: `Module "${body.module}" not found` });
    }

    return reply.send({ ok: true, module: updated });
  });

  // ═══════════════════════════════════════════════════════════
  // PHASE 8: ACCURACY TRACKING LAYER (Truth & Proof)
  // ═══════════════════════════════════════════════════════════

  /**
   * GET /accuracy — Overall accuracy metrics
   * Query: ?asset=BTC&horizon=7D&minConfidence=0.6
   */
  fastify.get('/accuracy', async (request, reply) => {
    const query = request.query as { asset?: string; horizon?: string; minConfidence?: string };
    
    const filters: any = {};
    if (query.asset) filters.asset = query.asset.toUpperCase();
    if (query.horizon) filters.horizon = query.horizon as '24H' | '7D' | '30D';
    if (query.minConfidence) filters.minConfidence = parseFloat(query.minConfidence);
    
    const { calculateAccuracy } = await import('../outcomes/accuracy.service.js');
    const report = await calculateAccuracy(filters);
    
    return reply.send({ ok: true, ...report });
  });

  /**
   * GET /module-impact — Ablation test results
   * Shows which modules help vs hurt
   */
  fastify.get('/module-impact', async (_request, reply) => {
    const { calculateModuleImpact } = await import('../outcomes/module-impact.service.js');
    const impact = await calculateModuleImpact();
    
    return reply.send({ ok: true, impact });
  });

  /**
   * GET /outcomes — Raw outcomes (for debugging)
   * Query: ?limit=50
   */
  fastify.get('/outcomes', async (request, reply) => {
    const query = request.query as { limit?: string };
    const limit = parseInt(query.limit || '50', 10);
    
    const { getResolvedOutcomes } = await import('../outcomes/meta_brain_outcomes.repo.js');
    const outcomes = await getResolvedOutcomes();
    
    return reply.send({
      ok: true,
      count: outcomes.length,
      outcomes: outcomes.slice(0, limit),
    });
  });

  console.log('[MetaBrain-V2] Phase 8 routes: /accuracy, /module-impact, /outcomes');
  console.log('[MetaBrain-V2] Phase 7 routes: /modules, /modules/update');

  console.log('[MetaBrain-V2] Phase 3 routes registered: /performance, /performance/eval, /exchange/refresh');
  console.log('[MetaBrain-V2] Phase 2 routes registered: /run, /state');
  console.log('[MetaBrain-V2] Phase 1 routes registered: /signals, /signals/aligned, /status, /providers');
}

export default metaBrainV2Routes;
