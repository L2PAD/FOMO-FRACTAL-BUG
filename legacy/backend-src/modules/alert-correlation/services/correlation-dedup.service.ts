/**
 * Correlation Dedup Service
 *
 * Prevents meta-alert spam. Cooldown per type + dominant factor + regime direction.
 */

const dedupCache = new Map<string, number>();

const COOLDOWN_MS: Record<string, number> = {
  SECTOR_ROTATION: 60 * 60 * 1000,       // 1 hour
  MULTI_MARKET_CONFIRMATION: 45 * 60 * 1000,
  UNLOCK_RISK_CLUSTER: 2 * 60 * 60 * 1000, // 2 hours
  RISK_ON_SHIFT: 90 * 60 * 1000,           // 1.5 hours
  RISK_OFF_SHIFT: 90 * 60 * 1000,
  NARRATIVE_EXHAUSTION: 2 * 60 * 60 * 1000,
  BROAD_OVERHEAT: 2 * 60 * 60 * 1000,
  CLUSTER_WAKEUP: 60 * 60 * 1000,
  MIXED_CLUSTER: 30 * 60 * 1000,
};

class CorrelationDedupService {
  /**
   * Check if a meta-alert can be emitted (not in cooldown).
   */
  canEmit(dedupKey: string, type: string): boolean {
    const last = dedupCache.get(dedupKey);
    if (!last) return true;

    const cooldown = COOLDOWN_MS[type] || 60 * 60 * 1000;
    return Date.now() - last >= cooldown;
  }

  /**
   * Allow re-emission if confidence/priority materially increased.
   */
  canReEmit(dedupKey: string, type: string, newConfidence: number): boolean {
    if (this.canEmit(dedupKey, type)) return true;
    // Allow if confidence jumped significantly (re-emit on escalation)
    return newConfidence > 0.8;
  }

  /**
   * Mark meta-alert as emitted.
   */
  markEmitted(dedupKey: string): void {
    dedupCache.set(dedupKey, Date.now());

    // Cleanup
    if (dedupCache.size > 500) {
      const now = Date.now();
      const maxCooldown = Math.max(...Object.values(COOLDOWN_MS));
      for (const [key, ts] of dedupCache.entries()) {
        if (now - ts > maxCooldown) dedupCache.delete(key);
      }
    }
  }

  clear(): void {
    dedupCache.clear();
  }
}

export const correlationDedupService = new CorrelationDedupService();
