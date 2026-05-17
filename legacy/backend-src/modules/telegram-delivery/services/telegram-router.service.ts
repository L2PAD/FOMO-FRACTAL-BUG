/**
 * Telegram Router Service
 *
 * Decides what to send and how based on alert priority + user preferences.
 * HIGH → instant, MEDIUM → queue for batch, LOW → suppress.
 */

import type { TelegramPayload, PredictionTelegramPrefs } from '../types/telegram.types.js';

export type RouteDecision = 'SEND_NOW' | 'QUEUE_BATCH' | 'SUPPRESS';

export interface RouteResult {
  decision: RouteDecision;
  reason: string;
}

class TelegramRouterService {
  route(payload: TelegramPayload, prefs: PredictionTelegramPrefs): RouteResult {
    // 1. Not enabled
    if (!prefs.enabled) {
      return { decision: 'SUPPRESS', reason: 'DISABLED' };
    }

    // 2. Muted
    if (prefs.muteUntil && Date.now() < prefs.muteUntil) {
      return { decision: 'SUPPRESS', reason: 'MUTED' };
    }

    // 3. Route by type
    switch (payload.type) {
      case 'ENTRY_ALERT':
      case 'EXIT_ALERT':
      case 'RISK_ALERT':
        return this.routeInstant(payload, prefs);

      case 'BATCH_DIGEST':
        if (!prefs.batchDigest30m) {
          return { decision: 'SUPPRESS', reason: 'BATCH_DISABLED' };
        }
        return { decision: 'SEND_NOW', reason: 'BATCH_ENABLED' };

      case 'WEEKLY_DIGEST':
        if (!prefs.weeklyDigest) {
          return { decision: 'SUPPRESS', reason: 'WEEKLY_DISABLED' };
        }
        return { decision: 'SEND_NOW', reason: 'WEEKLY_ENABLED' };

      case 'SYSTEM_MESSAGE':
        return { decision: 'SEND_NOW', reason: 'SYSTEM' };

      default:
        return { decision: 'SUPPRESS', reason: 'UNKNOWN_TYPE' };
    }
  }

  private routeInstant(payload: TelegramPayload, prefs: PredictionTelegramPrefs): RouteResult {
    if (!prefs.instantHighAlerts) {
      return { decision: 'SUPPRESS', reason: 'INSTANT_DISABLED' };
    }

    // High only mode — suppress MEDIUM and LOW
    if (prefs.highOnly && payload.priority !== 'HIGH') {
      return { decision: 'QUEUE_BATCH', reason: 'HIGH_ONLY_BATCH' };
    }

    // HIGH → send immediately
    if (payload.priority === 'HIGH') {
      return { decision: 'SEND_NOW', reason: 'HIGH_PRIORITY' };
    }

    // MEDIUM → queue for batch
    if (payload.priority === 'MEDIUM') {
      return { decision: 'QUEUE_BATCH', reason: 'MEDIUM_BATCH' };
    }

    // LOW → suppress from Telegram entirely
    return { decision: 'SUPPRESS', reason: 'LOW_PRIORITY' };
  }
}

export const telegramRouterService = new TelegramRouterService();
