/**
 * Telegram Delivery Routes
 *
 * API endpoints for managing prediction Telegram delivery:
 * - Connect/disconnect
 * - Preferences
 * - Test messages
 * - Status/stats
 * - Webhook for bot updates (commands)
 * - Manual alert/digest triggers
 */

import type { FastifyInstance } from 'fastify';
import { telegramDeliveryOrchestrator } from './services/telegram-delivery-orchestrator.service.js';
import { telegramPreferencesService } from './services/telegram-preferences.service.js';
import { telegramCommandService } from './services/telegram-command.service.js';
import { telegramBotService } from './services/telegram-bot.service.js';
import type { TelegramPayload } from './types/telegram.types.js';

export function registerTelegramDeliveryRoutes(app: FastifyInstance) {
  // Register chatId for prediction alerts
  app.post('/api/telegram-delivery/connect', async (req) => {
    const { chatId } = req.body as { chatId: string };
    if (!chatId) return { ok: false, error: 'chatId required' };

    const prefs = await telegramPreferencesService.getOrCreate(chatId);

    // Send welcome message
    await telegramBotService.sendMessage(chatId,
      '<b>Prediction Alerts Connected!</b>\n\nYou will receive HIGH priority trading alerts, 30m digests, and weekly reports.\n\nUse /predictions to manage settings.',
      { parseMode: 'HTML' },
    );

    return { ok: true, prefs };
  });

  // Get preferences for a chatId
  app.get('/api/telegram-delivery/preferences/:chatId', async (req) => {
    const { chatId } = req.params as { chatId: string };
    const prefs = await telegramPreferencesService.getPrefs(chatId);
    return { ok: true, prefs };
  });

  // Update preferences
  app.post('/api/telegram-delivery/preferences', async (req) => {
    const { chatId, ...updates } = req.body as any;
    if (!chatId) return { ok: false, error: 'chatId required' };

    const prefs = await telegramPreferencesService.updatePrefs(chatId, updates);
    return { ok: true, prefs };
  });

  // Disconnect (disable)
  app.post('/api/telegram-delivery/disconnect', async (req) => {
    const { chatId } = req.body as { chatId: string };
    if (!chatId) return { ok: false, error: 'chatId required' };

    await telegramPreferencesService.updatePrefs(chatId, { enabled: false });
    return { ok: true, message: 'Disconnected' };
  });

  // Send test alert
  app.post('/api/telegram-delivery/test', async (req) => {
    const { chatId, type } = req.body as { chatId: string; type?: string };
    if (!chatId) return { ok: false, error: 'chatId required' };

    const testPayload: TelegramPayload = {
      type: (type as any) || 'ENTRY_ALERT',
      priority: 'HIGH',
      title: 'Test Alert',
      body: 'This is a test prediction alert.',
      asset: 'BTC',
      marketId: 'test',
      meta: {
        asset: 'BTC',
        question: 'Will BTC reach 100k?',
        action: 'YES_NOW',
        edge: 0.11,
        confidence: 0.68,
        conviction: 'HIGH',
        entryStyle: 'ENTER_MARKET',
        reasons: ['Strong ETF narrative', 'Early repricing phase', 'Market not fully priced'],
        risks: ['Volatility elevated', 'Already +6% move'],
        urgency: 'HIGH URGENCY (early phase)',
      },
    };

    const result = await telegramDeliveryOrchestrator.deliverToChat(chatId, testPayload);
    return { ok: result, message: result ? 'Test alert sent' : 'Delivery failed or suppressed' };
  });

  // Get delivery stats
  app.get('/api/telegram-delivery/stats', async () => {
    const stats = await telegramDeliveryOrchestrator.getStats();
    return { ok: true, stats };
  });

  // Deliver an alert to all subscribers (called by alert engine)
  app.post('/api/telegram-delivery/deliver', async (req) => {
    const payload = req.body as TelegramPayload;
    if (!payload.type) return { ok: false, error: 'type required' };

    const result = await telegramDeliveryOrchestrator.deliverAlert(payload);
    return { ok: true, ...result };
  });

  // Deliver weekly digest to all subscribers
  app.post('/api/telegram-delivery/deliver-weekly', async (req) => {
    const digestData = req.body as any;
    const sent = await telegramDeliveryOrchestrator.deliverWeeklyDigest(digestData);
    return { ok: true, sent };
  });

  // Flush batch queue manually
  app.post('/api/telegram-delivery/flush-batch', async () => {
    const sent = await telegramDeliveryOrchestrator.flushBatches();
    return { ok: true, sent };
  });

  // Webhook for bot updates (prediction commands)
  app.post('/api/telegram-delivery/webhook', async (req) => {
    const update = req.body as any;
    const message = update?.message;
    if (!message?.text || !message?.chat?.id) return { ok: true };

    const chatId = String(message.chat.id);
    const text = message.text.trim();

    if (text.startsWith('/')) {
      await telegramCommandService.handleCommand(chatId, text);
    }

    return { ok: true };
  });

  // Get all subscribers
  app.get('/api/telegram-delivery/subscribers', async () => {
    const subs = await telegramPreferencesService.getAllEnabled();
    return { ok: true, count: subs.length, subscribers: subs };
  });

  // Start batch scheduler
  telegramDeliveryOrchestrator.startBatchScheduler();

  app.log.info('[Telegram Delivery] Routes registered at /api/telegram-delivery/*');
}
