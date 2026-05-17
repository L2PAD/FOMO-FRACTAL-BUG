/**
 * Telegram Delivery Orchestrator
 *
 * Main entry point for all prediction Telegram delivery.
 * Coordinates: preferences → mute → cooldown → rate limit → format → send → log.
 *
 * Also manages the 30m batch queue and scheduled weekly digest.
 */

import { MongoClient } from 'mongodb';
import { telegramBotService } from './telegram-bot.service.js';
import { telegramPreferencesService } from './telegram-preferences.service.js';
import { telegramCooldownService } from './telegram-cooldown.service.js';
import { telegramFormatService } from './telegram-format.service.js';
import { telegramRouterService } from './telegram-router.service.js';
import type { TelegramPayload, DeliveryLogEntry, PredictionTelegramPrefs } from '../types/telegram.types.js';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'intelligence_engine';

// Batch queue: chatId → queued payloads
const batchQueue = new Map<string, TelegramPayload[]>();
let batchIntervalId: ReturnType<typeof setInterval> | null = null;

class TelegramDeliveryOrchestrator {
  /**
   * Deliver a prediction alert to all enabled subscribers.
   */
  async deliverAlert(payload: TelegramPayload): Promise<{ sent: number; suppressed: number }> {
    const allPrefs = await telegramPreferencesService.getAllEnabled();
    let sent = 0;
    let suppressed = 0;

    for (const prefs of allPrefs) {
      const result = await this.deliverToUser(prefs, payload);
      if (result) sent++;
      else suppressed++;
    }

    console.log(`[TG-Orchestrator] ${payload.type} delivered: ${sent} sent, ${suppressed} suppressed`);
    return { sent, suppressed };
  }

  /**
   * Deliver to a specific user (by chatId).
   */
  async deliverToChat(chatId: string, payload: TelegramPayload): Promise<boolean> {
    const prefs = await telegramPreferencesService.getOrCreate(chatId);
    return this.deliverToUser(prefs, payload);
  }

  /**
   * Core delivery logic for a single user.
   */
  private async deliverToUser(prefs: PredictionTelegramPrefs, payload: TelegramPayload): Promise<boolean> {
    // 1. Route decision
    const route = telegramRouterService.route(payload, prefs);

    if (route.decision === 'SUPPRESS') {
      return false;
    }

    if (route.decision === 'QUEUE_BATCH') {
      this.addToBatch(prefs.chatId, payload);
      return false; // Not sent yet — will be in batch
    }

    // 2. Cooldown check
    const dedupKey = payload.dedupKey || `${prefs.chatId}:${payload.type}:${payload.marketId || 'global'}`;
    if (!telegramCooldownService.canSend(prefs.chatId, payload.type, dedupKey)) {
      // EXIT always bypasses cooldown
      if (payload.type === 'EXIT_ALERT') {
        telegramCooldownService.bypass(prefs.chatId, payload.type, dedupKey);
      } else {
        return false;
      }
    }

    // 3. Rate limit
    if (!telegramCooldownService.checkRateLimit(prefs.chatId, prefs.maxMessagesPerHour)) {
      return false;
    }

    // 4. Format
    const text = telegramFormatService.format(payload.type, payload.meta || {
      ...payload,
    });

    // 5. Send
    const result = await telegramBotService.sendMessage(prefs.chatId, text, {
      parseMode: 'HTML',
      disableNotification: payload.priority === 'LOW',
    });

    // 6. Log + update cooldown
    if (result.ok) {
      telegramCooldownService.markSent(prefs.chatId, payload.type, dedupKey);
      telegramCooldownService.incrementCount(prefs.chatId);
    }

    await this.logDelivery({
      chatId: prefs.chatId,
      type: payload.type,
      priority: payload.priority,
      title: payload.title,
      dedupKey,
      sentAt: new Date().toISOString(),
      success: result.ok,
      error: result.error,
    });

    return result.ok;
  }

  /**
   * Add payload to 30m batch queue.
   */
  private addToBatch(chatId: string, payload: TelegramPayload): void {
    if (!batchQueue.has(chatId)) batchQueue.set(chatId, []);
    const queue = batchQueue.get(chatId)!;
    // Max 20 per batch
    if (queue.length < 20) {
      queue.push(payload);
    }
  }

