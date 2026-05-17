/**
 * Signal of the Moment  (Iteration A+)
 * =====================================
 *   score     = priority * 0.5 + watchersCount(log-scaled) * 0.2 + recency * 0.3
 *   hero lock = 2 minutes — a picked Hero stays sticky unless a CRITICAL
 *               signal arrives that beats the current one.
 *
 * Why sticky?
 *   Hero must feel like an anchor, not a ticker. If it flips every 30s,
 *   users stop trusting it. Lock is enforced at backend so Home / Feed /
 *   Edge / Notification Center ALL read the SAME hero id simultaneously.
 *
 *   Override rule:
 *     new CRITICAL   → replace immediately (even if locked)
 *     new HIGH over  → only after lock expires
 *     MEDIUM/LOW     → never replace locked hero
 */

import mongoose from 'mongoose';
import { resolvePriority, priorityLabel } from './priority.engine.js';

const LOOKBACK_MS = 6 * 60 * 60 * 1000;          // 6h window
const WATCHERS_LOG_DIVISOR = Math.log(200);
const HERO_LOCK_MS = 2 * 60 * 1000;              // 2 minute anchor lock

function recencyScore(ts: Date | string | number): number {
  const t = new Date(ts as any).getTime();
  const diff = Date.now() - t;
  if (diff <= 0) return 1;
  if (diff >= 60 * 60 * 1000) return 0;
  return 1 - diff / (60 * 60 * 1000);
}

export interface TopSignal {
  id: string;
  type: string;
  source: string;
  sourceLabel: string;
  sourceIcon: string;
  asset: string | null;
  title: string;
  body: string;
  icon: string;
  confidenceText: string | null;   // muted 1-line reinforcement under title ("8 sources aligned")
  sourcesCount: number;            // raw signal count contributing to this hero — used for "● based on X signals"
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  priorityScore: number;
  score: number;
  watchersCount: number;
  ctaLabel: string | null;
  deepLink: string | null;
  startParam: string | null;
  createdAt: string;
  ageMinutes: number;
  locked: boolean;                 // true when served from hero lock
  reason: { priority: number; watchers: number; recency: number };
}

function resolveSourceBadge(rawSource: string | null, pushType: string): { icon: string; label: string } {
  const s = String(rawSource || '').toLowerCase();
  const t = pushType.toUpperCase();
  if (t === 'LISTING') return { icon: '🚀', label: 'Listing' };
  if (t === 'EXPLOIT') return { icon: '⚠️', label: 'Exploit' };
  if (t === 'ETF') return { icon: '💎', label: 'ETF' };
  if (t === 'REGULATION') return { icon: '⚖️', label: 'Regulation' };
  if (t.startsWith('POLY_')) return { icon: '🎯', label: 'Polymarket' };
  if (t === 'NEWS') return { icon: '📰', label: 'News' };
  if (t === 'METABRAIN_SHIFT' || t === 'METABRAIN_CONVICTION_JUMP') return { icon: '🧠', label: 'MetaBrain' };
  if (t.startsWith('ACTOR_')) return { icon: '🐦', label: 'Actor' };
  if (t.startsWith('WHALE_')) return { icon: '🐋', label: 'Whale' };
  if (s === 'news') return { icon: '📰', label: 'News' };
  if (s === 'polymarket') return { icon: '🎯', label: 'Polymarket' };
  if (s === 'sentiment') return { icon: '📡', label: 'Sentiment' };
  if (s === 'actor') return { icon: '🐦', label: 'Actor' };
  if (s === 'whale') return { icon: '🐋', label: 'Whale' };
  if (s === 'metabrain') return { icon: '🧠', label: 'MetaBrain' };
  return { icon: '⚡', label: 'Signal' };
}

/**
 * Confidence string — one-liner printed under the Hero title.
 * Turns "a signal" into "an argument for a signal".
 *
 * Hard-coded per push type because product spec is explicit: "verbose, не универсальный".
 */
function buildConfidenceText(pushType: string, data: any): string | null {
  const t = String(pushType || '').toUpperCase();
  const sources = Number(data?.sourcesCount || 0);
  const movePct = Number(data?.movePct || 0);
  const usd = Number(data?.usdValue || data?.notionalUsd || 0);
  const mentions = Number(data?.mentionCount || 0);
  const influence = Number(data?.influenceScore || 0);
  const conviction = Number(data?.toConviction || data?.conviction || 0);

  if (t === 'LISTING')  return 'CEX liquidity expansion expected';
  if (t === 'EXPLOIT')  return 'systemic risk — watch for contagion';
  if (t === 'ETF')      return 'institutional flow incoming';
  if (t === 'REGULATION') return 'regulatory driver · re-pricing risk';

  if (t.startsWith('POLY_')) {
    if (movePct >= 5) return `${movePct.toFixed(0)}% market repricing · edge widening`;
    if (movePct > 0)  return `${movePct.toFixed(0)}% market repricing`;
    return 'prediction market dislocation';
  }

  if (t === 'NEWS' && sources >= 3)  return `${sources} sources aligned · narrative forming`;
  if (t === 'NEWS')                   return 'breaking narrative detected';

  if (t === 'ACTOR_NARRATIVE_PUSH')   return `${mentions || 'multiple'} aligned mentions · narrative building`;
  if (t === 'ACTOR_MENTION_SPIKE')    return influence >= 0.85
    ? 'high-influence mention spike'
    : 'attention rising across social flow';

  if (t === 'WHALE_EXCHANGE_INFLOW')  return usd >= 10_000_000
    ? 'large inflow · sell pressure risk'
    : 'inflow spike · potential sell pressure';
  if (t === 'WHALE_EXCHANGE_OUTFLOW') return usd >= 10_000_000
    ? 'large outflow · supply tightening'
    : 'outflow spike · supply tightening';

  if (t === 'METABRAIN_DECISION_SHIFT')   return 'system bias flipped · alignment building';
  if (t === 'METABRAIN_CONVICTION_JUMP')  return conviction > 0
    ? `conviction ${Math.round(conviction)}% · pressure building`
    : 'conviction jump detected';

  if (t === 'CONFIRMED' && sources >= 3) return `${sources} sources aligned`;
  if (t === 'PERSONAL')  return 'tracked asset · action window';
  if (t === 'FORMING')   return 'early setup · forming';

  return null;
}

