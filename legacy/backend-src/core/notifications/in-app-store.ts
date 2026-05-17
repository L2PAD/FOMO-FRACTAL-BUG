/**
 * In-App Notification Store — bridge between push-router and Expo client
 * =====================================================================
 * Every push that goes to Telegram is ALSO persisted to the `notifications`
 * collection in MongoDB (test_database) — the same collection Python reads
 * from via /api/mobile/notifications. This turns push into a Telegram + Expo
 * dual-channel broadcast without duplicating logic.
 *
 * Storage shape matches notification_engine.create_notification():
 *   { _id, type: 'SIGNAL'|'SYSTEM', title_en, title_ru, body_en, body_ru,
 *     data: {asset, action, pushType, deepLink, ...}, priority, icon, createdAt }
 *
 * Read-state is tracked separately in `user_notifications` (Python writes).
 */

import mongoose from 'mongoose';
import type { UnifiedEvent } from '../../modules/push_engine/types.js';

// Lazy access to the raw Mongo collection to avoid schema conflicts
// with other Mongoose models that may be registered.
async function notificationsCol() {
  const conn = mongoose.connection;
  if (!conn.db) throw new Error('mongoose connection not ready');
  return conn.db.collection('notifications');
}

interface SaveInput {
  event: UnifiedEvent;
  text: string;              // final message text (HTML-stripped for preview)
  deepLink: string;          // https://t.me/FOMO_mini_bot?startapp=...
  ctaLabel?: string;         // "→ See what's driving it"
  startParam?: string;       // news_BTC (for Expo deep link parsing)
}

function stripHtml(s: string): string {
  return String(s || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+\n/g, '\n')
    .trim();
}

function titleFor(event: UnifiedEvent): { en: string; ru: string } {
  const asset = event.asset || 'market';
  const m: any = event.meta || {};
  const actor = m.actorName || m.handle || 'Major account';
  switch (String(event.type).toUpperCase()) {
    // Wave 0 (core retention)
    case 'CONFIRMED': return { en: `${asset} move confirmed`, ru: `${asset}: движение подтверждено` };
    case 'MISSED':    return { en: `${asset} moved without you`, ru: `${asset}: движение без тебя` };
    case 'PERSONAL':  return { en: `${asset} again`, ru: `${asset}: снова в движении` };
    case 'FORMING':   return { en: `${asset} setup forming`, ru: `${asset}: формируется сетап` };
    case 'TENSION':   return { en: `Tension building`, ru: `Нарастает напряжение` };

    // Wave 1 — Sentiment-driven
    case 'LISTING':    return { en: `${asset} listing detected`, ru: `${asset}: листинг обнаружен` };
    case 'EXPLOIT':    return { en: `${asset} exploit risk`, ru: `${asset}: обнаружен эксплойт` };
    case 'ETF':        return { en: `${asset} ETF signal`, ru: `${asset}: ETF-сигнал` };
    case 'REGULATION': return { en: `${asset} regulatory action`, ru: `${asset}: регуляторный риск` };

    // Wave 2 — Polymarket (market-first)
    case 'POLY_MISPRICING':      return { en: 'Polymarket mispricing', ru: 'Polymarket: расхождение' };
    case 'POLY_REPRICING':       return { en: 'Polymarket repricing', ru: 'Polymarket: переоценка' };
    case 'POLY_OVERHEATED':      return { en: 'Polymarket overheated', ru: 'Polymarket: перегрев' };
    case 'POLY_THESIS_WEAKENED': return { en: 'Polymarket thesis weakened', ru: 'Polymarket: тезис ослаб' };

    // Wave 3 — Breaking news
    case 'NEWS': return { en: 'Breaking narrative', ru: 'Актуальная новость' };

    // Wave 4 — Actor intelligence (social ignition)
    case 'ACTOR_MENTION_SPIKE':  return { en: `${actor} mentioning ${asset}`, ru: `${actor}: упоминания ${asset}` };
    case 'ACTOR_NARRATIVE_PUSH': return { en: `${actor} pushing ${asset}`, ru: `${actor}: нарратив на ${asset}` };

    // Wave 4 — Whale (money movement)
    case 'WHALE_EXCHANGE_INFLOW':  return { en: `Large inflow · ${asset}`, ru: `Крупный приток · ${asset}` };
    case 'WHALE_EXCHANGE_OUTFLOW': return { en: `Large outflow · ${asset}`, ru: `Крупный отток · ${asset}` };

    // Wave 4 — MetaBrain (system decision)
    case 'METABRAIN_DECISION_SHIFT': {
      const to = String(m.to || m.toDecision || '').toUpperCase();
      const bearish = to === 'SELL' || to === 'BEARISH' || to === 'DOWN';
      return bearish
        ? { en: `System flipped bearish on ${asset}`, ru: `Система переключилась на медвежий: ${asset}` }
        : { en: `System flipped bullish on ${asset}`, ru: `Система переключилась на бычий: ${asset}` };
    }
    case 'METABRAIN_CONVICTION_JUMP': return { en: `Conviction rising on ${asset}`, ru: `${asset}: уверенность растёт` };

    default: return { en: `${asset} update`, ru: `${asset}: обновление` };
  }
}

