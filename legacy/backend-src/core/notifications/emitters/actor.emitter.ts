/**
 * Actor Emitter (Wave 4)
 * =======================
 * Bridge: actor_signal_events (MongoDB) → pushRouter.
 *
 * Push ONLY if:
 *   - asset != null
 *   - influenceScore >= 0.75
 *   - mentionCount >= 3 (within 15-minute window)
 *
 * Two push types:
 *   ACTOR_MENTION_SPIKE   — mentions >= 3 (mention burst)
 *   ACTOR_NARRATIVE_PUSH  — influence >= 0.80 AND abs(sentimentScore) >= 0.6
 *                            AND confidence >= 0.7 (narrative push)
 *
 * Dedupe: asset + actor + pushType · 20 min window.
 */

import { pushRouter } from '../push-router.service.js';
import type { UnifiedEvent } from '../../../modules/push_engine/types.js';
import { buildActorMentionSpikeMessage } from '../builders/actor-mention-spike.builder.js';
import { buildActorNarrativeMessage } from '../builders/actor-narrative.builder.js';

type ActorSignalDoc = {
  _id: any;
  asset?: string;
  symbol?: string;
  actorName?: string;
  handle?: string;
  actorId?: string;
  mentionCount?: number;
  count?: number;
  influenceScore?: number;
  actorScore?: number;
  sentimentScore?: number;
  direction?: string;
  sentimentHint?: string;
  confidence?: number;
  createdAt?: string | Date;
  windowMinutes?: number;
};

const DEDUPE_WINDOW_MS = 20 * 60 * 1000;
const emitDedupeCache = new Map<string, number>();

function shouldEmit(key: string): boolean {
  const now = Date.now();
  const last = emitDedupeCache.get(key);
  if (last && now - last < DEDUPE_WINDOW_MS) return false;
  emitDedupeCache.set(key, now);
  return true;
}

function classifyActor(doc: ActorSignalDoc): 'ACTOR_NARRATIVE_PUSH' | 'ACTOR_MENTION_SPIKE' | null {
  const influence = Number(doc.influenceScore || doc.actorScore || 0);
  const mentions = Number(doc.mentionCount || doc.count || 0);
  const sent = Math.abs(Number(doc.sentimentScore || 0));
  const confidence = Number(doc.confidence || 0);

  // Narrative push — strong, directional, audience-reacting.
  if (influence >= 0.8 && sent >= 0.6 && confidence >= 0.7) {
    return 'ACTOR_NARRATIVE_PUSH';
  }
  // Mention spike — 3+ mentions in a tight window from influential account.
  if (mentions >= 3 && influence >= 0.75) {
    return 'ACTOR_MENTION_SPIKE';
  }
  return null;
}

export async function emitActorEvent(doc: ActorSignalDoc) {
  const asset = doc.asset || doc.symbol;
  if (!asset) {
    return { eventId: `actor_${String(doc._id)}`, skipped: 'no_asset' };
  }

  const pushType = classifyActor(doc);
  if (!pushType) {
    return { eventId: `actor_${String(doc._id)}`, skipped: 'below_thresholds' };
  }

  const actor = doc.actorName || doc.handle || doc.actorId || 'major_account';
  const dedupeKey = `actor:${asset}:${actor}:${pushType}`;
  if (!shouldEmit(dedupeKey)) {
    return { eventId: dedupeKey, skipped: 'source_dedupe_20min' };
  }

  const event: UnifiedEvent = {
    id: `actor_${pushType.toLowerCase()}_${asset}_${String(doc._id)}`,
    category: 'alert',
    source: 'actor',
    type: pushType,
    asset,
    stage: 'CONFIRMED',
    alpha: Math.max(Number(doc.influenceScore || 0), 0.7),
    reason: `${actor}:${pushType.toLowerCase()}`,
    timestamp: doc.createdAt ? new Date(doc.createdAt).getTime() : Date.now(),
    meta: {
      actorName: actor,
      mentionCount: Number(doc.mentionCount || doc.count || 0),
      influenceScore: Number(doc.influenceScore || doc.actorScore || 0),
      direction: doc.direction || doc.sentimentHint || (Number(doc.sentimentScore || 0) < 0 ? 'bearish' : 'bullish'),
      sentimentScore: Number(doc.sentimentScore || 0),
      confidence: Number(doc.confidence || 0),
      windowMinutes: Number(doc.windowMinutes || 15),
    },
  };

  return pushRouter.routeEvent(event);
}

export function buildActorMessage(event: UnifiedEvent, watchersCount?: number) {
  switch (String(event.type).toUpperCase()) {
    case 'ACTOR_MENTION_SPIKE':  return buildActorMentionSpikeMessage({ event, watchersCount });
    case 'ACTOR_NARRATIVE_PUSH': return buildActorNarrativeMessage({ event, watchersCount });
    default: return null;
  }
}
