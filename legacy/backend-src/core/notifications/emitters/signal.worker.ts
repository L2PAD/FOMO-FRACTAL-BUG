/**
 * Signal Auto-Emit Worker
 * ========================
 * Polls sentiment_events + prediction_alerts every N seconds and emits
 * ONLY NEW records through the respective emitters. Makes the push system
 * a production pipeline (not a manual test endpoint).
 *
 * Uses `signal_worker_state` collection to track last processed _id per source
 * (Mongo ObjectId timestamps monotonic — good enough for polling).
 *
 * Disabled by default. Enable with env `SIGNAL_WORKER_ENABLED=true`.
 */

import mongoose from 'mongoose';
import { emitSentimentEvent } from './sentiment.emitter.js';
import { emitPolymarketAlert } from './polymarket.emitter.js';
import { emitNewsArticle } from './news.emitter.js';
import { emitActorEvent } from './actor.emitter.js';
import { emitWhaleEvent } from './whale.emitter.js';
import { emitMetabrainEvent } from './metabrain.emitter.js';
import { pollMissedSignals } from './missed.emitter.js';

const POLL_INTERVAL_MS = Number(process.env.SIGNAL_WORKER_POLL_MS || 30000); // 30s
const ENABLED = String(process.env.SIGNAL_WORKER_ENABLED || '').toLowerCase() === 'true';
const BATCH_LIMIT = 25;  // protect router from floods

// Wave 1: sentiment event types we push
const SENTIMENT_KINDS = ['listing', 'exploit', 'etf', 'regulation', 'legal'];

// Wave 2: prediction alert types we push
const POLY_KINDS = ['new_mispricing', 'repricing_started', 'repricing_change', 'overheated', 'thesis_weakened', 'entry_window_closed'];

interface WorkerState {
  _id: string;
  lastProcessedTimestamp?: Date;
  updatedAt?: Date;
}

async function getWorkerState(source: string): Promise<WorkerState | null> {
  const col = mongoose.connection.db?.collection('signal_worker_state');
  if (!col) return null;
  return (await col.findOne({ _id: source as any })) as WorkerState | null;
}

async function setWorkerState(source: string, ts: Date) {
  const col = mongoose.connection.db?.collection('signal_worker_state');
  if (!col) return;
  await col.updateOne(
    { _id: source as any },
    { $set: { lastProcessedTimestamp: ts, updatedAt: new Date() } },
    { upsert: true },
  );
}

async function pollSentiment(): Promise<{ processed: number; skipped: number }> {
  const col = mongoose.connection.db?.collection('sentiment_events');
  if (!col) return { processed: 0, skipped: 0 };
  const state = await getWorkerState('sentiment_events');
  const since = state?.lastProcessedTimestamp || new Date(Date.now() - 60 * 60 * 1000); // default: 1h ago

  const docs = await col.find({
    eventType: { $in: SENTIMENT_KINDS },
    createdAt: { $gt: since },
  }).sort({ createdAt: 1 }).limit(BATCH_LIMIT).toArray();

  let processed = 0;
  let skipped = 0;
  let maxTs = since;
  for (const d of docs) {
    try {
      const res = await emitSentimentEvent(d as any);
      if ((res as any)?.sent > 0) processed++;
      else skipped++;
    } catch (err) {
      console.error('[signal-worker] sentiment emit failed:', err);
      skipped++;
    }
    if (d.createdAt && new Date(d.createdAt) > maxTs) maxTs = new Date(d.createdAt);
  }
  if (docs.length > 0) await setWorkerState('sentiment_events', maxTs);
  return { processed, skipped };
}

async function pollPolymarket(): Promise<{ processed: number; skipped: number }> {
  const col = mongoose.connection.db?.collection('prediction_alerts');
  if (!col) return { processed: 0, skipped: 0 };
  const state = await getWorkerState('prediction_alerts');
  const since = state?.lastProcessedTimestamp || new Date(Date.now() - 60 * 60 * 1000);

  // prediction_alerts uses `created_at` (string) as ISO; Mongo compares strings lexicographically
  const sinceIso = (since instanceof Date ? since : new Date(since)).toISOString();

  const docs = await col.find({
    alert_type: { $in: POLY_KINDS },
    created_at: { $gt: sinceIso },
  }).sort({ created_at: 1 }).limit(BATCH_LIMIT).toArray();

  let processed = 0;
  let skipped = 0;
  let maxTs = sinceIso;
  for (const d of docs) {
    try {
      const res = await emitPolymarketAlert(d as any);
      if ((res as any)?.sent > 0) processed++;
      else skipped++;
    } catch (err) {
      console.error('[signal-worker] polymarket emit failed:', err);
      skipped++;
    }
    if (d.created_at && String(d.created_at) > maxTs) maxTs = String(d.created_at);
  }
  if (docs.length > 0) await setWorkerState('prediction_alerts', new Date(maxTs));
  return { processed, skipped };
}

