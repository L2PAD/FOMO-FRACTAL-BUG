/**
 * Push Admin Routes
 * =================
 * Admin-only introspection endpoints for the Push Engine.
 *
 *   GET  /api/panel/push/stats       — last cycle + config
 *   GET  /api/panel/push/queue       — recent queue items (sent/skipped/pending)
 *   GET  /api/panel/push/events      — last detection events (what WOULD be sent)
 *   GET  /api/panel/push/logs        — real deliveries (mock-channel included)
 *   POST /api/panel/push/run         — force a cycle now (debug)
 *   POST /api/panel/push/subscribe   — create/update a subscriber (used by mobile app)
 */

import type { FastifyInstance } from 'fastify';
import { PushQueueModel, PushLogModel, PushSubscriberModel, PushStateModel } from './push_state.repository.js';
import { runCycleOnce, lastCycleReport, cycleHistory } from './push_scheduler.js';
import { PUSH_RULES_CONFIG } from './push_rules.js';
import { PUSH_ENGINE_CHANNEL } from './push_sender.js';
import { pushRouter } from '../../core/notifications/push-router.service.js';
import { buildMessage } from '../../core/notifications/message-builder.js';
import type { UnifiedEvent, SubscriberRole } from './types.js';

export async function registerPushAdminRoutes(app: FastifyInstance): Promise<void> {
  app.get('/stats', async () => {
    const [queueCounts, logsCount, subsCount, stateCount] = await Promise.all([
      PushQueueModel.aggregate([{ $group: { _id: '$status', n: { $sum: 1 } } }]),
      PushLogModel.countDocuments({}),
      PushSubscriberModel.countDocuments({}),
      PushStateModel.countDocuments({}),
    ]);
    const byStatus: Record<string, number> = { pending: 0, sent: 0, skipped: 0 };
    for (const row of queueCounts) byStatus[row._id] = row.n;
    return {
      ok: true,
      data: {
        channel: PUSH_ENGINE_CHANNEL,
        rules: PUSH_RULES_CONFIG,
        subscribers: subsCount,
        stateEntries: stateCount,
        logs: logsCount,
        queue: byStatus,
        lastCycle: lastCycleReport,
        recentCycles: cycleHistory,
      },
    };
  });

  app.get('/queue', async (req) => {
    const q = req.query as Record<string, string>;
    const status = q.status; // 'pending'|'sent'|'skipped' optional
    const limit = Math.min(parseInt(q.limit || '50', 10), 200);
    const filter: any = {};
    if (status) filter.status = status;
    if (q.type) filter.type = q.type;
    if (q.asset) filter.asset = q.asset.toUpperCase();
    const items = await PushQueueModel.find(filter).sort({ createdAt: -1 }).limit(limit).lean();
    return { ok: true, data: items };
  });

  app.get('/events', async () => {
    // Aggregate what WAS detected this window, per event/type.
    // Reads from push_queue (both sent + skipped) grouped.
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const rows = await PushQueueModel.aggregate([
      { $match: { createdAt: { $gte: since } } },
      {
        $group: {
          _id: { eventId: '$eventId', type: '$type', asset: '$asset', stage: '$stage' },
          queued: { $sum: { $cond: [{ $eq: ['$status', 'pending'] }, 1, 0] } },
          sent:   { $sum: { $cond: [{ $eq: ['$status', 'sent'] },    1, 0] } },
          skipped: { $sum: { $cond: [{ $eq: ['$status', 'skipped'] }, 1, 0] } },
          avgAlpha: { $avg: '$alpha' },
          reasons:  { $addToSet: '$reason' },
          skipReasons: { $addToSet: '$skipReason' },
          firstAt:  { $min: '$createdAt' },
          lastAt:   { $max: '$createdAt' },
        },
      },
      { $sort: { lastAt: -1 } },
      { $limit: 100 },
    ]);
    const data = rows.map((r) => ({
      eventId: r._id.eventId,
      type: r._id.type,
      asset: r._id.asset,
      stage: r._id.stage,
      alpha: r.avgAlpha ? Number(r.avgAlpha.toFixed(3)) : 0,
      wouldSendTo: r.sent + r.queued,
      filteredOut: r.skipped,
      reasons: (r.reasons || []).filter(Boolean),
      skipReasons: (r.skipReasons || []).filter(Boolean),
      firstAt: r.firstAt,
      lastAt: r.lastAt,
    }));
    return { ok: true, data };
  });

  app.get('/logs', async (req) => {
    const q = req.query as Record<string, string>;
    const limit = Math.min(parseInt(q.limit || '50', 10), 200);
    const logs = await PushLogModel.find({}).sort({ ts: -1 }).limit(limit).lean();
    return { ok: true, data: logs };
  });

  app.post('/run', async () => {
    const report = await runCycleOnce();
    return { ok: true, data: report };
  });

  // ── Wave 1: Sentiment → Push bridge ─────────────────────────────────────────
  // Emit a push from an EXISTING sentiment_events document (by _id) OR from an
  // inline sentiment-shaped payload. Used to drive listing/exploit/etf/regulation
  // signals through the unified router without touching the Python pipeline.
  //   body: { _id?: string, doc?: SentimentDoc }
  app.post('/emit/sentiment', async (req) => {
    const body = (req.body || {}) as any;
    try {
      const { emitSentimentEvent } = await import('../../core/notifications/emitters/sentiment.emitter.js');
      let doc = body.doc;
      if (!doc && body._id) {
        const mongoose = (await import('mongoose')).default;
        const col = mongoose.connection.db?.collection('sentiment_events');
        if (!col) return { ok: false, error: 'mongo_not_ready' };
        const { ObjectId } = await import('mongodb');
        let id: any = body._id;
        try { id = new ObjectId(String(body._id)); } catch { /* keep as string */ }
        doc = await col.findOne({ _id: id });
        if (!doc) return { ok: false, error: 'sentiment_event_not_found', id: String(body._id) };
      }
      if (!doc) return { ok: false, error: 'doc_or_id_required' };
      const res = await emitSentimentEvent(doc);
      return { ok: true, data: res };
    } catch (err: any) {
      return { ok: false, error: String(err?.message || err) };
    }
  });

  // ── Wave 2: Polymarket → Push bridge ────────────────────────────────────────
  app.post('/emit/polymarket', async (req) => {
    const body = (req.body || {}) as any;
    try {
      const { emitPolymarketAlert } = await import('../../core/notifications/emitters/polymarket.emitter.js');
      let doc = body.doc;
      if (!doc && body._id) {
        const mongoose = (await import('mongoose')).default;
        const col = mongoose.connection.db?.collection('prediction_alerts');
        if (!col) return { ok: false, error: 'mongo_not_ready' };
        const { ObjectId } = await import('mongodb');
        let id: any = body._id;
        try { id = new ObjectId(String(body._id)); } catch { /* keep string */ }
        doc = await col.findOne({ _id: id });
        if (!doc) return { ok: false, error: 'prediction_alert_not_found', id: String(body._id) };
      }
      if (!doc) return { ok: false, error: 'doc_or_id_required' };
      const res = await emitPolymarketAlert(doc);
      return { ok: true, data: res };
    } catch (err: any) {
      return { ok: false, error: String(err?.message || err) };
    }
  });

  // ── Signal Worker (auto-emit polling) — manual trigger ──────────────────────
  app.post('/worker/run-once', async () => {
    try {
      const { runSignalWorkerOnce } = await import('../../core/notifications/emitters/signal.worker.js');
      const res = await runSignalWorkerOnce();
      return { ok: true, data: res };
    } catch (err: any) {
      return { ok: false, error: String(err?.message || err) };
    }
  });

  // Preview — render message text for an event WITHOUT touching the router.
  // Useful for QA / copy iteration: see exactly what telegram will get.
  //   body: { event: UnifiedEvent, role?: 'user'|'admin' }
  app.post('/preview', async (req) => {
    const body = (req.body || {}) as { event?: Partial<UnifiedEvent>; role?: SubscriberRole };
    if (!body.event || !body.event.type || !body.event.id) {
      return { ok: false, error: 'event.id and event.type are required' };
    }
    const event: UnifiedEvent = {
      id: String(body.event.id),
      category: (body.event.category as any) || 'alert',
      source: (body.event.source as any) || 'fomo',
      type: String(body.event.type),
      asset: body.event.asset ?? null,
      stage: body.event.stage,
      alpha: body.event.alpha,
      severity: body.event.severity,
      reason: body.event.reason,
      deepLink: body.event.deepLink,
      timestamp: body.event.timestamp ?? Date.now(),
      meta: body.event.meta || {},
    };
    const msg = buildMessage(event, (body.role as SubscriberRole) || 'user');
    return { ok: true, data: { text: msg.text, parseMode: msg.parseMode, deepLink: msg.deepLink } };
  });

  // Webhook for ANY external source (Python engine, FOMO alerts, external scripts)
  // to inject an event directly into the unified router. Bypasses the news detector
  // but respects dedupe, rules, and delivery channel.
  app.post('/event', async (req) => {
    const body = (req.body || {}) as Partial<UnifiedEvent>;
    if (!body.id || !body.type || !body.source || !body.category) {
      return { ok: false, error: 'id, type, source, category are required' };
    }
    const event: UnifiedEvent = {
      id: String(body.id),
      category: body.category as any,
      source: body.source as any,
      type: String(body.type),
      asset: body.asset ?? null,
      stage: body.stage,
      alpha: body.alpha,
      severity: body.severity,
      reason: body.reason,
      deepLink: body.deepLink,
      timestamp: body.timestamp ?? Date.now(),
      meta: body.meta || {},
    };
    const res = await pushRouter.routeEvent(event);
    return { ok: true, data: res };
  });

  // Debug aliases (per unified-router task spec)
  app.get('/debug/events', async () => {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const rows = await PushQueueModel.aggregate([
      { $match: { createdAt: { $gte: since } } },
      {
        $group: {
          _id: { eventId: '$eventId', type: '$type', asset: '$asset' },
          wouldSendTo: { $sum: { $cond: [{ $ne: ['$status', 'skipped'] }, 1, 0] } },
          filteredOut: { $sum: { $cond: [{ $eq: ['$status', 'skipped'] }, 1, 0] } },
          avgAlpha: { $avg: '$alpha' },
          lastAt: { $max: '$createdAt' },
        },
      },
      { $sort: { lastAt: -1 } },
      { $limit: 100 },
    ]);
    return {
      ok: true,
      data: rows.map((r) => ({
        eventId: r._id.eventId,
        type: r._id.type,
        asset: r._id.asset,
        alpha: r.avgAlpha ? Number(r.avgAlpha.toFixed(3)) : 0,
        wouldSendTo: r.wouldSendTo,
        filteredOut: r.filteredOut,
        lastAt: r.lastAt,
      })),
    };
  });

  app.get('/debug/dedupe', async () => {
    return { ok: true, data: pushRouter.getDedupeStats() };
  });

  app.post('/debug/dedupe/clear', async () => {
    const cleared = pushRouter.clearDedupeCache();
    return { ok: true, data: { cleared } };
  });

  // Force-fire morning/evening digest for testing.
  // POST /api/push/debug/digest { slot: 'morning' | 'evening' }
  app.post('/debug/digest', async (req) => {
    const body = (req.body || {}) as { slot?: 'morning' | 'evening' };
    if (!body.slot || !['morning', 'evening'].includes(body.slot)) {
      return { ok: false, error: 'slot must be "morning" or "evening"' };
    }
    const { forceFireDigest } = await import('./push_digest.js');
    // Also clear state for today's digest so it can re-fire on demand
    const today = new Date().toISOString().slice(0, 10);
    await PushStateModel.deleteOne({ eventId: `digest:${body.slot}:${today}` });
    await forceFireDigest(body.slot);
    return { ok: true, data: { slot: body.slot, fired: true } };
  });

  // ─── SELF-TEST TOOLING (before flipping channel=telegram) ───────────────────
  //
  // GET /api/push/debug/preview?type=FORMING&asset=BTC&role=user
  //   Returns the EXACT message text that WOULD be sent for a given event.
  //   No dedupe, no state, no delivery. Read-only render.
  //
  app.get('/debug/preview', async (req) => {
    const q = req.query as Record<string, string>;
    const ev: UnifiedEvent = {
      id: q.id || `preview_${Date.now()}`,
      category: (q.category as any) || 'retention',
      source: (q.source as any) || 'external',
      type: q.type || 'FORMING',
      asset: q.asset || 'BTC',
      stage: (q.stage as any) || 'FORMING',
      alpha: q.alpha ? Number(q.alpha) : 0.55,
      reason: q.reason || 'preview',
      timestamp: Date.now(),
    };
    const userMsg = buildMessage(ev, 'user');
    const adminMsg = buildMessage(ev, 'admin');
    return {
      ok: true,
      data: {
        event: ev,
        user: { text: userMsg.text, deepLink: userMsg.deepLink },
        admin: { text: adminMsg.text, deepLink: adminMsg.deepLink },
      },
    };
  });

  //
  // POST /api/push/debug/sample-pack
  //   body: { userId: "telegram:<chatId>" } OR { userId: "<existing push_subscribers.userId>" }
  //
  //   Resets the target user's counters + dedupe, then fires 5 curated events
  //   through the unified router. If PUSH_ENGINE_CHANNEL=telegram AND the user
  //   has a real telegramChatId, they WILL receive 5 Telegram messages.
  //
  //   Use this to self-test copy + deep links BEFORE flipping for real users.
  //
  app.post('/debug/sample-pack', async (req) => {
    const body = (req.body || {}) as { userId?: string };
    const userId = body.userId;
    if (!userId) return { ok: false, error: 'userId required' };

    const sub = await PushSubscriberModel.findOne({ userId }).lean();
    if (!sub) return { ok: false, error: `subscriber '${userId}' not found. Link via /start link_<token> or POST /api/push/subscribe first.` };

    // Reset counters so cooldown does not block the batch
    await PushSubscriberModel.updateOne(
      { userId },
      { $set: { lastPushAt: null, lastPushedAsset: null, pushCount24h: 0, pushCount24hResetAt: new Date() } },
    );
    pushRouter.clearDedupeCache();

    const ts = Date.now();
    const sample: UnifiedEvent[] = [
      {
        id: `sample_${ts}_1`, category: 'retention', source: 'external',
        type: 'FORMING', asset: 'BTC', stage: 'FORMING',
        alpha: 0.55, reason: 'sample-pack FORMING',
        timestamp: ts, meta: { sourcesCount: 7, velocity: 1.4, minutesOld: 22 },
      },
      {
        id: `sample_${ts}_2`, category: 'retention', source: 'external',
        type: 'CONFIRMED', asset: 'ETH', stage: 'CONFIRMED',
        alpha: 0.72, reason: 'sample-pack CONFIRMED',
        timestamp: ts, meta: { sourcesCount: 9, velocity: 2.3, minutesOld: 8 },
      },
      {
        id: `sample_${ts}_3`, category: 'retention', source: 'external',
        type: 'PERSONAL', asset: (sub.recentAssets && sub.recentAssets[0]) || 'SOL',
        stage: 'FORMING', alpha: 0.48, reason: 'sample-pack PERSONAL',
        timestamp: ts, meta: { sourcesCount: 4, minutesOld: 35, personal: true },
      },
      {
        id: `sample_${ts}_4`, category: 'retention', source: 'external',
        type: 'FORMING', asset: 'ARB', stage: 'FORMING',
        alpha: 0.62, reason: 'sample-pack FORMING mid-alpha ARB',
        timestamp: ts, meta: { sourcesCount: 4, velocity: 1.2, minutesOld: 18 },
      },
      {
        id: `sample_${ts}_5`, category: 'retention', source: 'external',
        type: 'CONFIRMED', asset: 'DOGE', stage: 'CONFIRMED',
        alpha: 0.68, reason: 'sample-pack CONFIRMED long-tail',
        timestamp: ts, meta: { sourcesCount: 6, velocity: 1.7, minutesOld: 12 },
      },
    ];

    // Temporarily lift daily-cap + cooldown for the target user by setting
    // counters to safe values BETWEEN each send.
    const results: any[] = [];
    for (const ev of sample) {
      await PushSubscriberModel.updateOne(
        { userId },
        { $set: { lastPushAt: null, pushCount24h: 0 } },
      );
      const res = await pushRouter.routeEvent(ev);
      results.push({
        id: ev.id,
        type: ev.type,
        asset: ev.asset,
        sent: res.sent,
        filteredOut: res.filteredOut,
        duplicated: res.duplicated,
      });
    }
    return { ok: true, data: { userId, channel: PUSH_ENGINE_CHANNEL, results } };
  });

  app.post('/subscribe', async (req) => {
    const body = (req.body || {}) as {
      userId?: string; role?: 'user' | 'admin'; telegramChatId?: string; expoToken?: string;
      recentAssets?: string[]; muted?: boolean;
    };
    if (!body.userId) return { ok: false, error: 'userId required' };
    const update: any = {};
    if (body.role !== undefined) update.role = body.role === 'admin' ? 'admin' : 'user';
    if (body.telegramChatId !== undefined) update.telegramChatId = body.telegramChatId;
    if (body.expoToken !== undefined) update.expoToken = body.expoToken;
    if (body.recentAssets !== undefined) update.recentAssets = body.recentAssets;
    if (body.muted !== undefined) update.muted = body.muted;

    const setOnInsert: any = {
      userId: body.userId,
      createdAt: new Date(),
      pushCount24hResetAt: new Date(),
      pushCount24h: 0,
    };
    // role must NOT appear in both $set and $setOnInsert (Mongo rejects that)
    if (update.role === undefined) setOnInsert.role = 'user';

    await PushSubscriberModel.updateOne(
      { userId: body.userId },
      { $set: update, $setOnInsert: setOnInsert },
      { upsert: true },
    );
    return { ok: true };
  });

  app.get('/subscribers', async (req) => {
    const q = req.query as Record<string, string>;
    const limit = Math.min(parseInt(q.limit || '50', 10), 500);
    const items = await PushSubscriberModel.find({}).sort({ createdAt: -1 }).limit(limit).lean();
    return { ok: true, data: items };
  });
}