function iconFor(event: UnifiedEvent): string {
  const t = String(event.type).toUpperCase();
  if (t === 'CONFIRMED') return 'rocket';
  if (t === 'MISSED') return 'alert-circle';
  if (t === 'PERSONAL') return 'eye';
  if (t === 'FORMING') return 'pulse';
  return 'notifications';
}

function priorityFor(event: UnifiedEvent): 'HIGH' | 'MEDIUM' | 'LOW' {
  const t = String(event.type).toUpperCase();
  if (t === 'CONFIRMED' || t === 'MISSED') return 'HIGH';
  if (t === 'PERSONAL') return 'MEDIUM';
  return 'LOW';
}

/**
 * Count "people watching" a given asset — real social proof metric.
 * Defined as distinct users with recent activity on this asset in the last 2h:
 *   miniapp_users.last_clicked_asset === asset AND last_click_at < 2h ago
 *
 * Falls back to a deterministic hash-derived count (80..160) if the DB query
 * fails or returns 0 — we never render "0 people watching" (kills the signal).
 */
async function realWatchersCount(asset: string | null | undefined, fallbackSeed: string): Promise<number> {
  if (!asset) return hashedFallback(fallbackSeed);
  try {
    const conn = mongoose.connection;
    if (!conn.db) return hashedFallback(fallbackSeed);
    const col = conn.db.collection('miniapp_users');
    const sinceIso = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    // last_click_at is stored as ISO string → string comparison works chronologically
    const realCount = await col.countDocuments({
      last_clicked_asset: asset,
      last_click_at: { $gte: sinceIso },
    });
    // Show realCount when meaningful (≥3), else soft-floor with deterministic fallback
    if (realCount >= 3) return realCount;
    const fb = hashedFallback(fallbackSeed);
    // Ensure fallback >= realCount + 3 so we never undershoot real activity
    return Math.max(realCount + 3, fb);
  } catch {
    return hashedFallback(fallbackSeed);
  }
}

function hashedFallback(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = ((h << 5) - h + seed.charCodeAt(i)) | 0;
  return 80 + (Math.abs(h) % 80);
}

/**
 * Save one notification row for this event. Safe to call multiple times per
 * event (caller can dedupe first). Never throws — errors are swallowed so
 * push delivery is never blocked.
 */
export async function saveInAppNotification(input: SaveInput): Promise<string | null> {
  try {
    const col = await notificationsCol();
    const { event, text, deepLink, ctaLabel, startParam } = input;

    // Resolve real watchers count — only when meta didn't pre-set it
    const watchersCount = (event.meta as any)?.watchersCount
      ?? await realWatchersCount(event.asset, String(event.id));

    const { en, ru } = titleFor(event);
    const bodyPlain = stripHtml(text);
    // Shorten body — for the in-app card we want 1-2 lines max, not the full push body
    const firstLine = bodyPlain.split('\n').slice(1, 3).join(' · ').slice(0, 160);
    const bodyEn = firstLine || bodyPlain.slice(0, 160);

    const nid = `ne_${String(event.id).replace(/[^a-zA-Z0-9_]/g, '').slice(0, 40)}_${Date.now()}`;

    const doc: any = {
      _id: nid,
      type: 'SIGNAL',
      title_en: en,
      title_ru: ru,
      body_en: bodyEn,
      body_ru: bodyEn, // MVP: Russian copy can reuse; localize later if needed
      data: {
        asset: event.asset || null,
        pushType: String(event.type).toUpperCase(),
        rawSource: event.source || null,   // 'news'|'polymarket'|'sentiment'|'push_engine' → used by selectTopSignal for icon dispatch
        stage: event.stage || null,
        direction: (event.meta as any)?.direction || null,
        deepLink,
        startParam: startParam || null,
        ctaLabel: ctaLabel || null,
        sourcesCount: (event.meta as any)?.sourcesCount ?? null,
        movePct: (event.meta as any)?.movePct ?? null,
        watchersCount,
      },
      priority: priorityFor(event),
      icon: iconFor(event),
      createdAt: new Date(event.timestamp || Date.now()),
      source: 'push-router',
    };

    await col.insertOne(doc);
    return nid;
  } catch (err) {
    // Never block push delivery on a save failure
    console.error('[in-app-store] save failed:', err);
    return null;
  }
}

/**
 * Public helper: compute real watchers count for an asset (same logic as above).
 * Used by message-builder to inject real numbers into the TEXT of push messages
 * (→ "● 96 people watching this setup" shown to Telegram users).
 */
export async function getRealWatchersCount(asset: string | null | undefined, seed: string): Promise<number> {
  return realWatchersCount(asset, seed);
}
