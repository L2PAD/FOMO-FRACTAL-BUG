/**
 * Delivery Service — WebSocket + Telegram
 *
 * Pushes alerts to connected clients via WebSocket and
 * routes to Telegram delivery for high-priority alerts.
 */

import { wsServer } from '../../../ws/ws.server.js';
import { telegramDeliveryOrchestrator } from '../../telegram-delivery/services/telegram-delivery-orchestrator.service.js';
import type { AlertPayload, DigestPayload } from '../types/alert.types.js';
import type { TelegramPayload } from '../../telegram-delivery/types/telegram.types.js';

class DeliveryService {
  /**
   * Send a real-time alert to all subscribed clients + Telegram.
   */
  sendRealtime(alert: AlertPayload): void {
    wsServer.broadcast('alerts', 'alert:realtime', alert);
    console.log(`[AlertEngine] Realtime alert sent: ${alert.type} ${alert.tier} — ${alert.asset} ${alert.action}`);

    // Route to Telegram
    this.routeToTelegram(alert).catch(() => {});
  }

  /**
   * Send a batch digest to all subscribed clients + Telegram batch.
   */
  sendBatchDigest(digest: DigestPayload): void {
    wsServer.broadcast('alerts', 'alert:digest', digest);
    console.log(`[AlertEngine] Batch digest sent: ${digest.summary.total} alerts (${digest.summary.high}H/${digest.summary.medium}M/${digest.summary.low}L)`);
  }

  /**
   * Send to all connected clients (global broadcast, no subscription needed).
   */
  broadcastHighPriority(alert: AlertPayload): void {
    wsServer.broadcastAll('alert:urgent', alert);
    console.log(`[AlertEngine] URGENT broadcast: ${alert.type} ${alert.tier} — ${alert.asset} ${alert.action}`);

    // Always route urgent to Telegram
    this.routeToTelegram(alert).catch(() => {});
  }

  /**
   * Get connected client count.
   */
  getClientCount(): number {
    return wsServer.getClientCount();
  }

  /**
   * Route an alert to Telegram delivery.
   */
  private async routeToTelegram(alert: AlertPayload): Promise<void> {
    try {
      const tgType = this.mapAlertType(alert.type, alert.action);
      const tgPriority = this.mapTier(alert.tier);

      const payload: TelegramPayload = {
        type: tgType,
        priority: tgPriority,
        title: `${alert.asset} — ${alert.action}`,
        body: alert.reasoning || '',
        asset: alert.asset,
        marketId: alert.marketId,
        dedupKey: `${alert.marketId}:${alert.type}:${alert.action}`,
        meta: {
          asset: alert.asset,
          question: alert.question || '',
          action: alert.action,
          edge: alert.edge,
          confidence: alert.confidence,
          conviction: alert.conviction || 'MEDIUM',
          entryStyle: alert.entryStyle || 'ENTER_MARKET',
          reasons: alert.reasons || [],
          risks: alert.risks || [],
          urgency: tgPriority === 'HIGH' ? 'HIGH URGENCY' : 'STANDARD',
        },
      };

      await telegramDeliveryOrchestrator.deliverAlert(payload);
    } catch (err) {
      console.error('[AlertEngine] Telegram delivery error:', err);
    }
  }

  private mapAlertType(type: string, action?: string): TelegramPayload['type'] {
    if (type === 'RISK' || type === 'RISK_ALERT') return 'RISK_ALERT';
    if (action === 'EXIT' || action === 'SELL') return 'EXIT_ALERT';
    return 'ENTRY_ALERT';
  }

  private mapTier(tier: string): TelegramPayload['priority'] {
    if (tier === 'HIGH' || tier === 'CRITICAL') return 'HIGH';
    if (tier === 'MEDIUM') return 'MEDIUM';
    return 'LOW';
  }
}

export const deliveryService = new DeliveryService();