  /**
   * Flush all batch queues — called every 30 minutes.
   */
  async flushBatches(): Promise<number> {
    let totalSent = 0;

    for (const [chatId, payloads] of batchQueue.entries()) {
      if (payloads.length === 0) continue;

      const prefs = await telegramPreferencesService.getPrefs(chatId);
      if (!prefs?.enabled || !prefs.batchDigest30m) continue;
      if (telegramPreferencesService.isMuted(prefs)) continue;

      // Build batch digest from queued items
      const opportunities = payloads
        .filter(p => p.type === 'ENTRY_ALERT')
        .map(p => ({
          asset: p.asset || p.meta?.asset || 'N/A',
          action: p.meta?.action || 'ENTRY',
          edge: p.meta?.edge || 0,
        }));

      const stateChanges = payloads.filter(p => p.meta?.isStateChange).length;
      const riskAlerts = payloads.filter(p => p.type === 'RISK_ALERT').length;

      const digestPayload: TelegramPayload = {
        type: 'BATCH_DIGEST',
        priority: 'MEDIUM',
        title: '30m Digest',
        body: '',
        meta: { opportunities, stateChanges, riskAlerts },
      };

      const text = telegramFormatService.format('BATCH_DIGEST', digestPayload.meta);
      const result = await telegramBotService.sendMessage(chatId, text, { parseMode: 'HTML' });

      if (result.ok) totalSent++;
    }

    batchQueue.clear();
    if (totalSent > 0) {
      console.log(`[TG-Orchestrator] Batch flush: ${totalSent} digests sent`);
    }
    return totalSent;
  }

  /**
   * Send weekly digest to all subscribers.
   */
  async deliverWeeklyDigest(digestData: any): Promise<number> {
    const allPrefs = await telegramPreferencesService.getAllEnabled();
    let sent = 0;

    for (const prefs of allPrefs) {
      if (!prefs.weeklyDigest) continue;
      if (telegramPreferencesService.isMuted(prefs)) continue;

      const text = telegramFormatService.format('WEEKLY_DIGEST', digestData);
      const result = await telegramBotService.sendMessage(prefs.chatId, text, { parseMode: 'HTML' });
      if (result.ok) sent++;
    }

    console.log(`[TG-Orchestrator] Weekly digest delivered to ${sent} subscribers`);
    return sent;
  }

  /**
   * Auto-register operator chatId from env (TG_USER_CHAT_ID) into prediction_telegram_prefs.
   * This ensures the operator receives prediction alerts without manual /connect.
   */
  async ensureOperatorRegistered(): Promise<void> {
    const operatorChatId = process.env.TG_USER_CHAT_ID;
    if (!operatorChatId) return;

    const existing = await telegramPreferencesService.getPrefs(operatorChatId);
    if (existing) {
      console.log(`[TG-Orchestrator] Operator chatId ${operatorChatId} already registered`);
      return;
    }

    await telegramPreferencesService.getOrCreate(operatorChatId);
    console.log(`[TG-Orchestrator] Auto-registered operator chatId ${operatorChatId} for prediction alerts`);
  }

  /**
   * Start the 30m batch flush interval.
   */
  startBatchScheduler(): void {
    if (batchIntervalId) return;

    // Auto-register operator on startup
    this.ensureOperatorRegistered().catch(err => {
      console.error('[TG-Orchestrator] Failed to auto-register operator:', err);
    });

    batchIntervalId = setInterval(() => {
      this.flushBatches().catch(err => {
        console.error('[TG-Orchestrator] Batch flush error:', err);
      });
    }, 30 * 60 * 1000); // 30 minutes
    console.log('[TG-Orchestrator] Batch scheduler started (30m interval)');
  }

  /**
   * Stop batch scheduler.
   */
  stopBatchScheduler(): void {
    if (batchIntervalId) {
      clearInterval(batchIntervalId);
      batchIntervalId = null;
    }
  }

  /**
   * Get delivery stats.
   */
  async getStats(): Promise<any> {
    const client = new MongoClient(MONGO_URL);
    try {
      await client.connect();
      const db = client.db(DB_NAME);
      const total = await db.collection('prediction_telegram_log').countDocuments();
      const last24h = await db.collection('prediction_telegram_log').countDocuments({
        sentAt: { $gte: new Date(Date.now() - 24 * 3600 * 1000).toISOString() },
      });
      const subscribers = await db.collection('prediction_telegram_prefs').countDocuments({ enabled: true });
      const batchQueueSize = [...batchQueue.values()].reduce((s, q) => s + q.length, 0);

      return { total, last24h, subscribers, batchQueueSize };
    } finally {
      await client.close();
    }
  }

  private async logDelivery(entry: DeliveryLogEntry): Promise<void> {
    try {
      const client = new MongoClient(MONGO_URL);
      await client.connect();
      await client.db(DB_NAME).collection('prediction_telegram_log').insertOne({ ...entry });
      await client.close();
    } catch {
      // Logging failure is not critical
    }
  }
}

export const telegramDeliveryOrchestrator = new TelegramDeliveryOrchestrator();
