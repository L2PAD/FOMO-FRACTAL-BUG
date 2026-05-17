/**
 * Project Intelligence Routes
 *
 * POST /api/project-intelligence/analyze         — Full single-asset analysis
 * POST /api/project-intelligence/batch            — Batch analysis for multiple assets
 * POST /api/project-intelligence/quick            — Quick assessment (pipeline use)
 * GET  /api/project-intelligence/profiles         — Known project profiles
 * GET  /api/project-intelligence/profile/:asset   — Single project profile
 */

import type { FastifyInstance } from 'fastify';
import { projectIntelligenceOrchestrator } from './services/project-intelligence-orchestrator.service.js';
import { KNOWN_PROFILES, getProjectProfile } from './services/known-profiles.js';

export async function projectIntelligenceRoutes(app: FastifyInstance): Promise<void> {
  /**
   * POST /api/project-intelligence/analyze — Full analysis
   * Body: { asset: string, dynamicData?: { currentPrice, fdv, marketCap, ... } }
   */
  app.post<{
    Body: { asset: string; dynamicData?: Record<string, any> };
  }>('/analyze', async (request) => {
    const { asset, dynamicData } = request.body;
    if (!asset) return { ok: false, error: 'asset required' };

    const intel = projectIntelligenceOrchestrator.analyze(asset, dynamicData);
    return { ok: true, intel };
  });

  /**
   * POST /api/project-intelligence/batch — Batch analysis
   * Body: { assets: string[], dynamicData?: { [asset]: { currentPrice, fdv, ... } } }
   */
  app.post<{
    Body: { assets: string[]; dynamicData?: Record<string, Record<string, any>> };
  }>('/batch', async (request) => {
    const { assets, dynamicData } = request.body;
    if (!assets?.length) return { ok: false, error: 'assets array required' };

    const results = projectIntelligenceOrchestrator.analyzeBatch(
      assets.slice(0, 30),
      dynamicData,
    );
    return { ok: true, results, count: Object.keys(results).length };
  });

  /**
   * POST /api/project-intelligence/quick — Quick assessment (used by pipeline)
   * Body: { asset: string, dynamicData?: { currentPrice, fdv, ... } }
   */
  app.post<{
    Body: { asset: string; dynamicData?: Record<string, any> };
  }>('/quick', async (request) => {
    const { asset, dynamicData } = request.body;
    if (!asset) return { ok: false, error: 'asset required' };

    const result = projectIntelligenceOrchestrator.quickAssess(asset, dynamicData);
    return { ok: true, ...result };
  });

  /**
   * GET /api/project-intelligence/profiles — Known project profiles
   */
  app.get('/profiles', async () => {
    const profiles = Object.keys(KNOWN_PROFILES);
    return {
      ok: true,
      profiles,
      count: profiles.length,
    };
  });

  /**
   * GET /api/project-intelligence/profile/:asset — Single profile
   */
  app.get<{ Params: { asset: string } }>('/profile/:asset', async (request) => {
    const profile = getProjectProfile(request.params.asset);
    return { ok: true, profile };
  });
}
