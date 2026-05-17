/**
 * Feature Flag Lock Service
 * ===========================
 * 
 * F6: Lock/unlock admin mutations with TTL support.
 * 
 * Usage:
 * - Lock before maintenance/freeze
 * - Auto-unlock when TTL expires
 * - All changes logged to Evidence Store
 */

import { FeatureFlagLockModel, FeatureFlagLockDoc } from './feature-flag-lock.model.js';
import { getEvidenceWriterService } from './evidence-writer.service.js';

export type LockStatus =
  | { locked: false }
  | { locked: true; unlockAt: Date; reason: string; lockedBy: string; remainingMinutes: number };

export interface LockInput {
  reason: string;
  lockedBy?: string;
  ttlHours: number;
  metadata?: Record<string, any>;
}

export class FeatureFlagLockService {
  /**
   * Get current lock status for a module
   */
  async getStatus(moduleKey: string, scope: string = 'admin-write'): Promise<LockStatus> {
    const doc = await FeatureFlagLockModel.findOne({
      moduleKey,
      scope,
      isActive: true,
    }).lean();

    if (!doc) {
      return { locked: false };
    }

    const now = Date.now();
    const unlockAt = new Date(doc.unlockAt).getTime();

    // TTL expired → auto unlock
    if (unlockAt <= now) {
      await this.autoUnlock(moduleKey, scope);
      return { locked: false };
    }

    const remainingMinutes = Math.round((unlockAt - now) / 60000);

    return {
      locked: true,
      unlockAt: new Date(doc.unlockAt),
      reason: doc.reason,
      lockedBy: doc.lockedBy,
      remainingMinutes,
    };
  }

  /**
   * Set lock with TTL
   */
  async lock(moduleKey: string, input: LockInput, scope: string = 'admin-write'): Promise<FeatureFlagLockDoc> {
    const evidence = getEvidenceWriterService();
    const unlockAt = new Date(Date.now() + input.ttlHours * 3600_000);

    const doc = await FeatureFlagLockModel.findOneAndUpdate(
      { moduleKey, scope },
      {
        $set: {
          isActive: true,
          reason: input.reason,
          lockedBy: input.lockedBy || 'admin',
          lockedAt: new Date(),
          unlockAt,
          metadata: input.metadata || {},
        },
      },
      { upsert: true, new: true }
    ).lean();

    await evidence.append(
      moduleKey as any,
      'feature_lock_changed',
      'INFO',
      `Feature lock SET for ${moduleKey}:${scope} until ${unlockAt.toISOString()}`,
      { manifestVersion: '1.0.0' },
      { action: 'LOCK', reason: input.reason, ttlHours: input.ttlHours, unlockAt }
    );

    console.log(`[FeatureLock] Locked ${moduleKey}:${scope} until ${unlockAt.toISOString()}`);

    return doc as FeatureFlagLockDoc;
  }

  /**
   * Manual unlock
   */
  async unlock(moduleKey: string, reason: string, scope: string = 'admin-write'): Promise<boolean> {
    const evidence = getEvidenceWriterService();

    const result = await FeatureFlagLockModel.findOneAndUpdate(
      { moduleKey, scope, isActive: true },
      { $set: { isActive: false } },
      { new: true }
    );

    if (!result) {
      return false;
    }

    await evidence.append(
      moduleKey as any,
      'feature_lock_changed',
      'INFO',
      `Feature lock REMOVED for ${moduleKey}:${scope}`,
      {},
      { action: 'UNLOCK', reason }
    );

    console.log(`[FeatureLock] Unlocked ${moduleKey}:${scope}`);

    return true;
  }

  /**
   * Auto-unlock when TTL expires
   */
  private async autoUnlock(moduleKey: string, scope: string): Promise<void> {
    const evidence = getEvidenceWriterService();

    await FeatureFlagLockModel.updateOne(
      { moduleKey, scope, isActive: true },
      { $set: { isActive: false } }
    );

    await evidence.append(
      moduleKey as any,
      'feature_lock_changed',
      'INFO',
      `Feature lock AUTO-EXPIRED for ${moduleKey}:${scope}`,
      {},
      { action: 'AUTO_UNLOCK', reason: 'ttl-expired' }
    );

    console.log(`[FeatureLock] Auto-unlocked ${moduleKey}:${scope} (TTL expired)`);
  }

  /**
   * Assert module is unlocked (for guards)
   * Throws 423 if locked
   */
  async assertUnlocked(moduleKey: string, scope: string = 'admin-write'): Promise<void> {
    const status = await this.getStatus(moduleKey, scope);

    if (status.locked) {
      const error: any = new Error(`FEATURE_FLAGS_LOCKED: ${status.reason}`);
      error.statusCode = 423;
      error.code = 'FEATURE_FLAGS_LOCKED';
      error.details = status;
      throw error;
    }
  }

  /**
   * Check if any module has active lock
   */
  async listActiveLocks(): Promise<Array<{ moduleKey: string; scope: string; reason: string; unlockAt: Date }>> {
    const docs = await FeatureFlagLockModel.find({
      isActive: true,
      unlockAt: { $gt: new Date() },
    }).lean();

    return docs.map(d => ({
      moduleKey: d.moduleKey,
      scope: d.scope,
      reason: d.reason,
      unlockAt: d.unlockAt,
    }));
  }
}

// Singleton
let lockServiceInstance: FeatureFlagLockService | null = null;

export function getFeatureFlagLockService(): FeatureFlagLockService {
  if (!lockServiceInstance) {
    lockServiceInstance = new FeatureFlagLockService();
  }
  return lockServiceInstance;
}

console.log('[Shared] Feature Flag Lock Service loaded (F6)');
