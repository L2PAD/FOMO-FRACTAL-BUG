/**
 * News Emitter
 * ============
 * Bridge: news_articles (MongoDB) → pushRouter.
 *
 * Hard gate via classifyBreakingNews() — most articles are rejected here.
 * Global throttle: max 3 NEWS pushes per 6h across all subscribers.
 *
 * Market-first: asset=null, category='retention' (so builder dispatcher picks it up).
 */

import mongoose from 'mongoose';
import { pushRouter } from '../push-router.service.js';
import type { UnifiedEvent } from '../../../modules/push_engine/types.js';
import { classifyBreakingNews, type NewsClassification } from '../classifiers/news.classifier.js';
import { buildBreakingNewsMessage } from '../builders/news.builder.js';

// Global NEWS rate-limit — separate from per-user daily cap
const NEWS_WINDOW_MS = 6 * 60 * 60 * 1000;
const NEWS_MAX_PER_WINDOW = Number(process.env.PUSH_NEWS_MAX_PER_6H || 3);

const globalNewsEmittedAt: number[] = [];

function globalNewsQuotaOk(): boolean {
  const now = Date.now();
  while (globalNewsEmittedAt.length && now - globalNewsEmittedAt[0]! > NEWS_WINDOW_MS) {
    globalNewsEmittedAt.shift();
  }
  return globalNewsEmittedAt.length < NEWS_MAX_PER_WINDOW;
}

// Per-source dedupe: same URL/id within 2h — never push twice
const DEDUPE_WINDOW_MS = 2 * 60 * 60 * 1000;
const emitDedupeCache = new Map<string, number>();
function shouldEmit(key: string): boolean {
  const now = Date.now();
  const last = emitDedupeCache.get(key);
  if (last && now - last < DEDUPE_WINDOW_MS) return false;
  emitDedupeCache.set(key, now);
  return true;
}

type NewsDoc = {
  _id: any; id?: string; title?: string; summary?: string; url?: string;
  tags?: string[]; tier?: string; source_name?: string; category?: string;
  entities_mentioned?: string[]; entity_count?: number;
  published_at?: string; created_at?: string;
};

export async function emitNewsArticle(doc: NewsDoc, classification?: NewsClassification) {
  const cls = classification || classifyBreakingNews(doc);
  if (!cls.isBreaking) {
    return { eventId: `news_${String(doc._id)}`, skipped: `not_breaking_reason=${cls.reason}` };
  }

  const key = String(doc.url || doc.id || doc._id);
  if (!shouldEmit(key)) {
    return { eventId: `news_${key}`, skipped: 'source_dedupe_2h' };
  }

  if (!globalNewsQuotaOk()) {
    return { eventId: `news_${key}`, skipped: `global_news_quota_${NEWS_MAX_PER_WINDOW}_per_6h` };
  }

  const event: UnifiedEvent = {
    id: `news_${String(doc._id)}`,
    category: 'retention',   // routed via retention path so message-builder can dispatch
    source: 'news',
    type: 'NEWS',
    asset: null,             // market-first
    stage: 'CONFIRMED',
    alpha: cls.score,
    reason: doc.title || 'news',
    timestamp: doc.published_at ? new Date(doc.published_at).getTime() : Date.now(),
    meta: {
      title: doc.title,
      summary: doc.summary,
      url: doc.url,
      sourceName: doc.source_name,
      tier: doc.tier,
      tags: doc.tags,
      sentiment: cls.sentiment,
      direction: cls.sentiment,
      priority: cls.priority,
      classificationScore: cls.score,
      classificationReason: cls.reason,
    },
  };

  const res = await pushRouter.routeEvent(event);
  // Count toward quota only if something was actually sent (not filteredOut/duplicated)
  if ((res as any)?.sent > 0) {
    globalNewsEmittedAt.push(Date.now());
  }
  return res;
}

export function buildNewsMessage(
  event: UnifiedEvent,
  watchersCount?: number,
): { text: string; cta: string; priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' } | null {
  if (String(event.type).toUpperCase() !== 'NEWS') return null;
  return buildBreakingNewsMessage({ event, watchersCount });
}
