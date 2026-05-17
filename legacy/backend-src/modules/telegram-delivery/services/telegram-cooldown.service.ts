/**
 * Telegram Cooldown Service
 *
 * Delivery-level cooldown (separate from alert engine cooldown).
 * Prevents spam to Telegram even when alert engine produces multiple alerts.
 *
 * Key: chatId + marketId + action + state
 */

const cooldownCache = new Map<string, number>();
const messageCountCache = new Map<string, { count: number; windowStart: number }>();

const COOLDOWN_TTL: Record<string, number> = {
  ENTRY_ALERT: 30 * 60 * 1000,   // 30 min between same entry alerts
  EXIT_ALERT: 5 * 60 * 1000,     // 5 min — exits are urgent
  RISK_ALERT: 15 * 60 * 1000,    // 15 min
  BATCH_DIGEST: 25 * 60 * 1000,  // 25 min (batch is 30m)
  WEEKLY_DIGEST: 6 * 3600 * 1000, // 6 hours
  SYSTEM_MESSAGE: 60 * 1000,      // 1 min
};

class TelegramCooldownService {
  /**
   * Check if this message can be sent (not in cooldown).
   */
  canSend(chatId: string, type: string, dedupKey?: string): boolean {
    const key = dedupKey || `${chatId}:${type}`;
    const last = cooldownCache.get(key);
    if (!last) return true;

    const ttl = COOLDOWN_TTL[type] || 10 * 60 * 1000;
    return Date.now() - last >= ttl;
  }

  /**
   * Mark message as sent (start cooldown).
   */
  markSent(chatId: string, type: string, dedupKey?: string): void {
    const key = dedupKey || `${chatId}:${type}`;
    cooldownCache.set(key, Date.now());

    // Cleanup if cache gets big
    if (cooldownCache.size > 2000) {
      this.cleanup();
    }
  }

  /**
   * Check per-hour rate limit.
   */
  checkRateLimit(chatId: string, maxPerHour: number): boolean {
    const now = Date.now();
    const hourMs = 3600 * 1000;
    const entry = messageCountCache.get(chatId);

    if (!entry || now - entry.windowStart > hourMs) {
      messageCountCache.set(chatId, { count: 0, windowStart: now });
      return true;
    }

    return entry.count < maxPerHour;
  }

  /**
   * Increment rate counter.
   */
  incrementCount(chatId: string): void {
    const entry = messageCountCache.get(chatId);
    if (entry) {
      entry.count++;
    } else {
      messageCountCache.set(chatId, { count: 1, windowStart: Date.now() });
    }
  }

  /**
   * Force bypass cooldown (for EXIT/RISK escalation).
   */
  bypass(chatId: string, type: string, dedupKey?: string): void {
    const key = dedupKey || `${chatId}:${type}`;
    cooldownCache.delete(key);
  }

  private cleanup(): void {
    const now = Date.now();
    const maxTtl = Math.max(...Object.values(COOLDOWN_TTL));
    for (const [key, ts] of cooldownCache.entries()) {
      if (now - ts > maxTtl) cooldownCache.delete(key);
    }
  }
}

export const telegramCooldownService = new TelegramCooldownService();
