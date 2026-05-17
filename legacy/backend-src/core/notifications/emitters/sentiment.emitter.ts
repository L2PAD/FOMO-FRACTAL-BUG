/**
 * Sentiment Emitter
 * =================
 * Bridge: sentiment_events (MongoDB) → pushRouter.
 *
 * Accepts a raw sentiment_events document (from test_database.sentiment_events)
 * and emits a UnifiedEvent via pushRouter. Message text is built by a
 * kind-specific builder (listing / exploit / etf / regulation) — no generic
 * switch, each type has its own copy module.
 *
 * Wave 1 scope: listing | exploit | etf | regulation. Other eventTypes skipped.
 */

import { pushRouter } from '../push-router.service.js';
import type { UnifiedEvent } from '../../../modules/push_engine/types.js';

import { buildListingMessage } from '../builders/listing.builder.js';
import { buildExploitMessage } from '../builders/exploit.builder.js';
import { buildETFMessage } from '../builders/etf.builder.js';
import { buildRegulationMessage } from '../builders/regulation.builder.js';

type SentimentDoc = {
  _id: any;
  symbol?: string;
  tokens?: string[];
  sourceType?: string;
  source?: string;
  eventType?: string;            // listing | exploit | etf | regulation | legal | …
  weightedScore?: number;        // 0..1 (>0.5 bullish)
  weightedConfidence?: number;
  authorHandle?: string;
  title?: string;
  headline?: string;
  raw?: any;
  createdAt?: string | Date;
};

const WAVE_1_TYPES = new Set(['listing', 'exploit', 'etf', 'regulation', 'legal']);

export async function emitSentimentEvent(doc: SentimentDoc) {
  const eventType = String(doc.eventType || '').toLowerCase();
  if (!WAVE_1_TYPES.has(eventType)) {
    return { eventId: `sentiment_${String(doc._id)}`, skipped: `out_of_wave1_eventType=${eventType}` };
  }

  const asset = (doc.symbol || (doc.tokens && doc.tokens[0]) || 'BTC').toUpperCase();
  const score = typeof doc.weightedScore === 'number' ? doc.weightedScore : 0.5;
  const direction = score >= 0.6 ? 'bullish' : score <= 0.4 ? 'bearish' : 'neutral';

  // Type → PushType (stored on the unified event so router + in-app know which kind)
  const pushType: string =
    eventType === 'listing' ? 'LISTING' :
    eventType === 'exploit' ? 'EXPLOIT' :
    eventType === 'etf' ? 'ETF' :
    (eventType === 'regulation' || eventType === 'legal') ? 'REGULATION' :
    'CONFIRMED';

  // Priority — product rule (simple, not overengineered)
  const priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' =
    (eventType === 'listing' || eventType === 'exploit' || eventType === 'etf') ? 'CRITICAL' : 'HIGH';

  const event: UnifiedEvent = {
    id: `sentiment_${pushType.toLowerCase()}_${String(doc._id)}`,
    category: 'retention',
    source: 'sentiment',
    type: pushType,
    asset,
    stage: 'CONFIRMED',
    alpha: doc.weightedConfidence ?? 0.6,
    reason: doc.authorHandle || doc.source || doc.sourceType || 'sentiment_engine',
    timestamp: doc.createdAt ? new Date(doc.createdAt).getTime() : Date.now(),
    meta: {
      eventType,
      direction,
      weightedScore: score,
      weightedConfidence: doc.weightedConfidence ?? null,
      priority,
      // Raw payload preserved for future UX (headline, URL, etc.)
      rawSource: doc.raw?.source || doc.source || null,
      rawTitle: doc.raw?.title || doc.title || doc.headline || null,
      rawUrl: doc.raw?.url || null,
      // Hint for message-builder: builders below look at these
      exchange: doc.raw?.exchange || null,
      protocol: doc.raw?.protocol || null,
    },
  };

  return pushRouter.routeEvent(event);
}

/**
 * Invoked by push-router when it sees one of our LISTING/EXPLOIT/ETF/REGULATION
 * types — dispatches to the right builder. Returns {text, cta, priority}.
 * watchersCount is resolved by router via getRealWatchersCount before this call.
 */
export function buildSentimentMessage(
  event: UnifiedEvent,
  watchersCount?: number,
): { text: string; cta: string; priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' } | null {
  switch (String(event.type).toUpperCase()) {
    case 'LISTING':
      return buildListingMessage({ event, watchersCount });
    case 'EXPLOIT':
      return buildExploitMessage({ event });
    case 'ETF':
      return buildETFMessage({ event, watchersCount });
    case 'REGULATION':
      return buildRegulationMessage({ event });
    default:
      return null;
  }
}
