/**
 * Push Router — Unified Notification Flow
 * ========================================
 * Single entry point every event source calls to deliver a message.
 *
 *   PushEngine ─┐
 *   FomoAlerts ─┼──> pushRouter.routeEvent(UnifiedEvent)
 *   External   ─┘            │
 *                              ├─ dedupe (5-min TTL)
 *                              ├─ fanout to push_subscribers
 *                              ├─ rules (cooldown / cap / recent)
 *                              ├─ role-aware message (user | admin)
 *                              └─ telegram.sendTelegramMessage
 *
 * NO parallel telegram pipelines are replaced. This router IS the new
 * transport for Push Engine + future FOMO-Alerts/external webhook consumers.
 * Legacy Telegram Delivery / Python engine stay as-is.
 */

import {
  PushSubscriberModel,
  PushLogModel,
  markPushTypeSent,
} from '../../modules/push_engine/push_state.repository.js';
import {
  enqueuePush,
  enqueueSkipped,
  markQueueItemSent,
  bumpUserCounters,
} from '../../modules/push_engine/push_queue.js';
import {
  shouldSendToUser,
  isEventEligible,
} from '../../modules/push_engine/push_rules.js';
import { saveInAppNotification, getRealWatchersCount } from './in-app-store.js';
import { antiSpamCheck } from './throttle.engine.js';
import type {
  UnifiedEvent,
  PushSubscriber,
  DetectedEvent,
  PushType,
  SubscriberRole,
} from '../../modules/push_engine/types.js';
import { buildMessage } from './message-builder.js';

const CHANNEL = (process.env.PUSH_ENGINE_CHANNEL || 'mock').toLowerCase() as 'mock' | 'telegram';
const DEDUPE_TTL_MS = Number(process.env.PUSH_ROUTER_DEDUPE_MS || 5 * 60 * 1000);

// Allowed types gate — env-controlled so we can introduce new event types without
// re-deploy. Default day-1: retention only (no TENSION noise).
const ALLOWED_TYPES = (process.env.PUSH_ENGINE_ALLOWED_TYPES || 'FORMING,CONFIRMED,PERSONAL')
  .split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);

// ─── Dedupe cache (in-memory, 5-min TTL) ─────────────────────────────────────
const dedupeCache = new Map<string, number>();

function dedupeKey(event: UnifiedEvent): string {
  // Dedupe per (source,asset,stage,type,id) — stops the exact same event being routed twice in the TTL window.
  return `${event.source}|${event.asset || '-'}|${event.stage || '-'}|${event.type}|${event.id}`;
}

function isDuplicate(event: UnifiedEvent): boolean {
  const k = dedupeKey(event);
  const now = Date.now();
  const last = dedupeCache.get(k);
  if (last && now - last < DEDUPE_TTL_MS) return true;
  dedupeCache.set(k, now);
  // Opportunistic cleanup
  if (dedupeCache.size > 2000) {
    const cutoff = now - DEDUPE_TTL_MS;
    for (const [key, ts] of dedupeCache) if (ts < cutoff) dedupeCache.delete(key);
  }
  return false;
}

