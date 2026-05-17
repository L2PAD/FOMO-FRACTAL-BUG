/**
 * Polymarket Emitter
 * ==================
 * Bridge: prediction_alerts (MongoDB) → pushRouter.
 *
 * Polymarket signals are MARKET-FIRST — no asset-centric CTA. Each alert_type
 * gets its own copy module (no generic switch). Includes source-specific dedupe:
 * dedupeKey = marketId + alertType + 10-minute window.
 */

import { pushRouter } from '../push-router.service.js';
import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

import { buildPolymarketMispricingMessage } from '../builders/polymarket-mispricing.builder.js';
import { buildPolymarketRepricingMessage } from '../builders/polymarket-repricing.builder.js';
import { buildPolymarketOverheatedMessage } from '../builders/polymarket-overheated.builder.js';
import { buildPolymarketThesisWeakenedMessage } from '../builders/polymarket-thesis-weakened.builder.js';

type PredictionAlertDoc = {
  _id: any;
  market_id?: string;
  alert_type?: string;
  priority?: string;
  title?: string;
  summary?: string;
  actionability?: number;
  transition?: { field?: string; from?: string; to?: string };
  meta?: any;
  created_at?: string | Date;
};

const WAVE_2_ALERTS = new Set([
  'new_mispricing',
  'repricing_started',
  'repricing_change',
  'overheated',
  'thesis_weakened',
  'entry_window_closed',
]);

// In-memory dedupe: marketId+alertType => lastEmitTimestamp. Survives process
// lifetime. Cross-process dedupe is already done by pushRouter (eventId + 5min).
const DEDUPE_WINDOW_MS = 10 * 60 * 1000; // 10 minutes
const emitDedupeCache = new Map<string, number>();

function shouldEmit(marketId: string, alertType: string): boolean {
  const key = `${marketId}:${alertType}`;
  const now = Date.now();
  const last = emitDedupeCache.get(key);
  if (last && now - last < DEDUPE_WINDOW_MS) return false;
  emitDedupeCache.set(key, now);
  return true;
}

function classifyAlert(alertType: string): { pushType: string; priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' } {
  switch (alertType) {
    case 'new_mispricing':     return { pushType: 'POLY_MISPRICING', priority: 'CRITICAL' };
    case 'repricing_started':  return { pushType: 'POLY_REPRICING', priority: 'HIGH' };
    case 'repricing_change':   return { pushType: 'POLY_REPRICING', priority: 'MEDIUM' };
    case 'overheated':         return { pushType: 'POLY_OVERHEATED', priority: 'HIGH' };
    case 'thesis_weakened':    return { pushType: 'POLY_THESIS_WEAKENED', priority: 'HIGH' };
    case 'entry_window_closed':return { pushType: 'POLY_THESIS_WEAKENED', priority: 'MEDIUM' };
    default:                   return { pushType: 'POLY_REPRICING', priority: 'MEDIUM' };
  }
}

export async function emitPolymarketAlert(doc: PredictionAlertDoc) {
  const alertType = String(doc.alert_type || '').toLowerCase();
  if (!WAVE_2_ALERTS.has(alertType)) {
    return { eventId: `polymarket_${String(doc._id)}`, skipped: `out_of_wave2_alertType=${alertType}` };
  }

  const marketId = String(doc.market_id || doc._id);
  if (!shouldEmit(marketId, alertType)) {
    return { eventId: `polymarket_${alertType}_${marketId}`, skipped: 'source_dedupe_10min' };
  }

  const { pushType, priority } = classifyAlert(alertType);

  const event: UnifiedEvent = {
    id: `polymarket_${alertType}_${marketId}`,
    category: 'retention',           // routed via retention path so builder dispatcher sees it
                                    // (asset=null prevents PERSONAL conversion automatically)
    source: 'polymarket',
    type: pushType,
    asset: null,                     // market-first — no asset attached
    stage: 'CONFIRMED',
    alpha: typeof doc.actionability === 'number' ? doc.actionability : 0.6,
    reason: doc.title || doc.summary || 'polymarket_alert',
    timestamp: doc.created_at ? new Date(doc.created_at).getTime() : Date.now(),
    meta: {
      alertType,
      marketId,
      marketTitle: doc.title || null,
      summary: doc.summary || null,
      actionability: doc.actionability ?? null,
      transitionFrom: doc.transition?.from || null,
      transitionTo: doc.transition?.to || null,
      edge: doc.meta?.edge ?? null,
      action: doc.meta?.action || null,
      conviction: doc.meta?.conviction || null,
      priority,
    },
  };

  return pushRouter.routeEvent(event);
}

/**
 * message-builder dispatcher — invoked when router sees POLY_* types.
 */
export function buildPolymarketMessage(
  event: UnifiedEvent,
  watchersCount?: number,
): { text: string; cta: string; priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' } | null {
  switch (String(event.type).toUpperCase()) {
    case 'POLY_MISPRICING':
      return buildPolymarketMispricingMessage({ event, watchersCount });
    case 'POLY_REPRICING':
      return buildPolymarketRepricingMessage({ event });
    case 'POLY_OVERHEATED':
      return buildPolymarketOverheatedMessage({ event });
    case 'POLY_THESIS_WEAKENED':
      return buildPolymarketThesisWeakenedMessage({ event });
    default:
      return null;
  }
}
