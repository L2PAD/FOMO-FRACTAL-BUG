/**
 * Sentiment Lifecycle Admin Routes
 * ==================================
 * 
 * BLOCK 5: Admin API for lifecycle management.
 * 
 * Endpoints:
 * - GET /registry — Current registry state for all windows
 * - GET /promotion/readiness — Check promotion readiness
 * - POST /promotion/tick — Run promotion evaluation
 * - POST /rollback/tick — Run rollback evaluation
 * - GET /events — Recent lifecycle events
 * - GET /shadow/window — Shadow stats for lookback window
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getSentimentModelRegistryService } from './sentiment_model_registry.service.js';
import { getSentimentAutoPromotionService } from './sentiment_auto_promotion.service.js';
import { getSentimentAutoRollbackService } from './sentiment_auto_rollback.service.js';
import { getSentimentShadowWindowService } from './sentiment_shadow_window.service.js';
import { getSentimentGuardsService } from './sentiment_guards.service.js';
import { SentimentModelEventModel } from './sentiment_model_events.model.js';
import type { SentimentWindow } from '../contracts/sentiment-ml.types.js';

const WINDOWS: SentimentWindow[] = ['24H', '7D', '30D'];

async function sentimentLifecycleRoutes(app: FastifyInstance): Promise<void> {
  const registry = getSentimentModelRegistryService();
  const promotion = getSentimentAutoPromotionService();
  const rollback = getSentimentAutoRollbackService();
  const shadowWindow = getSentimentShadowWindowService();
  const guards = getSentimentGuardsService();

  /**
   * GET /status — Lifecycle status summary
   */
  app.get('/status', async () => {
    const regs = await registry.getAll();
    const guardsState = guards.getState();
    
    const windows: Record<string, any> = {};
    for (const r of regs) {
      windows[r.window] = {
        activeType: r.activeType,
        activeModelId: r.activeModelId,
        shadowModelId: r.shadowModelId,
      };
    }
    
    return {
      ok: true,
      lifecycle: {
        guardsLevel: guardsState.level,
        guardsReasons: guardsState.reasons,
        windows,
        promotionEnabled: false,
        rollbackEnabled: false,
      },
    };
  });

  /**
   * GET /registry — Current registry state
   */
  app.get('/registry', async () => {
    const regs = await registry.getAll();
    
    return {
      ok: true,
      guards: guards.getState(),
      windows: regs.reduce((acc, r) => {
        acc[r.window] = {
          activeType: r.activeType,
          activeModelId: r.activeModelId,
          shadowModelId: r.shadowModelId,
          meta: r.meta,
        };
        return acc;
      }, {} as Record<string, any>),
    };
  });

  /**
   * GET /promotion/readiness — Check promotion readiness for all windows
   */
  app.get('/promotion/readiness', async (req: FastifyRequest<{ Querystring: { window?: string } }>) => {
    const window = (req.query.window?.toUpperCase() || '24H') as SentimentWindow;
    
    const readiness = await promotion.getPromotionReadiness(window);
    
    return {
      ok: true,
      window,
      ...readiness,
    };
  });

  /**
   * POST /promotion/tick — Run promotion evaluation for all windows
   */
  app.post('/promotion/tick', async () => {
    const results: Record<string, any> = {};
    
    for (const w of WINDOWS) {
      results[w] = await promotion.evaluateAndPromote(w);
    }
    
    return {
      ok: true,
      results,
    };
  });

  /**
   * POST /rollback/tick — Run rollback evaluation for all windows
   */
  app.post('/rollback/tick', async () => {
    const results: Record<string, any> = {};
    
    for (const w of WINDOWS) {
      results[w] = await rollback.evaluateAndRollback(w);
    }
    
    return {
      ok: true,
      results,
    };
  });

  /**
   * GET /rollback/risk — Get rollback risk for all windows
   */
  app.get('/rollback/risk', async () => {
    const results: Record<string, any> = {};
    
    for (const w of WINDOWS) {
      results[w] = await rollback.getRollbackRisk(w);
    }
    
    return {
      ok: true,
      results,
    };
  });

  /**
   * GET /shadow/window — Get shadow stats for lookback window
   */
  app.get('/shadow/window', async (req: FastifyRequest<{ Querystring: { window?: string; days?: string } }>) => {
    const window = (req.query.window?.toUpperCase() || '24H') as SentimentWindow;
    const days = Number(req.query.days ?? 14);
    
    const stats = await shadowWindow.getWindowStats(window, days);
    
    return {
      ok: true,
      window,
      lookbackDays: days,
      stats,
      formatted: {
        hitRuleRate: `${(stats.hitRule / Math.max(1, stats.finalized) * 100).toFixed(1)}%`,
        hitMLRate: `${(stats.hitML / Math.max(1, stats.finalized) * 100).toFixed(1)}%`,
        edgeDelta: `${stats.edgeDelta >= 0 ? '+' : ''}${(stats.edgeDelta * 100).toFixed(1)}%`,
        disagreement: `${(stats.disagreement * 100).toFixed(1)}%`,
      },
    };
  });

  /**
   * GET /events — Recent lifecycle events
   */
  app.get('/events', async (req: FastifyRequest<{ Querystring: { limit?: string } }>) => {
    const limit = Number(req.query.limit ?? 50);
    
    const events = await SentimentModelEventModel.find()
      .sort({ createdAt: -1 })
      .limit(limit)
      .lean();
    
    return {
      ok: true,
      count: events.length,
      events: events.map(e => ({
        type: e.type,
        window: e.window,
        modelId: e.modelId,
        prevModelId: e.prevModelId,
        createdAt: e.createdAt,
      })),
    };
  });

  /**
   * GET /dashboard — Combined dashboard data
   */
  app.get('/dashboard', async () => {
    const regs = await registry.getAll();
    const guardsState = guards.getState();
    
    const windows: Record<string, any> = {};
    
    for (const w of WINDOWS) {
      const reg = regs.find(r => r.window === w);
      const readiness = await promotion.getPromotionReadiness(w);
      const risk = await rollback.getRollbackRisk(w);
      
      windows[w] = {
        activeType: reg?.activeType ?? 'RULE',
        activeModelId: reg?.activeModelId,
        shadowModelId: reg?.shadowModelId,
        promotionReadiness: readiness,
        rollbackRisk: risk,
      };
    }
    
    return {
      ok: true,
      guards: guardsState,
      windows,
    };
  });

  console.log('[Sentiment-ML] Lifecycle admin routes registered (BLOCK 5)');
}

// Export wrapped in fastify-plugin
export default fp(sentimentLifecycleRoutes, {
  name: 'sentiment-lifecycle-routes',
  fastify: '4.x',
});

export { sentimentLifecycleRoutes };
