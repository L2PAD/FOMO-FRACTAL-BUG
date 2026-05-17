/**
 * Dedup Engine
 *
 * Smart cooldown: key = marketId + state + action
 * Different states for same market can trigger again.
 * EXIT always goes through even if recently alerted.
 */

import type { AlertType, AlertTier } from '../types/alert.types.js';

interface CooldownEntry {
  timestamp: number;
  action: string;
  state: string;
  tier: AlertTier;
}

// Default cooldown windows (ms)
const COOLDOWN_MS: Record<AlertTier, number> = {
  HIGH: 30 * 60 * 1000,   // 30 min for HIGH
  MEDIUM: 45 * 60 * 1000, // 45 min for MEDIUM
  LOW: 60 * 60 * 1000,    // 60 min for LOW
};

class DedupEngineService {
  private cooldowns = new Map<string, CooldownEntry>();

  /**
   * Check if alert should be sent (not a duplicate).
   */
  shouldSend(
    marketId: string,
    action: string,
    state: string, // repricing state or exit action
    tier: AlertTier,
    alertType: AlertType,
  ): { send: boolean; reason: string } {
    // EXIT always goes through
    if (alertType === 'EXIT_SIGNAL') {
      return { send: true, reason: 'EXIT signals always deliver' };
    }

    // Build composite cooldown key: market + action + state
    const key = `${marketId}:${action}:${state}`;
    const now = Date.now();
    const existing = this.cooldowns.get(key);

    if (existing) {
      const elapsed = now - existing.timestamp;
      const window = COOLDOWN_MS[tier];

      if (elapsed < window) {
        const remaining = Math.round((window - elapsed) / 60000);
        return { send: false, reason: `Cooldown active (${remaining}min remaining for ${key})` };
      }
    }

    // Record this send
    this.cooldowns.set(key, { timestamp: now, action, state, tier });

    // Cleanup old entries (older than 2 hours)
    this.cleanup(now);

    return { send: true, reason: 'No active cooldown' };
  }

  private cleanup(now: number): void {
    const maxAge = 2 * 60 * 60 * 1000; // 2 hours
    for (const [key, entry] of this.cooldowns.entries()) {
      if (now - entry.timestamp > maxAge) {
        this.cooldowns.delete(key);
      }
    }
  }

  /** Get active cooldown count */
  getCooldownCount(): number {
    return this.cooldowns.size;
  }

  /** Clear all cooldowns (for testing) */
  clearAll(): void {
    this.cooldowns.clear();
  }
}

export const dedupEngineService = new DedupEngineService();