// ─── Telegram transport (lazy-loaded to avoid circular import at boot) ───────────────
async function sendViaTelegram(
  chatId: string,
  text: string,
  inlineButton?: { text: string; webAppUrl: string },
): Promise<{ ok: boolean; error?: string }> {
  try {
    const mod = await import('./telegram.service.js');
    return mod.sendTelegramMessage(chatId, text, {
      parseMode: 'HTML',
      disableWebPagePreview: true,
      inlineKeyboard: inlineButton ? [[{ text: inlineButton.text, webAppUrl: inlineButton.webAppUrl }]] : undefined,
    });
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

// ─── Normalizer: DetectedEvent → UnifiedEvent ──────────────────────────────────
export function fromDetectedEvent(e: DetectedEvent): UnifiedEvent {
  return {
    id: e.eventId,
    category: 'retention',
    source: 'push_engine',
    type: e.type,
    asset: e.asset,
    stage: e.stage,
    alpha: e.alpha,
    reason: e.reason,
    deepLink: e.deepLink,
    timestamp: e.createdAt.getTime(),
    meta: e.meta,
  };
}

// ─── Target user selection ───────────────────────────────────────────────
async function getTargetUsers(event: UnifiedEvent): Promise<PushSubscriber[]> {
  // Targeted delivery (MISSED / PERSONAL retention) — only to the user who
  // had prior interaction with this asset. Scoped emission bypasses broadcast.
  if (event.forUserId) {
    const one = await PushSubscriberModel.findOne({ userId: event.forUserId, muted: { $ne: true } })
      .lean<PushSubscriber>().exec();
    return one ? [one] : [];
  }
  // 'system' category → admins only. 'retention'/'alert' → all non-muted users (admins also receive).
  const filter: any = { muted: { $ne: true } };
  if (event.category === 'system') filter.role = 'admin';
  return PushSubscriberModel.find(filter).lean<PushSubscriber[]>().exec();
}

// ─── Rule adapter: UnifiedEvent → DetectedEvent-like for existing rules ───────────────
function toDetectedLike(event: UnifiedEvent): DetectedEvent {
  return {
    type: event.type as PushType,
    eventId: event.id,
    clusterId: undefined,
    asset: event.asset ?? null,
    stage: (event.stage as any) || 'FORMING',
    alpha: event.alpha ?? 0.5,
    reason: event.reason || '',
    title: '',
    body: '',
    deepLink: event.deepLink || '',
    priority: (event.severity === 'critical' ? 'high' : 'normal'),
    createdAt: new Date(event.timestamp),
    meta: event.meta || {},
  };
}

// ─── Public API ──────────────────────────────────────────────────────────
export interface RouteResult {
  eventId: string;
  duplicated: boolean;
  wouldSendTo: number;
  filteredOut: number;
  sent: number;
  sendFailures: number;
}

export async function routeEvent(event: UnifiedEvent): Promise<RouteResult> {
  const result: RouteResult = {
    eventId: event.id,
    duplicated: false,
    wouldSendTo: 0,
    filteredOut: 0,
    sent: 0,
    sendFailures: 0,
  };

  // 1. Dedup
  if (isDuplicate(event)) {
    result.duplicated = true;
    return result;
  }

  // 1b. Allowed-types gate (env-controlled; default retention-only on day-1)
  if (!ALLOWED_TYPES.includes(String(event.type).toUpperCase())) {
    result.filteredOut = 1;
    return result;
  }

  // 2. Global event sanity
  const detectedLike = toDetectedLike(event);
  const gate = isEventEligible(detectedLike);
  if (!gate.allowed) {
    result.filteredOut = 1;
    return result;
  }

  // 3. Fanout
  const subscribers = await getTargetUsers(event);
  let stateTouched = false;
  let inAppSavedForEvent = false;

  // Resolve real watchers count ONCE per event (before per-user fan-out),
  // so every push — Telegram text + Expo card — shows the same real number.
  // miniapp_users.last_clicked_asset === asset AND last_click_at < 2h
  const watchersResolved = await getRealWatchersCount(event.asset, String(event.id));
  if (!event.meta) event.meta = {};
  if (typeof (event.meta as any).watchersCount !== 'number') {
    (event.meta as any).watchersCount = watchersResolved;
  }

  if (subscribers.length === 0) {
    // Observability fallback — still record the event so admins can see what WOULD have shipped.
    await enqueuePush(null, detectedLike);
    stateTouched = true;
  }

  for (const sub of subscribers) {
    // Personal conversion — retention events matching a user's recent assets
    // read as PERSONAL (retention reminder "you tracked this").
    // Exception: MISSED is its own retention flavour with its own builder +
    // bypass rules, so we never reclassify it.
    let perUserEvent = event;
    if (
      event.category === 'retention' &&
      event.asset &&
      sub.recentAssets?.includes(event.asset) &&
      event.type !== 'PERSONAL' &&
      event.type !== 'MISSED'
    ) {
      perUserEvent = { ...event, type: 'PERSONAL', reason: `PERSONAL via ${event.type}` };
    }

    const perUserDetected = toDetectedLike(perUserEvent);
    const rule = shouldSendToUser(sub, perUserDetected);
    if (!rule.allowed) {
      await enqueueSkipped(sub.userId, perUserDetected, rule.reason || 'skipped');
      result.filteredOut += 1;
      continue;
    }

    // ── Anti-Spam soft throttle (priority-aware) ─────────────────────────
    // CRITICAL (priority >= 90: LISTING/EXPLOIT/ETF/POLY_MISPRICING/METABRAIN_SHIFT)
    // ALWAYS passes. Lower-priority events get demoted to in-app-only if user got
    // ≥ PUSH_SOFT_CAP_6H (default 5) pushes in the last 6h.
    const antiSpam = await antiSpamCheck(sub.userId, {
      type: perUserEvent.type as string,
      meta: perUserEvent.meta,
    });
    const demoteToInApp = antiSpam.allow && antiSpam.overrideToInApp;
    if (!antiSpam.allow) {
      await enqueueSkipped(sub.userId, perUserDetected, `anti_spam_${antiSpam.reason}`);
      result.filteredOut += 1;
      continue;
    }

    // Build role-aware message
    const role: SubscriberRole = (sub.role as SubscriberRole) || 'user';
    const msg = buildMessage(perUserEvent, role);

    const queueItem = await enqueuePush(sub.userId, perUserDetected);
    result.wouldSendTo += 1;

    // Demoted (anti-spam soft cap) → skip Telegram but keep in-app mirror below
    if (CHANNEL === 'telegram' && sub.telegramChatId && !demoteToInApp) {
      const tg = await sendViaTelegram(sub.telegramChatId, msg.text, msg.inlineButton);
      if (!tg.ok) {
        result.sendFailures += 1;
        await PushLogModel.create({
          userId: sub.userId, eventId: event.id, type: perUserEvent.type,
          asset: perUserEvent.asset ?? null,
          title: msg.text.split('\n')[0]?.slice(0, 80) || '',
          body: `[send_failed] ${tg.error || ''}`,
          channel: 'telegram', ts: new Date(),
        });
        continue;
      }
    }

    // Log delivery (mock or telegram)
    await PushLogModel.create({
      userId: sub.userId,
      eventId: event.id,
      type: perUserEvent.type,
      asset: perUserEvent.asset ?? null,
      title: msg.text.split('\n')[0]?.slice(0, 120) || '',
      body: msg.text,
      channel: CHANNEL,
      ts: new Date(),
    });

    // Also mirror this push into the in-app `notifications` collection so
    // the Expo client sees it in Notification Center. Broadcast style —
    // one row per event, read-state tracked per user in `user_notifications`.
    // Saved once per event (on the first subscriber's pass) so duplicates
    // don't flood the bell badge.
    if (!inAppSavedForEvent) {
      const sp = `${String(perUserEvent.category === 'retention' ? 'news' : 'news')}_${perUserEvent.asset || ''}`;
      saveInAppNotification({
        event: perUserEvent,
        text: msg.text,
        deepLink: msg.deepLink,
        ctaLabel: msg.inlineButton?.text,
        startParam: sp,
      }).catch(() => {});
      inAppSavedForEvent = true;
    }

    await markQueueItemSent((queueItem as any)._id, CHANNEL);
    await bumpUserCounters(sub.userId, perUserEvent.asset ?? null);
    result.sent += 1;
    stateTouched = true;
  }

  // 4. Mark state (dedup guarantee across cycles, not just 5-min window)
  if (stateTouched) {
    await markPushTypeSent(
      event.id,
      event.type as string,
      (event.stage as string) || 'FORMING',
      event.alpha ?? 0,
    );
  }

  return result;
}

export function getDedupeStats() {
  return {
    size: dedupeCache.size,
    ttlMs: DEDUPE_TTL_MS,
    channel: CHANNEL,
    allowedTypes: ALLOWED_TYPES,
  };
}

export function clearDedupeCache(): number {
  const n = dedupeCache.size;
  dedupeCache.clear();
  return n;
}

export const pushRouter = { routeEvent, fromDetectedEvent, getDedupeStats, clearDedupeCache };
