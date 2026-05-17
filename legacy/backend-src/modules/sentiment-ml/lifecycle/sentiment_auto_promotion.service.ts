/**
 * Sentiment Auto-Promotion Service
 * ==================================
 * 
 * BLOCK 5 + S4: Evaluates if ML should be promoted to active.
 * 
 * Promotion Conditions (all must be true):
 * - Kill switch OFF
 * - Promotion lock OFF
 * - Cooldown passed (56 days since last promotion)
 * - Min finalized samples (150+)
 * - Sustained lift: ML better than Rule in 3 consecutive 14-day windows
 * - Edge delta >= 2%
 * 
 * S4 CAPITAL GATES (new):
 * - CapitalHealth >= 70%
 * - MaxDD <= 15%
 * - Expectancy > 0
 * - SharpeLike >= 0.10
 * - URI >= 60%
 * - Drift != DEGRADED/CRITICAL
 */

import type { SentimentWindow } from '../contracts/sentiment-ml.types.js';
import { getSentimentGuardsService, type SentimentGuardsService } from './sentiment_guards.service.js';
import { getSentimentModelRegistryService, type SentimentModelRegistryService } from './sentiment_model_registry.service.js';
import { getSentimentShadowWindowService, type SentimentShadowWindowService } from './sentiment_shadow_window.service.js';
import { SentimentModelEventModel } from './sentiment_model_events.model.js';
import { getSentimentCapitalGuard, type SentimentCapitalGuard } from './sentiment_capital_guard.js';

const DAY_MS = 24 * 60 * 60 * 1000;

// Configuration (can be overridden via env)
const CONFIG = {
  COOLDOWN_DAYS: Number(process.env.SENTIMENT_PROMOTION_COOLDOWN_DAYS ?? 56),
  MIN_FINALIZED: Number(process.env.SENTIMENT_PROMOTION_MIN_FINALIZED ?? 150),
  MIN_EDGE_DELTA: Number(process.env.SENTIMENT_PROMOTION_MIN_EDGE_DELTA ?? 0.02),
  SUSTAINED_WINDOWS: 3,
  WINDOW_DAYS: 14,
};

export interface PromotionResult {
  ok: boolean;
  promoted: boolean;
  reason?: string;
  activeModelId?: string;
  meta?: Record<string, any>;
}

export class SentimentAutoPromotionService {
  private guards: SentimentGuardsService;
  private registry: SentimentModelRegistryService;
  private shadowStats: SentimentShadowWindowService;
  private capitalGuard: SentimentCapitalGuard;

  constructor() {
    this.guards = getSentimentGuardsService();
    this.registry = getSentimentModelRegistryService();
    this.shadowStats = getSentimentShadowWindowService();
    this.capitalGuard = getSentimentCapitalGuard();
  }

  /**
   * Evaluate and potentially promote ML for a window
   */
  async evaluateAndPromote(window: SentimentWindow): Promise<PromotionResult> {
    // Guard checks
    const g = this.guards.getState();
    if (g.killSwitch) {
      return { ok: false, promoted: false, reason: 'kill_switch' };
    }
    if (g.promotionLock) {
      return { ok: false, promoted: false, reason: 'promotion_lock' };
    }

    // Registry check
    const reg = await this.registry.get(window);
    if (!reg) {
      return { ok: false, promoted: false, reason: 'no_registry' };
    }
    if (!reg.shadowModelId) {
      return { ok: false, promoted: false, reason: 'no_shadow_model' };
    }

    // Already ML active?
    if (reg.activeType === 'ML') {
      return { ok: true, promoted: false, reason: 'already_ml_active' };
    }

    // Cooldown check
    const lastPromotionAt = reg.meta?.lastPromotionAt ? new Date(reg.meta.lastPromotionAt) : null;
    if (lastPromotionAt && Date.now() - lastPromotionAt.getTime() < CONFIG.COOLDOWN_DAYS * DAY_MS) {
      const daysLeft = Math.ceil((CONFIG.COOLDOWN_DAYS * DAY_MS - (Date.now() - lastPromotionAt.getTime())) / DAY_MS);
      return { 
        ok: false, 
        promoted: false, 
        reason: 'cooldown',
        meta: { daysLeft, lastPromotionAt }
      };
    }

    // Get shadow stats for 3 windows (14d, 28d, 42d)
    const s14 = await this.shadowStats.getWindowStats(window, 14);
    const s28 = await this.shadowStats.getWindowStats(window, 28);
    const s42 = await this.shadowStats.getWindowStats(window, 42);

    // Min finalized check
    if (s42.finalized < CONFIG.MIN_FINALIZED) {
      return {
        ok: false,
        promoted: false,
        reason: 'not_enough_finalized',
        meta: { finalized: s42.finalized, required: CONFIG.MIN_FINALIZED },
      };
    }

    // Sustained lift check
    const ok14 = s14.edgeDelta >= CONFIG.MIN_EDGE_DELTA;
    const ok28 = s28.edgeDelta >= CONFIG.MIN_EDGE_DELTA;
    const ok42 = s42.edgeDelta >= CONFIG.MIN_EDGE_DELTA;

    if (!(ok14 && ok28 && ok42)) {
      return {
        ok: false,
        promoted: false,
        reason: 'not_sustained_lift',
        meta: {
          s14: { edge: s14.edgeDelta, pass: ok14 },
          s28: { edge: s28.edgeDelta, pass: ok28 },
          s42: { edge: s42.edgeDelta, pass: ok42 },
          required: CONFIG.MIN_EDGE_DELTA,
        },
      };
    }

    // S4: Capital Gate check
    const capitalGate = await this.capitalGuard.canPromote(window as any);
    if (!capitalGate.ok) {
      return {
        ok: false,
        promoted: false,
        reason: `capital_gate:${capitalGate.reason}`,
        meta: {
          capitalMetrics: capitalGate.metrics,
          s14, s28, s42,
        },
      };
    }

    // All conditions met - promote!
    const { prevActiveModelId, activeModelId } = await this.registry.promoteShadow(window, 'auto_promotion');

    await SentimentModelEventModel.create({
      type: 'PROMOTED',
      window,
      modelId: activeModelId,
      prevModelId: prevActiveModelId,
      payload: {
        s14: { finalized: s14.finalized, edge: s14.edgeDelta },
        s28: { finalized: s28.finalized, edge: s28.edgeDelta },
        s42: { finalized: s42.finalized, edge: s42.edgeDelta },
        capitalMetrics: capitalGate.metrics,
        config: CONFIG,
      },
    });

    console.log(`[Promotion] ML promoted for ${window}: ${activeModelId}`);

    return {
      ok: true,
      promoted: true,
      activeModelId,
      meta: { s14, s28, s42, capitalMetrics: capitalGate.metrics },
    };
  }

