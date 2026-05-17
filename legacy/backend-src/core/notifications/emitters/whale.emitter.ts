/**
 * Whale Emitter (Wave 4)
 * =======================
 * Bridge: exchange_whale_events (MongoDB) → pushRouter.
 *
 * Push ONLY if:
 *   - asset != null
 *   - usdValue >= $5M
 *   - flowType in ('inflow','outflow')
 *   - optional: zScore >= 2 (spike confirmation)
 *
 * Two push types:
 *   WHALE_EXCHANGE_INFLOW
 *   WHALE_EXCHANGE_OUTFLOW
 *
 * Dedupe: asset + direction · 30 min window.
 */

import { pushRouter } from '../push-router.service.js';
import type { UnifiedEvent } from '../../../modules/push_engine/types.js';
import { buildWhaleInflowMessage } from '../builders/whale-inflow.builder.js';
import { buildWhaleOutflowMessage } from '../builders/whale-outflow.builder.js';

type WhaleDoc = {
  _id: any;
  asset?: string;
  symbol?: string;
  usdValue?: number;
  notionalUsd?: number;
  flowType?: string;
  direction?: string;
  exchange?: string;
  zScore?: number;
  createdAt?: string | Date;
};

const MIN_USD = 5_000_000;
const DEDUPE_WINDOW_MS = 30 * 60 * 1000;
const emitDedupeCache = new Map<string, number>();

function shouldEmit(key: string): boolean {
  const now = Date.now();
  const last = emitDedupeCache.get(key);
  if (last && now - last < DEDUPE_WINDOW_MS) return false;
  emitDedupeCache.set(key, now);
  return true;
}

export async function emitWhaleEvent(doc: WhaleDoc) {
  const asset = doc.asset || doc.symbol;
  if (!asset) {
    return { eventId: `whale_${String(doc._id)}`, skipped: 'no_asset' };
  }

  const flowType = String(doc.flowType || doc.direction || '').toLowerCase();
  if (flowType !== 'inflow' && flowType !== 'outflow') {
    return { eventId: `whale_${String(doc._id)}`, skipped: `bad_flow=${flowType}` };
  }

  const usd = Number(doc.usdValue || doc.notionalUsd || 0);
  if (usd < MIN_USD) {
    return { eventId: `whale_${String(doc._id)}`, skipped: 'below_5M' };
  }

  const pushType = flowType === 'inflow' ? 'WHALE_EXCHANGE_INFLOW' : 'WHALE_EXCHANGE_OUTFLOW';
  const dedupeKey = `whale:${asset}:${flowType}`;
  if (!shouldEmit(dedupeKey)) {
    return { eventId: dedupeKey, skipped: 'source_dedupe_30min' };
  }

  const event: UnifiedEvent = {
    id: `whale_${pushType.toLowerCase()}_${asset}_${String(doc._id)}`,
    category: 'alert',
    source: 'whale',
    type: pushType,
    asset,
    stage: 'CONFIRMED',
    alpha: 0.75,
    reason: `whale_${flowType}:${asset}`,
    timestamp: doc.createdAt ? new Date(doc.createdAt).getTime() : Date.now(),
    meta: {
      usdValue: usd,
      exchange: doc.exchange || 'Exchange',
      flowType,
      zScore: Number(doc.zScore || 0),
    },
  };

  return pushRouter.routeEvent(event);
}

export function buildWhaleMessage(event: UnifiedEvent, watchersCount?: number) {
  switch (String(event.type).toUpperCase()) {
    case 'WHALE_EXCHANGE_INFLOW':  return buildWhaleInflowMessage({ event, watchersCount });
    case 'WHALE_EXCHANGE_OUTFLOW': return buildWhaleOutflowMessage({ event, watchersCount });
    default: return null;
  }
}
