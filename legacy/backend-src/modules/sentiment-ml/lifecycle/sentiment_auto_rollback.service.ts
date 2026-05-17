/**
 * Sentiment Auto-Rollback Service
 * =================================
 * 
 * BLOCK 5 + S4: Evaluates if ML should be rolled back to RULE.
 * 
 * Only applies when activeType = ML.
 * 
 * Rollback Conditions:
 * 
 * Original (hit-rate based):
 * - ML hit rate <= Rule hit rate - 3%
 * - After min finalized (80+) in 14-day lookback
 * - Cooldown: 14 days between rollbacks
 * 
 * S4 Capital triggers (new):
 * - Rolling 30D: Expectancy < 0 OR MaxDD > 20% OR Sharpe < 0
 * - AND CapitalHealth < 50%
 */

import type { SentimentWindow } from '../contracts/sentiment-ml.types.js';
import { getSentimentGuardsService, type SentimentGuardsService } from './sentiment_guards.service.js';
import { getSentimentModelRegistryService, type SentimentModelRegistryService } from './sentiment_model_registry.service.js';
import { getSentimentShadowWindowService, type SentimentShadowWindowService } from './sentiment_shadow_window.service.js';
import { SentimentModelEventModel } from './sentiment_model_events.model.js';
import { getSentimentCapitalGuard, type SentimentCapitalGuard } from './sentiment_capital_guard.js';

const DAY_MS = 24 * 60 * 60 * 1000;

// Configuration
const CONFIG = {
  COOLDOWN_DAYS: Number(process.env.SENTIMENT_ROLLBACK_COOLDOWN_DAYS ?? 14),
  MIN_FINALIZED: Number(process.env.SENTIMENT_ROLLBACK_MIN_FINALIZED ?? 80),
  MAX_NEG_DELTA: Number(process.env.SENTIMENT_ROLLBACK_MAX_NEG_DELTA ?? -0.03),
  LOOKBACK_DAYS: 14,
};

export interface RollbackResult {
  ok: boolean;
  rolledBack: boolean;
  reason?: string;
  meta?: Record<string, any>;
}

export class SentimentAutoRollbackService {
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
   * Evaluate and potentially rollback ML for a window
   */
  async evaluateAndRollback(window: SentimentWindow): Promise<RollbackResult> {
    // Guard checks
    const g = this.guards.getState();
    if (g.killSwitch) {
      return { ok: false, rolledBack: false, reason: 'kill_switch' };
    }

    // Registry check
    const reg = await this.registry.get(window);
    if (!reg) {
      return { ok: false, rolledBack: false, reason: 'no_registry' };
    }

    // Only rollback if ML is active
    if (reg.activeType !== 'ML') {
      return { ok: true, rolledBack: false, reason: 'active_not_ml' };
    }

    // Cooldown check
    const lastRollbackAt = reg.meta?.lastRollbackAt ? new Date(reg.meta.lastRollbackAt) : null;
    if (lastRollbackAt && Date.now() - lastRollbackAt.getTime() < CONFIG.COOLDOWN_DAYS * DAY_MS) {
      const daysLeft = Math.ceil((CONFIG.COOLDOWN_DAYS * DAY_MS - (Date.now() - lastRollbackAt.getTime())) / DAY_MS);
      return {
        ok: false,
        rolledBack: false,
        reason: 'cooldown',
        meta: { daysLeft, lastRollbackAt },
      };
    }

    // Get shadow stats for 14-day lookback
    const s14 = await this.shadowStats.getWindowStats(window, CONFIG.LOOKBACK_DAYS);

    // Min finalized check
    if (s14.finalized < CONFIG.MIN_FINALIZED) {
      return {
        ok: true,
        rolledBack: false,
        reason: 'not_enough_finalized',
        meta: { finalized: s14.finalized, required: CONFIG.MIN_FINALIZED },
      };
    }

    // S4: Check capital-based rollback first (takes priority)
    const capitalRollback = await this.capitalGuard.shouldRollback(window as any);
    if (capitalRollback.ok) {
      const { prevActiveModelId } = await this.registry.rollbackToRule(window, 'auto_rollback_capital');
      
      // Lock promotion for 14 days after capital-based rollback
      this.guards.setPromotionLockUntil(new Date(Date.now() + 14 * DAY_MS));

      await SentimentModelEventModel.create({
        type: 'ROLLED_BACK',
        window,
        prevModelId: prevActiveModelId,
        payload: {
          trigger: 'CAPITAL',
          capitalMetrics: capitalRollback.metrics,
          reason: capitalRollback.reason,
        },
      });

      console.log(`[Rollback] ML rolled back for ${window} due to CAPITAL: ${capitalRollback.reason}`);

      return {
        ok: true,
        rolledBack: true,
        reason: `capital_rollback:${capitalRollback.reason}`,
        meta: { capitalMetrics: capitalRollback.metrics },
      };
    }

    // Original: Check if ML is underperforming by hit-rate
    // edgeDelta = hitML - hitRule
    // If edgeDelta <= -0.03, ML is 3%+ worse than Rule
    if (s14.edgeDelta <= CONFIG.MAX_NEG_DELTA) {
      const { prevActiveModelId } = await this.registry.rollbackToRule(window, 'auto_rollback_edge');

      await SentimentModelEventModel.create({
        type: 'ROLLED_BACK',
        window,
        prevModelId: prevActiveModelId,
        payload: {
          trigger: 'EDGE',
          s14,
          threshold: CONFIG.MAX_NEG_DELTA,
          reason: `ML underperforming by ${(s14.edgeDelta * 100).toFixed(1)}%`,
        },
      });

      console.log(`[Rollback] ML rolled back for ${window}: edge ${(s14.edgeDelta * 100).toFixed(1)}%`);

      return {
        ok: true,
        rolledBack: true,
        meta: { s14, threshold: CONFIG.MAX_NEG_DELTA },
      };
    }

    return {
      ok: true,
      rolledBack: false,
      meta: { s14, threshold: CONFIG.MAX_NEG_DELTA, capitalCheck: capitalRollback },
    };
  }

  /**
   * Get rollback risk status
   */
  async getRollbackRisk(window: SentimentWindow): Promise<{
    atRisk: boolean;
    activeType: string;
    edge: number;
    threshold: number;
    finalized: number;
  }> {
    const reg = await this.registry.get(window);
    if (!reg || reg.activeType !== 'ML') {
      return {
        atRisk: false,
        activeType: reg?.activeType ?? 'RULE',
        edge: 0,
        threshold: CONFIG.MAX_NEG_DELTA,
        finalized: 0,
      };
    }

    const s14 = await this.shadowStats.getWindowStats(window, CONFIG.LOOKBACK_DAYS);
    
    return {
      atRisk: s14.edgeDelta <= CONFIG.MAX_NEG_DELTA && s14.finalized >= CONFIG.MIN_FINALIZED,
      activeType: 'ML',
      edge: s14.edgeDelta,
      threshold: CONFIG.MAX_NEG_DELTA,
      finalized: s14.finalized,
    };
  }
}

// Singleton
let rollbackInstance: SentimentAutoRollbackService | null = null;

export function getSentimentAutoRollbackService(): SentimentAutoRollbackService {
  if (!rollbackInstance) {
    rollbackInstance = new SentimentAutoRollbackService();
  }
  return rollbackInstance;
}

console.log('[Sentiment-ML] Auto-Rollback Service loaded (BLOCK 5 Lifecycle)');