/**
 * Wave 3: news_articles polling. Classifier acts as the HARD gate — most
 * rows are rejected silently. Global quota (3 per 6h) enforced inside emitter.
 */
async function pollNews(): Promise<{ processed: number; skipped: number }> {
  const col = mongoose.connection.db?.collection('news_articles');
  if (!col) return { processed: 0, skipped: 0 };
  const state = await getWorkerState('news_articles');
  const since = state?.lastProcessedTimestamp || new Date(Date.now() - 60 * 60 * 1000);

  // news_articles.created_at is ISO string with timezone (+00:00); compare lexicographically
  const sinceIso = (since instanceof Date ? since : new Date(since)).toISOString();

  const docs = await col.find({
    created_at: { $gt: sinceIso },
    // prefilter at DB level: only tier A/B news pass through to the emitter
    tier: { $in: ['A', 'B'] },
  }).sort({ created_at: 1 }).limit(BATCH_LIMIT).toArray();

  let processed = 0;
  let skipped = 0;
  let maxTs = sinceIso;
  for (const d of docs) {
    try {
      const res = await emitNewsArticle(d as any);
      if ((res as any)?.sent > 0) processed++;
      else skipped++;
    } catch (err) {
      console.error('[signal-worker] news emit failed:', err);
      skipped++;
    }
    if (d.created_at && String(d.created_at) > maxTs) maxTs = String(d.created_at);
  }
  if (docs.length > 0) await setWorkerState('news_articles', new Date(maxTs));
  return { processed, skipped };
}

// ═══════════════════════════════════════════════════════════════════════════
// Wave 4: Actor / Whale / MetaBrain — 3 new pollers
// ═══════════════════════════════════════════════════════════════════════════

/** Poll actor_signal_events → actor emitter (mention spike / narrative push). */
async function pollActor(): Promise<{ processed: number; skipped: number }> {
  const col = mongoose.connection.db?.collection('actor_signal_events');
  if (!col) return { processed: 0, skipped: 0 };
  const state = await getWorkerState('actor_signal_events');
  const since = state?.lastProcessedTimestamp || new Date(Date.now() - 60 * 60 * 1000);

  const docs = await col.find({
    createdAt: { $gt: since },
  }).sort({ createdAt: 1 }).limit(BATCH_LIMIT).toArray();

  let processed = 0;
  let skipped = 0;
  let maxTs = since;
  for (const d of docs) {
    try {
      const res = await emitActorEvent(d as any);
      if ((res as any)?.sent > 0) processed++;
      else skipped++;
    } catch (err) {
      console.error('[signal-worker] actor emit failed:', err);
      skipped++;
    }
    const t = d.createdAt ? new Date(d.createdAt as any) : maxTs;
    if (t > maxTs) maxTs = t;
  }
  if (docs.length > 0) await setWorkerState('actor_signal_events', maxTs);
  return { processed, skipped };
}

/** Poll exchange_whale_events → whale emitter (inflow/outflow spike $5M+). */
async function pollWhale(): Promise<{ processed: number; skipped: number }> {
  const col = mongoose.connection.db?.collection('exchange_whale_events');
  if (!col) return { processed: 0, skipped: 0 };
  const state = await getWorkerState('exchange_whale_events');
  const since = state?.lastProcessedTimestamp || new Date(Date.now() - 60 * 60 * 1000);

  const docs = await col.find({
    createdAt: { $gt: since },
  }).sort({ createdAt: 1 }).limit(BATCH_LIMIT).toArray();

  let processed = 0;
  let skipped = 0;
  let maxTs = since;
  for (const d of docs) {
    try {
      const res = await emitWhaleEvent(d as any);
      if ((res as any)?.sent > 0) processed++;
      else skipped++;
    } catch (err) {
      console.error('[signal-worker] whale emit failed:', err);
      skipped++;
    }
    const t = d.createdAt ? new Date(d.createdAt as any) : maxTs;
    if (t > maxTs) maxTs = t;
  }
  if (docs.length > 0) await setWorkerState('exchange_whale_events', maxTs);
  return { processed, skipped };
}

