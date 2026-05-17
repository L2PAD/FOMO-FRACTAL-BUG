/**
 * Shared Admin Routes
 * =====================
 * 
 * F1/F2/F4/F5/F6: Manifest, Evidence, Calibration, Simulation Registry, Feature Locks.
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getSentimentManifestService, getExchangeManifestService } from './module-manifest.service.js';
import { getEvidenceWriterService, EvidenceType, EvidenceSeverity, EvidenceModule } from './evidence-writer.service.js';
import { getFeatureFlagLockService } from './feature-flag-lock.service.js';
import { getSentimentCalibrationGuard, getExchangeCalibrationGuard } from './calibration-guard.service.js';
import { getSimulationRunRegistryService } from './simulation-run-registry.service.js';

async function sharedAdminRoutes(app: FastifyInstance): Promise<void> {
  const sentimentManifest = getSentimentManifestService();
  const exchangeManifest = getExchangeManifestService();
  const evidenceWriter = getEvidenceWriterService();
  const lockService = getFeatureFlagLockService();
  const simRegistry = getSimulationRunRegistryService();

  // ═══════════════════════════════════════════════════════════════
  // MANIFEST ENDPOINTS (F1)
  // ═══════════════════════════════════════════════════════════════

  app.get('/sentiment/manifest', async () => {
    return { ok: true, manifest: sentimentManifest.getManifestForAPI() };
  });

  app.get('/exchange/manifest', async () => {
    return { ok: true, manifest: exchangeManifest.getManifestForAPI() };
  });

  app.get('/manifests', async () => {
    const sentiment = sentimentManifest.getManifestForAPI();
    const exchange = exchangeManifest.getManifestForAPI();
    return {
      ok: true,
      modules: {
        sentiment: { name: sentiment.moduleName, version: sentiment.version, frozen: sentiment.freezeStatus.frozen, flags: sentiment.flags },
        exchange: { name: exchange.moduleName, version: exchange.version, frozen: exchange.freezeStatus.frozen, flags: exchange.flags },
      },
    };
  });

  // ═══════════════════════════════════════════════════════════════
  // EVIDENCE ENDPOINTS (F2)
  // ═══════════════════════════════════════════════════════════════

  app.get('/evidence/recent', async (req: FastifyRequest<{
    Querystring: { module?: string; type?: string; severity?: string; limit?: string; since?: string }
  }>) => {
    const module = (req.query.module || 'sentiment') as EvidenceModule;
    const type = req.query.type as EvidenceType | undefined;
    const severity = req.query.severity as EvidenceSeverity | undefined;
    const limit = parseInt(req.query.limit || '50', 10);
    const since = req.query.since ? new Date(req.query.since) : undefined;
    const events = await evidenceWriter.getRecent(module, { limit, type, severity, since });
    return { ok: true, module, count: events.length, events };
  });

  app.get('/evidence/stats', async (req: FastifyRequest<{ Querystring: { module?: string } }>) => {
    const module = (req.query.module || 'sentiment') as EvidenceModule;
    const stats = await evidenceWriter.getStats(module);
    return { ok: true, module, period: '24h', eventCounts: stats };
  });

  app.post('/evidence/test', async (req: FastifyRequest<{ Body: { module?: string; message?: string } }>) => {
    const body = req.body || {};
    const module = (body.module || 'sentiment') as EvidenceModule;
    await evidenceWriter.append(module, 'guard_state_changed', 'INFO', body.message || 'Test event', { manifestVersion: '1.0.0' }, { test: true });
    return { ok: true, message: 'Test event written' };
  });

  // ═══════════════════════════════════════════════════════════════
  // FEATURE FLAG LOCK ENDPOINTS (F6)
  // ═══════════════════════════════════════════════════════════════

  app.get('/feature-lock/:moduleKey/status', async (req: FastifyRequest<{ Params: { moduleKey: string } }>) => {
    const { moduleKey } = req.params;
    const status = await lockService.getStatus(moduleKey);
    return { ok: true, moduleKey, ...status };
  });

  app.post('/feature-lock/:moduleKey/lock', async (req: FastifyRequest<{
    Params: { moduleKey: string };
    Body: { reason?: string; ttlHours?: number }
  }>) => {
    const { moduleKey } = req.params;
    const body = req.body || {};
    
    // Check if module is frozen
    const manifest = moduleKey === 'sentiment' ? sentimentManifest : exchangeManifest;
    const freezeStatus = manifest.checkFreezeStatus();
    if (freezeStatus.frozen) {
      return { ok: false, code: 'MODULE_FROZEN', message: 'Cannot lock frozen module' };
    }

    const doc = await lockService.lock(moduleKey, {
      reason: body.reason || 'maintenance',
      ttlHours: body.ttlHours || 24,
    });
    return { ok: true, locked: true, unlockAt: doc.unlockAt, reason: doc.reason };
  });

  app.post('/feature-lock/:moduleKey/unlock', async (req: FastifyRequest<{
    Params: { moduleKey: string };
    Body: { reason?: string }
  }>) => {
    const { moduleKey } = req.params;
    const body = req.body || {};

    // Check if module is frozen
    const manifest = moduleKey === 'sentiment' ? sentimentManifest : exchangeManifest;
    const freezeStatus = manifest.checkFreezeStatus();
    if (freezeStatus.frozen) {
      return { ok: false, code: 'MODULE_FROZEN', message: 'Cannot unlock frozen module' };
    }

    const unlocked = await lockService.unlock(moduleKey, body.reason || 'manual');
    return { ok: true, unlocked };
  });

  app.get('/feature-lock/active', async () => {
    const locks = await lockService.listActiveLocks();
    return { ok: true, count: locks.length, locks };
  });

  // ═══════════════════════════════════════════════════════════════
  // CALIBRATION ENDPOINTS (F4)
  // ═══════════════════════════════════════════════════════════════

  app.get('/calibration/:moduleKey/latest', async (req: FastifyRequest<{
    Params: { moduleKey: string };
    Querystring: { window?: string }
  }>) => {
    const { moduleKey } = req.params;
    const window = req.query.window || '24H';
    const guard = moduleKey === 'sentiment' ? getSentimentCalibrationGuard() : getExchangeCalibrationGuard();
    const result = await guard.getLatestStatus(window);

    if (!result) {
      return { ok: true, hasData: false, message: 'No calibration data yet. Run calibration first.' };
    }

    return {
      ok: true,
      hasData: true,
      moduleKey,
      window,
      status: result.status,
      ece: `${(result.ece * 100).toFixed(2)}%`,
      eceRaw: result.ece,
      total: result.total,
      confidenceMultiplier: result.confidenceMultiplier,
      promotionAllowed: result.promotionAllowed,
      buckets: result.buckets,
    };
  });

  app.get('/calibration/:moduleKey/buckets', async (req: FastifyRequest<{
    Params: { moduleKey: string };
    Querystring: { window?: string; channel?: string }
  }>) => {
    const { moduleKey } = req.params;
    const window = req.query.window || '24H';
    const channel = req.query.channel || 'RULE';
    const guard = moduleKey === 'sentiment' ? getSentimentCalibrationGuard() : getExchangeCalibrationGuard();
    const buckets = await guard.getBuckets(window, channel);

    return {
      ok: true,
      moduleKey,
      window,
      channel,
      count: buckets.length,
      buckets: buckets.map(b => ({
        range: `${b.bucketMin.toFixed(2)}-${b.bucketMax.toFixed(2)}`,
        n: b.n,
        wins: b.wins,
        posteriorMean: b.posteriorMean.toFixed(3),
        empiricalWinRate: b.empiricalWinRate.toFixed(3),
        calibrationError: b.calibrationError.toFixed(3),
      })),
    };
  });

  app.post('/calibration/:moduleKey/run', async (req: FastifyRequest<{
    Params: { moduleKey: string };
    Body: { window?: string; decisions?: Array<{ confidence: number; correct: boolean }> }
  }>) => {
    const { moduleKey } = req.params;
    const body = req.body || {};
    const window = body.window || '24H';

    // For testing, allow passing decisions directly
    // In production, this would fetch from shadow decisions
    const decisions = body.decisions || [];

    if (!decisions.length) {
      return {
        ok: true,
        message: 'No decisions provided. In production, provide decisions array or integrate with shadow decisions.',
        example: { decisions: [{ confidence: 0.72, correct: true }, { confidence: 0.65, correct: false }] },
      };
    }

    const guard = moduleKey === 'sentiment' ? getSentimentCalibrationGuard() : getExchangeCalibrationGuard();
    const result = await guard.run(window, decisions);

    return {
      ok: true,
      moduleKey,
      window,
      status: result.status,
      ece: `${(result.ece * 100).toFixed(2)}%`,
      total: result.total,
      confidenceMultiplier: result.confidenceMultiplier,
      promotionAllowed: result.promotionAllowed,
      buckets: result.buckets,
    };
  });

  // ═══════════════════════════════════════════════════════════════
  // SIMULATION RUN REGISTRY ENDPOINTS (F5)
  // ═══════════════════════════════════════════════════════════════

  app.get('/sim-runs/recent', async (req: FastifyRequest<{
    Querystring: { moduleKey?: string; limit?: string }
  }>) => {
    const moduleKey = req.query.moduleKey || 'sentiment';
    const limit = parseInt(req.query.limit || '20', 10);
    const runs = await simRegistry.listRuns(moduleKey, limit);

    return {
      ok: true,
      moduleKey,
      count: runs.length,
      runs: runs.map(r => ({
        runId: r.runId,
        kind: r.kind,
        window: r.window,
        status: r.status,
        createdAt: r.createdAt,
        finishedAt: r.finishedAt,
        resultSummary: r.resultSummary,
      })),
    };
  });

  app.get('/sim-runs/:runId', async (req: FastifyRequest<{ Params: { runId: string } }>) => {
    const { runId } = req.params;
    const run = await simRegistry.getRun(runId);

    if (!run) {
      return { ok: false, code: 'NOT_FOUND', message: 'Run not found' };
    }

    return { ok: true, run };
  });

  app.get('/sim-runs/stats/:moduleKey', async (req: FastifyRequest<{ Params: { moduleKey: string } }>) => {
    const { moduleKey } = req.params;
    const stats = await simRegistry.getStats(moduleKey);
    return { ok: true, moduleKey, stats };
  });

  app.post('/sim-runs/create', async (req: FastifyRequest<{
    Body: {
      moduleKey: string;
      kind: string;
      window?: string;
      params?: Record<string, any>;
    }
  }>) => {
    const body = req.body || {};
    const manifest = body.moduleKey === 'sentiment' ? sentimentManifest : exchangeManifest;

    const { runId } = await simRegistry.createRun({
      moduleKey: body.moduleKey || 'sentiment',
      kind: body.kind || 'MANUAL',
      window: body.window,
      params: body.params || {},
      manifest: manifest.loadManifest(),
      dataFingerprint: simRegistry.sha256({ moduleKey: body.moduleKey, kind: body.kind, ts: Date.now() }),
      codeFingerprint: 'sim_engine_v1.0.0',
    });

    return { ok: true, runId };
  });
}

export default fp(sharedAdminRoutes, {
  name: 'shared-admin-routes',
  fastify: '4.x',
});

export { sharedAdminRoutes };