  /**
   * Get promotion readiness status (without promoting)
   */
  async getPromotionReadiness(window: SentimentWindow): Promise<{
    ready: boolean;
    blockers: string[];
    stats: {
      s14: { finalized: number; edge: number; pass: boolean };
      s28: { finalized: number; edge: number; pass: boolean };
      s42: { finalized: number; edge: number; pass: boolean };
    };
    capitalGate?: {
      ok: boolean;
      reason?: string;
      metrics?: any;
    };
  }> {
    const blockers: string[] = [];

    const g = this.guards.getState();
    if (g.killSwitch) blockers.push('Kill switch is ON');
    if (g.promotionLock) blockers.push('Promotion is locked');

    const reg = await this.registry.get(window);
    if (!reg?.shadowModelId) blockers.push('No shadow model');
    if (reg?.activeType === 'ML') blockers.push('Already ML active');

    const lastPromo = reg?.meta?.lastPromotionAt;
    if (lastPromo && Date.now() - new Date(lastPromo).getTime() < CONFIG.COOLDOWN_DAYS * DAY_MS) {
      blockers.push(`Cooldown active (${CONFIG.COOLDOWN_DAYS}d)`);
    }

    const s14 = await this.shadowStats.getWindowStats(window, 14);
    const s28 = await this.shadowStats.getWindowStats(window, 28);
    const s42 = await this.shadowStats.getWindowStats(window, 42);

    if (s42.finalized < CONFIG.MIN_FINALIZED) {
      blockers.push(`Need ${CONFIG.MIN_FINALIZED} finalized, have ${s42.finalized}`);
    }

    const ok14 = s14.edgeDelta >= CONFIG.MIN_EDGE_DELTA;
    const ok28 = s28.edgeDelta >= CONFIG.MIN_EDGE_DELTA;
    const ok42 = s42.edgeDelta >= CONFIG.MIN_EDGE_DELTA;

    if (!ok14) blockers.push(`14d edge ${(s14.edgeDelta*100).toFixed(1)}% < ${CONFIG.MIN_EDGE_DELTA*100}%`);
    if (!ok28) blockers.push(`28d edge ${(s28.edgeDelta*100).toFixed(1)}% < ${CONFIG.MIN_EDGE_DELTA*100}%`);
    if (!ok42) blockers.push(`42d edge ${(s42.edgeDelta*100).toFixed(1)}% < ${CONFIG.MIN_EDGE_DELTA*100}%`);

    // S4: Capital Gate check
    const capitalGate = await this.capitalGuard.canPromote(window as any);
    if (!capitalGate.ok) {
      blockers.push(`Capital gate: ${capitalGate.reason}`);
    }

    return {
      ready: blockers.length === 0,
      blockers,
      stats: {
        s14: { finalized: s14.finalized, edge: s14.edgeDelta, pass: ok14 },
        s28: { finalized: s28.finalized, edge: s28.edgeDelta, pass: ok28 },
        s42: { finalized: s42.finalized, edge: s42.edgeDelta, pass: ok42 },
      },
      capitalGate: {
        ok: capitalGate.ok,
        reason: capitalGate.ok ? undefined : capitalGate.reason,
        metrics: capitalGate.metrics,
      },
    };
  }
}

// Singleton
let promotionInstance: SentimentAutoPromotionService | null = null;

export function getSentimentAutoPromotionService(): SentimentAutoPromotionService {
  if (!promotionInstance) {
    promotionInstance = new SentimentAutoPromotionService();
  }
  return promotionInstance;
}

console.log('[Sentiment-ML] Auto-Promotion Service loaded (BLOCK 5 Lifecycle)');