// ══════════════════ Hero Lock ═════════════════════════════════════════════
async function readLock(): Promise<{ heroId: string; priority: number; at: number } | null> {
  try {
    const db = mongoose.connection.db;
    if (!db) return null;
    const col = db.collection('hero_state');
    const doc = await col.findOne({ _id: 'hero_lock' } as any);
    if (!doc) return null;
    if (Date.now() - Number(doc.at || 0) > HERO_LOCK_MS) return null;
    return { heroId: String(doc.heroId), priority: Number(doc.priority), at: Number(doc.at) };
  } catch { return null; }
}

async function writeLock(heroId: string, priority: number): Promise<void> {
  try {
    const db = mongoose.connection.db;
    if (!db) return;
    await db.collection('hero_state').updateOne(
      { _id: 'hero_lock' } as any,
      { $set: { heroId, priority, at: Date.now() } },
      { upsert: true },
    );
  } catch { /* silent */ }
}

// ══════════════════════════════════════════════════════════════════════════
export async function selectTopSignal(): Promise<TopSignal | null> {
  try {
    const col = mongoose.connection.db?.collection('notifications');
    if (!col) return null;
    const since = new Date(Date.now() - LOOKBACK_MS);

    const docs = await col.find({
      source: 'push-router',
      createdAt: { $gte: since },
    }).sort({ createdAt: -1 }).limit(40).toArray();

    if (!docs.length) return null;

    const scored = docs.map(d => {
      const pushType = d.data?.pushType || 'CONFIRMED';
      const priority = resolvePriority({ type: pushType, meta: d.data });
      const watchers = Number(d.data?.watchersCount || 0);
      const watchersNorm = watchers > 1
        ? Math.min(Math.log(watchers) / WATCHERS_LOG_DIVISOR, 1)
        : 0;
      const recency = recencyScore(d.createdAt);
      const score = (priority / 100) * 0.5 + watchersNorm * 0.2 + recency * 0.3;
      return { d, priority, watchers, watchersNorm, recency, score };
    });

    scored.sort((a, b) => b.score - a.score);

    // ── Hero Lock resolution ────────────────────────────────────────────
    // Keep the current Hero sticky for HERO_LOCK_MS. Only flip early if
    // a genuinely new CRITICAL (>=90) signal appeared AND the locked hero
    // was NOT already CRITICAL — we don't want two CRITICALs fighting.
    const lock = await readLock();
    const topCandidate = scored[0];
    if (!topCandidate) return null;

    let pick = topCandidate;
    let fromLock = false;

    if (lock) {
      const lockedStill = scored.find(x => String(x.d._id) === lock.heroId);
      if (lockedStill) {
        const isUpgradeToCritical = topCandidate.priority >= 90 && lock.priority < 90
          && topCandidate.d._id !== lockedStill.d._id;
        if (!isUpgradeToCritical) {
          pick = lockedStill;
          fromLock = true;
        }
      }
    }

    if (!fromLock) {
      await writeLock(String(pick.d._id), pick.priority);
    }

    const pushType = String(pick.d.data?.pushType || 'CONFIRMED').toUpperCase();
    const rawSource = pick.d.data?.rawSource || null;
    const badge = resolveSourceBadge(rawSource, pushType);
    const createdAt = pick.d.createdAt instanceof Date ? pick.d.createdAt : new Date(pick.d.createdAt);
    const ageMinutes = Math.max(0, Math.round((Date.now() - createdAt.getTime()) / 60000));

    return {
      id: String(pick.d._id),
      type: pushType,
      source: rawSource || pick.d.source || 'push-router',
      sourceLabel: badge.label,
      sourceIcon: badge.icon,
      asset: pick.d.data?.asset || null,
      title: pick.d.title_en || 'Signal',
      body: pick.d.body_en || '',
      icon: pick.d.icon || 'rocket',
      confidenceText: buildConfidenceText(pushType, pick.d.data),
      sourcesCount: Number(pick.d.data?.sourcesCount || 0),
      priority: priorityLabel(pick.priority),
      priorityScore: pick.priority,
      score: pick.score,
      watchersCount: pick.watchers,
      ctaLabel: pick.d.data?.ctaLabel || null,
      deepLink: pick.d.data?.deepLink || null,
      startParam: pick.d.data?.startParam || null,
      createdAt: createdAt.toISOString(),
      ageMinutes,
      locked: fromLock,
      reason: {
        priority: pick.priority,
        watchers: pick.watchersNorm,
        recency: pick.recency,
      },
    };
  } catch (err) {
    console.error('[signal-selector] failed:', err);
    return null;
  }
}
