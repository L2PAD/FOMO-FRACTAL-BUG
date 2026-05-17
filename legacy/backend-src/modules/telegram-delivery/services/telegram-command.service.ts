/**
 * Telegram Command Service
 *
 * Handles prediction-specific bot commands:
 * /predictions, /high_only, /digest_on, /digest_off,
 * /weekly_on, /weekly_off, /mute_1h, /pred_status
 */

import { telegramPreferencesService } from './telegram-preferences.service.js';
import { telegramBotService } from './telegram-bot.service.js';

class TelegramCommandService {
  /**
   * Process a prediction command from a Telegram update.
   */
  async handleCommand(chatId: string, command: string): Promise<void> {
    const cmd = command.trim().toLowerCase().split(' ')[0];

    switch (cmd) {
      case '/predictions':
      case '/pred_start':
        await this.handleStart(chatId);
        break;
      case '/pred_off':
      case '/predictions_off':
        await this.handleOff(chatId);
        break;
      case '/pred_on':
      case '/predictions_on':
        await this.handleOn(chatId);
        break;
      case '/high_only':
        await this.handleHighOnly(chatId);
        break;
      case '/high_off':
        await this.handleHighOff(chatId);
        break;
      case '/digest_on':
        await this.handleDigestOn(chatId);
        break;
      case '/digest_off':
        await this.handleDigestOff(chatId);
        break;
      case '/weekly_on':
        await this.handleWeeklyOn(chatId);
        break;
      case '/weekly_off':
        await this.handleWeeklyOff(chatId);
        break;
      case '/mute_1h':
        await this.handleMute(chatId, 1);
        break;
      case '/mute_4h':
        await this.handleMute(chatId, 4);
        break;
      case '/unmute':
        await this.handleUnmute(chatId);
        break;
      case '/pred_status':
        await this.handleStatus(chatId);
        break;
      default:
        // Not a prediction command
        break;
    }
  }

  private async handleStart(chatId: string): Promise<void> {
    const prefs = await telegramPreferencesService.getOrCreate(chatId);
    await telegramBotService.sendMessage(chatId,
      `<b>Prediction Alerts — Active</b>\n\n` +
      `Instant HIGH alerts: ${prefs.instantHighAlerts ? 'ON' : 'OFF'}\n` +
      `30m batch digest: ${prefs.batchDigest30m ? 'ON' : 'OFF'}\n` +
      `Weekly digest: ${prefs.weeklyDigest ? 'ON' : 'OFF'}\n` +
      `High only: ${prefs.highOnly ? 'ON' : 'OFF'}\n\n` +
      `<b>Commands:</b>\n` +
      `/pred_status — current settings\n` +
      `/high_only — only HIGH priority\n` +
      `/high_off — all priorities\n` +
      `/digest_on /digest_off — 30m digest\n` +
      `/weekly_on /weekly_off — weekly report\n` +
      `/mute_1h /mute_4h /unmute\n` +
      `/pred_off — disable all`,
      { parseMode: 'HTML' },
    );
  }

  private async handleOff(chatId: string): Promise<void> {
    await telegramPreferencesService.updatePrefs(chatId, { enabled: false });
    await telegramBotService.sendMessage(chatId,
      '<b>Prediction alerts disabled.</b>\n\nUse /pred_on to re-enable.',
      { parseMode: 'HTML' },
    );
  }

  private async handleOn(chatId: string): Promise<void> {
    await telegramPreferencesService.updatePrefs(chatId, { enabled: true });
    await telegramBotService.sendMessage(chatId,
      '<b>Prediction alerts enabled.</b>',
      { parseMode: 'HTML' },
    );
  }

  private async handleHighOnly(chatId: string): Promise<void> {
    await telegramPreferencesService.updatePrefs(chatId, { highOnly: true });
    await telegramBotService.sendMessage(chatId,
      '<b>High-only mode ON.</b>\nOnly HIGH priority alerts will be sent instantly.\nMEDIUM alerts go to 30m digest.',
      { parseMode: 'HTML' },
    );
  }

  private async handleHighOff(chatId: string): Promise<void> {
    await telegramPreferencesService.updatePrefs(chatId, { highOnly: false });
    await telegramBotService.sendMessage(chatId,
      '<b>High-only mode OFF.</b>\nAll priority levels will be sent.',
      { parseMode: 'HTML' },
    );
  }

  private async handleDigestOn(chatId: string): Promise<void> {
    await telegramPreferencesService.updatePrefs(chatId, { batchDigest30m: true });
    await telegramBotService.sendMessage(chatId, '<b>30m batch digest: ON</b>', { parseMode: 'HTML' });
  }

  private async handleDigestOff(chatId: string): Promise<void> {
    await telegramPreferencesService.updatePrefs(chatId, { batchDigest30m: false });
    await telegramBotService.sendMessage(chatId, '<b>30m batch digest: OFF</b>', { parseMode: 'HTML' });
  }

  private async handleWeeklyOn(chatId: string): Promise<void> {
    await telegramPreferencesService.updatePrefs(chatId, { weeklyDigest: true });
    await telegramBotService.sendMessage(chatId, '<b>Weekly digest: ON</b>', { parseMode: 'HTML' });
  }

  private async handleWeeklyOff(chatId: string): Promise<void> {
    await telegramPreferencesService.updatePrefs(chatId, { weeklyDigest: false });
    await telegramBotService.sendMessage(chatId, '<b>Weekly digest: OFF</b>', { parseMode: 'HTML' });
  }

  private async handleMute(chatId: string, hours: number): Promise<void> {
    const until = Date.now() + hours * 3600 * 1000;
    await telegramPreferencesService.updatePrefs(chatId, { muteUntil: until });
    await telegramBotService.sendMessage(chatId,
      `<b>Muted for ${hours}h.</b>\nUse /unmute to unmute.`,
      { parseMode: 'HTML' },
    );
  }

  private async handleUnmute(chatId: string): Promise<void> {
    await telegramPreferencesService.updatePrefs(chatId, { muteUntil: null });
    await telegramBotService.sendMessage(chatId, '<b>Unmuted.</b>', { parseMode: 'HTML' });
  }

  private async handleStatus(chatId: string): Promise<void> {
    const prefs = await telegramPreferencesService.getPrefs(chatId);
    if (!prefs) {
      await telegramBotService.sendMessage(chatId,
        'Not registered. Use /predictions to start.',
        { parseMode: 'HTML' },
      );
      return;
    }

    const muted = prefs.muteUntil && Date.now() < prefs.muteUntil;
    const muteInfo = muted
      ? `MUTED until ${new Date(prefs.muteUntil!).toLocaleTimeString()}`
      : 'Not muted';

    await telegramBotService.sendMessage(chatId,
      `<b>Prediction Alert Settings</b>\n\n` +
      `Status: ${prefs.enabled ? 'ACTIVE' : 'DISABLED'}\n` +
      `Instant HIGH: ${prefs.instantHighAlerts ? 'ON' : 'OFF'}\n` +
      `30m digest: ${prefs.batchDigest30m ? 'ON' : 'OFF'}\n` +
      `Weekly: ${prefs.weeklyDigest ? 'ON' : 'OFF'}\n` +
      `High only: ${prefs.highOnly ? 'ON' : 'OFF'}\n` +
      `Mute: ${muteInfo}\n` +
      `Max/hour: ${prefs.maxMessagesPerHour}`,
      { parseMode: 'HTML' },
    );
  }
}

export const telegramCommandService = new TelegramCommandService();
