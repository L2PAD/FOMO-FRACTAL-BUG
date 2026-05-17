/**
 * Sentiment Guards Service
 * =========================
 * 
 * BLOCK 5 + S4: System-level guards for lifecycle control.
 * 
 * Guards:
 * - killSwitch: Disable all signals (everything returns NEUTRAL)
 * - promotionLock: Prevent auto-promotion
 * - promotionLockUntil: Time-based promotion lock (S4)
 * - retrainEnabled: Allow/block retraining
 * - shadowEnabled: Enable/disable shadow recording
 */

export interface SentimentGuardState {
  killSwitch: boolean;
  promotionLock: boolean;
  promotionLockUntil: Date | null;
  retrainEnabled: boolean;
  shadowEnabled: boolean;
  maxTrainsPerDay: number;
  minTrainIntervalMin: number;
}

// In-memory state for time-based locks
let promotionLockUntil: Date | null = null;

export class SentimentGuardsService {
  /**
   * Get current guard state from environment
   */
  getState(): SentimentGuardState {
    return {
      killSwitch: process.env.SENTIMENT_KILL_SWITCH === 'true',
      promotionLock: this.isPromotionLocked(),
      promotionLockUntil,
      retrainEnabled: process.env.SENTIMENT_RETRAIN_ENABLED !== 'false',
      shadowEnabled: process.env.SENTIMENT_SHADOW_ENABLED !== 'false',
      maxTrainsPerDay: Number(process.env.SENTIMENT_MAX_TRAIN_PER_DAY ?? 2),
      minTrainIntervalMin: Number(process.env.SENTIMENT_MIN_TRAIN_INTERVAL_MIN ?? 180),
    };
  }

  /**
   * Check if kill switch is active
   */
  isKillSwitchOn(): boolean {
    return process.env.SENTIMENT_KILL_SWITCH === 'true';
  }

  /**
   * Check if promotion is locked (env OR time-based)
   */
  isPromotionLocked(): boolean {
    // Check env-based lock
    if (process.env.SENTIMENT_PROMOTION_LOCK === 'true') {
      return true;
    }
    // Check time-based lock (S4)
    if (promotionLockUntil && promotionLockUntil.getTime() > Date.now()) {
      return true;
    }
    // Clear expired lock
    if (promotionLockUntil && promotionLockUntil.getTime() <= Date.now()) {
      promotionLockUntil = null;
    }
    return false;
  }

  /**
   * Set time-based promotion lock (S4: after capital rollback)
   */
  setPromotionLockUntil(until: Date): void {
    promotionLockUntil = until;
    console.log(`[Guards] Promotion locked until ${until.toISOString()}`);
  }

  /**
   * Clear time-based promotion lock
   */
  clearPromotionLock(): void {
    promotionLockUntil = null;
    console.log('[Guards] Promotion lock cleared');
  }

  /**
   * Get promotion lock expiry (for admin view)
   */
  getPromotionLockExpiry(): Date | null {
    if (promotionLockUntil && promotionLockUntil.getTime() > Date.now()) {
      return promotionLockUntil;
    }
    return null;
  }

  /**
   * Check if retraining is allowed
   */
  canRetrain(): boolean {
    return process.env.SENTIMENT_RETRAIN_ENABLED !== 'false';
  }

  /**
   * Check if shadow recording is enabled
   */
  isShadowEnabled(): boolean {
    return process.env.SENTIMENT_SHADOW_ENABLED !== 'false';
  }
}

// Singleton
let guardsInstance: SentimentGuardsService | null = null;

export function getSentimentGuardsService(): SentimentGuardsService {
  if (!guardsInstance) {
    guardsInstance = new SentimentGuardsService();
  }
  return guardsInstance;
}

console.log('[Sentiment-ML] Guards Service loaded (BLOCK 5 Lifecycle)');
