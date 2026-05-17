/**
 * Telegram Bot Service
 *
 * Low-level Telegram API sender with retries and rate-limit awareness.
 * Uses the user bot (@FOMOcx_bot) for prediction alerts.
 */

import type { TelegramSendResult } from '../types/telegram.types.js';

const USER_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const SYSTEM_BOT_TOKEN = process.env.SYSTEM_TELEGRAM_BOT_TOKEN || '';
const API_BASE = 'https://api.telegram.org/bot';

class TelegramBotService {
  private userEnabled: boolean;
  private systemEnabled: boolean;

  constructor() {
    this.userEnabled = !!USER_BOT_TOKEN;
    this.systemEnabled = !!SYSTEM_BOT_TOKEN;
    console.log(`[TG-Delivery] User bot: ${this.userEnabled ? 'ENABLED' : 'DISABLED'}`);
    console.log(`[TG-Delivery] System bot: ${this.systemEnabled ? 'ENABLED' : 'DISABLED'}`);
  }

  async sendMessage(chatId: string, text: string, options?: {
    parseMode?: 'HTML' | 'Markdown';
    disableNotification?: boolean;
    isSystem?: boolean;
  }): Promise<TelegramSendResult> {
    const token = options?.isSystem ? SYSTEM_BOT_TOKEN : USER_BOT_TOKEN;
    const enabled = options?.isSystem ? this.systemEnabled : this.userEnabled;

    if (!enabled) {
      console.log(`[TG-Delivery] Would send (disabled): ${text.slice(0, 60)}...`);
      return { ok: false, error: 'Bot not configured' };
    }

    const url = `${API_BASE}${token}/sendMessage`;

    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: chatId,
            text,
            parse_mode: options?.parseMode || 'HTML',
            disable_notification: options?.disableNotification || false,
          }),
          signal: AbortSignal.timeout(10000),
        });

        const data: any = await res.json();

        if (data.ok) {
          return { ok: true, messageId: data.result?.message_id };
        }

        // Rate limited — wait and retry
        if (data.error_code === 429) {
          const wait = (data.parameters?.retry_after || 5) * 1000;
          console.warn(`[TG-Delivery] Rate limited, waiting ${wait}ms`);
          await new Promise(r => setTimeout(r, wait));
          continue;
        }

        return { ok: false, error: data.description || 'API error' };
      } catch (err: any) {
        if (attempt < 2) {
          await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
          continue;
        }
        return { ok: false, error: err.message };
      }
    }

    return { ok: false, error: 'Max retries exceeded' };
  }

  get isUserBotEnabled() { return this.userEnabled; }
  get isSystemBotEnabled() { return this.systemEnabled; }
}

export const telegramBotService = new TelegramBotService();