/** Poll exchange_forecasts → metabrain emitter (decision shift / conviction jump). */
async function pollMetabrain(): Promise<{ processed: number; skipped: number }> {
  const col = mongoose.connection.db?.collection('exchange_forecasts');
  if (!col) return { processed: 0, skipped: 0 };
  const state = await getWorkerState('exchange_forecasts');
  const since = state?.lastProcessedTimestamp || new Date(Date.now() - 60 * 60 * 1000);

  const docs = await col.find({
    createdAt: { $gt: since },
  }).sort({ createdAt: 1 }).limit(BATCH_LIMIT).toArray();

  let processed = 0;
  let skipped = 0;
  let maxTs = since;
  for (const d of docs) {
    try {
      const res = await emitMetabrainEvent(d as any);
      if ((res as any)?.sent > 0) processed++;
      else skipped++;
    } catch (err) {
      console.error('[signal-worker] metabrain emit failed:', err);
      skipped++;
    }
    const t = d.createdAt ? new Date(d.createdAt as any) : maxTs;
    if (t > maxTs) maxTs = t;
  }
  if (docs.length > 0) await setWorkerState('exchange_forecasts', maxTs);
  return { processed, skipped };
}

let handle: NodeJS.Timeout | null = null;
let missedHandle: NodeJS.Timeout | null = null;
let running = false;

const MISSED_POLL_INTERVAL_MS = Number(process.env.MISSED_POLL_INTERVAL_MS || 15 * 60 * 1000);   // 15 min
const MISSED_ENABLED = process.env.MISSED_SIGNALS_ENABLED !== 'false';  // on by default

export function startSignalWorker() {
  if (!ENABLED) {
    console.log('[signal-worker] disabled (SIGNAL_WORKER_ENABLED != true)');
    return;
  }
  if (handle) return;
  console.log(`[signal-worker] started · poll every ${POLL_INTERVAL_MS}ms`);
  const tick = async () => {
    if (running) return;
    running = true;
    try {
      const [s, p, n, a, w, m] = await Promise.all([
        pollSentiment(), pollPolymarket(), pollNews(),
        pollActor(), pollWhale(), pollMetabrain(),
      ]);
      const total = s.processed + p.processed + n.processed + a.processed + w.processed + m.processed;
      if (total > 0) {
        console.log(
          `[signal-worker] sentiment:${s.processed} polymarket:${p.processed} news:${n.processed} `
          + `actor:${a.processed} whale:${w.processed} metabrain:${m.processed}`,
        );
      }
    } finally {
      running = false;
    }
  };
  setTimeout(tick, 5000);
  handle = setInterval(tick, POLL_INTERVAL_MS);

  // ── MISSED retention loop — runs on its own slow clock (every 15 min) ──
  // Separate clock because it's expensive (per-asset user fan-out) and
  // doesn't need the fast cadence of new-signal polling.
  if (MISSED_ENABLED) {
    console.log(`[missed-worker] started · poll every ${MISSED_POLL_INTERVAL_MS}ms`);
    const missedTick = async () => {
      try {
        const r = await pollMissedSignals();
        if (r.processed > 0) {
          console.log(`[missed-worker] emitted:${r.processed} skipped:${r.skipped}`);
        }
      } catch (err) {
        console.error('[missed-worker] tick failed:', err);
      }
    };
    // First run after 90s so fresh signals have a chance to land first
    setTimeout(missedTick, 90_000);
    missedHandle = setInterval(missedTick, MISSED_POLL_INTERVAL_MS);
  } else {
    console.log('[missed-worker] disabled (MISSED_SIGNALS_ENABLED=false)');
  }
}

export function stopSignalWorker() {
  if (handle) clearInterval(handle);
  if (missedHandle) clearInterval(missedHandle);
  handle = null;
  missedHandle = null;
  console.log('[signal-worker] stopped');
}

export async function runSignalWorkerOnce(): Promise<{
  sentiment: any; polymarket: any; news: any;
  actor: any; whale: any; metabrain: any; missed: any;
}> {
  const [s, p, n, a, w, m, missed] = await Promise.all([
    pollSentiment(), pollPolymarket(), pollNews(),
    pollActor(), pollWhale(), pollMetabrain(),
    pollMissedSignals(),
  ]);
  return { sentiment: s, polymarket: p, news: n, actor: a, whale: w, metabrain: m, missed };
}
