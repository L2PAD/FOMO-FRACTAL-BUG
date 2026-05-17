/**
 * Telegram Delivery Types
 */

export type PredictionAlertType =
  | 'ENTRY_ALERT'
  | 'EXIT_ALERT'
  | 'RISK_ALERT'
  | 'BATCH_DIGEST'
  | 'WEEKLY_DIGEST'
  | 'SYSTEM_MESSAGE';

export type AlertPriority = 'HIGH' | 'MEDIUM' | 'LOW';

export interface TelegramPayload {
  type: PredictionAlertType;
  priority: AlertPriority;
  title: string;
  body: string;
  marketId?: string;
  asset?: string;
  dedupKey?: string;
  meta?: Record<string, any>;
}

export interface PredictionTelegramPrefs {
  chatId: string;
  enabled: boolean;
  instantHighAlerts: boolean;
  batchDigest30m: boolean;
  weeklyDigest: boolean;
  highOnly: boolean;
  muteUntil: number | null;
  maxMessagesPerHour: number;
  createdAt: string;
  updatedAt: string;
}

export interface TelegramSendResult {
  ok: boolean;
  error?: string;
  messageId?: number;
}

export interface DeliveryLogEntry {
  chatId: string;
  type: PredictionAlertType;
  priority: AlertPriority;
  title: string;
  dedupKey: string;
  sentAt: string;
  success: boolean;
  error?: string;
}
