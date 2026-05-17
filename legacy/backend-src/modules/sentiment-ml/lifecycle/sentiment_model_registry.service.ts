/**
 * Sentiment Model Registry Service
 * ==================================
 * 
 * BLOCK 5: Manages active/shadow model assignments per window.
 * 
 * Key functions:
 * - ensureWindow: Create registry entry if missing
 * - get: Get current registry state
 * - setShadow: Assign new shadow model
 * - promoteShadow: Promote shadow to active (ML mode)
 * - rollbackToRule: Revert to rule-based mode
 */

import { SentimentBinRegistry, type SentimentBinRegistryDoc, type SentimentActiveType } from '../binary/models/sentiment_bin_registry.model.js';
import { SentimentModelEventModel } from './sentiment_model_events.model.js';
import type { SentimentWindow } from '../contracts/sentiment-ml.types.js';

export class SentimentModelRegistryService {
  /**
   * Ensure registry entry exists for window
   */
  async ensureWindow(window: SentimentWindow): Promise<SentimentBinRegistryDoc> {
    const existing = await SentimentBinRegistry.findOne({ window });
    if (existing) return existing;

    return await SentimentBinRegistry.create({
      window,
      activeType: 'RULE',
      shadowType: 'ML',
      meta: { activeReason: 'init' },
    });
  }

  /**
   * Get registry for window
   */
  async get(window: SentimentWindow): Promise<SentimentBinRegistryDoc | null> {
    await this.ensureWindow(window);
    return SentimentBinRegistry.findOne({ window }).lean();
  }

  /**
   * Get active type for window
   */
  async getActiveType(window: SentimentWindow): Promise<SentimentActiveType> {
    const reg = await this.get(window);
    return reg?.activeType ?? 'RULE';
  }

  /**
   * Set shadow model (called after retrain)
   */
  async setShadow(window: SentimentWindow, shadowModelId: string, reason = 'retrain'): Promise<void> {
    await this.ensureWindow(window);
    
    await SentimentBinRegistry.updateOne(
      { window },
      {
        $set: {
          shadowModelId,
          'meta.shadowReason': reason,
          'meta.lastShadowSetAt': new Date(),
        },
      }
    );

    await SentimentModelEventModel.create({
      type: 'SHADOW_SET',
      window,
      modelId: shadowModelId,
      payload: { reason },
    });

    console.log(`[Registry] Shadow set for ${window}: ${shadowModelId}`);
  }

  /**
   * Promote shadow to active (switch from RULE to ML)
   */
  async promoteShadow(window: SentimentWindow, reason = 'auto_promotion'): Promise<{
    prevActiveModelId?: string;
    activeModelId: string;
  }> {
    const reg = await SentimentBinRegistry.findOne({ window });
    if (!reg) throw new Error(`Registry missing for window=${window}`);
    if (!reg.shadowModelId) throw new Error(`Shadow missing for window=${window}`);

    const prevActiveModelId = reg.activeModelId;
    
    reg.activeType = 'ML';
    reg.activeModelId = reg.shadowModelId;
    reg.meta.activeReason = reason;
    reg.meta.lastPromotionAt = new Date();
    await reg.save();

    await SentimentModelEventModel.create({
      type: 'PROMOTED',
      window,
      modelId: reg.activeModelId,
      prevModelId: prevActiveModelId,
      payload: { reason },
    });

    console.log(`[Registry] Promoted ${window}: ${prevActiveModelId} → ${reg.activeModelId}`);

    return { prevActiveModelId, activeModelId: reg.activeModelId };
  }

  /**
   * Rollback to RULE mode
   */
  async rollbackToRule(window: SentimentWindow, reason = 'auto_rollback'): Promise<{
    prevActiveModelId?: string;
  }> {
    const reg = await SentimentBinRegistry.findOne({ window });
    if (!reg) throw new Error(`Registry missing for window=${window}`);

    const prevActiveModelId = reg.activeModelId;

    reg.activeType = 'RULE';
    reg.activeModelId = undefined;
    reg.meta.activeReason = reason;
    reg.meta.lastRollbackAt = new Date();
    await reg.save();

    await SentimentModelEventModel.create({
      type: 'ROLLED_BACK',
      window,
      prevModelId: prevActiveModelId,
      payload: { reason },
    });

    console.log(`[Registry] Rolled back ${window} to RULE (was ${prevActiveModelId})`);

    return { prevActiveModelId };
  }

  /**
   * Get all registries
   */
  async getAll(): Promise<SentimentBinRegistryDoc[]> {
    for (const w of ['24H', '7D', '30D'] as SentimentWindow[]) {
      await this.ensureWindow(w);
    }
    return SentimentBinRegistry.find({}).lean();
  }
}

// Singleton
let registryInstance: SentimentModelRegistryService | null = null;

export function getSentimentModelRegistryService(): SentimentModelRegistryService {
  if (!registryInstance) {
    registryInstance = new SentimentModelRegistryService();
  }
  return registryInstance;
}

console.log('[Sentiment-ML] Model Registry Service loaded (BLOCK 5 Lifecycle)');
