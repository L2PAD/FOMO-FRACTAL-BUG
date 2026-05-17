/**
 * MetaBrain Emitter (Wave 4)
 * ===========================
 * Bridge: exchange_forecasts (MongoDB) → pushRouter. Only the FINAL decision
 * of the system makes it through — not every internal module state.
 *
 * Two push types:
 *   METABRAIN_DECISION_SHIFT  (CRITICAL) — decision changed AND confidence >= 0.7
 *   METABRAIN_CONVICTION_JUMP (HIGH)     — same direction but confidence +>= 0.20
 *
 * Watches for state transitions by comparing the CURRENT forecast against
 * the LAST emitted state per asset (stored in metabrain_state).
 *
 * Dedupe: asset + decision · 30 min window.
 */

import mongoose from 'mongoose';
import { pushRouter } from '../push-router.service.js';
import type { UnifiedEvent } from '../../../modules/push_engine/types.js';
import { buildMetabrainDecisionMessage } from '../builders/metabrain-decision.builder.js';
import { buildMetabrainConvictionMessage } from '../builders/metabrain-conviction.builder.js';

type ForecastDoc = {
  _id: any;
  asset?: string;
  symbol?: string;
  decision?: string;     // BUY | SELL | NEUTRAL | HOLD
  conviction?: number;   // 0..1
  confidence?: number;   // 0..1 (alias)
  createdAt?: string | Date;
};

const DEDUPE_WINDOW_MS = 30 * 60 * 1000;
const CONVICTION_JUMP_MIN = 0.20;         // +20%
const MIN_CONFIDENCE_FOR_SHIFT = 0.70;

function stateCol() { return mongoose.connection.db!.collection('metabrain_state'); }

async function readPrev(asset: string): Promise<{ decision: string; conviction: number } | null> {
  const doc = await stateCol().findOne({ _id: asset } as any);
  if (!doc) return null;
  return { decision: String(doc.decision), conviction: Number(doc.conviction || 0) };
}

async function writePrev(asset: string, decision: string, conviction: number) {
  await stateCol().updateOne(
    { _id: asset } as any,
    { $set: { decision, conviction, at: Date.now() } },
    { upsert: true },
  );
}

const emitDedupeCache = new Map<string, number>();
function shouldEmit(key: string): boolean {
  const now = Date.now();
  const last = emitDedupeCache.get(key);
  if (last && now - last < DEDUPE_WINDOW_MS) return false;
  emitDedupeCache.set(key, now);
  return true;
}

export async function emitMetabrainEvent(doc: ForecastDoc) {
  const asset = doc.asset || doc.symbol;
  if (!asset) return { eventId: `mb_${String(doc._id)}`, skipped: 'no_asset' };

  const next = String(doc.decision || '').toUpperCase();
  if (!next) return { eventId: `mb_${String(doc._id)}`, skipped: 'no_decision' };
  const nextConv = Number(doc.conviction ?? doc.confidence ?? 0);

  const prev = await readPrev(asset);
  await writePrev(asset, next, nextConv);  // always persist — we still need latest state

  // First observation of this asset — no shift to emit yet.
  if (!prev) return { eventId: `mb_${asset}_first`, skipped: 'no_prev_state' };

  // Decision shift — BUY ↔ SELL, BUY ↔ NEUTRAL, etc.
  if (prev.decision !== next && nextConv >= MIN_CONFIDENCE_FOR_SHIFT) {
    const key = `metabrain:${asset}:shift:${next}`;
    if (!shouldEmit(key)) {
      return { eventId: key, skipped: 'source_dedupe_30min' };
    }
    const event: UnifiedEvent = {
      id: `metabrain_shift_${asset}_${String(doc._id)}`,
      category: 'alert',
      source: 'metabrain',
      type: 'METABRAIN_DECISION_SHIFT',
      asset,
      stage: 'CONFIRMED',
      alpha: nextConv,
      reason: `${prev.decision}->${next}`,
      timestamp: doc.createdAt ? new Date(doc.createdAt).getTime() : Date.now(),
      meta: {
        from: prev.decision,
        to: next,
        toDecision: next,
        prevConviction: prev.conviction,
        conviction: nextConv,
      },
    };
    return pushRouter.routeEvent(event);
  }

  // Conviction jump — same direction, strong upward delta.
  const delta = nextConv - prev.conviction;
  if (prev.decision === next && delta >= CONVICTION_JUMP_MIN) {
    const key = `metabrain:${asset}:jump:${next}`;
    if (!shouldEmit(key)) {
      return { eventId: key, skipped: 'source_dedupe_30min' };
    }
    const event: UnifiedEvent = {
      id: `metabrain_jump_${asset}_${String(doc._id)}`,
      category: 'alert',
      source: 'metabrain',
      type: 'METABRAIN_CONVICTION_JUMP',
      asset,
      stage: 'CONFIRMED',
      alpha: nextConv,
      reason: `conviction_+${(delta * 100).toFixed(0)}%`,
      timestamp: doc.createdAt ? new Date(doc.createdAt).getTime() : Date.now(),
      meta: {
        decision: next,
        prevConviction: prev.conviction,
        conviction: nextConv,
        delta,
        convictionDelta: delta,
      },
    };
    return pushRouter.routeEvent(event);
  }

  return { eventId: `mb_${asset}_${String(doc._id)}`, skipped: 'no_transition' };
}

export function buildMetabrainMessage(event: UnifiedEvent, watchersCount?: number) {
  switch (String(event.type).toUpperCase()) {
    case 'METABRAIN_DECISION_SHIFT':  return buildMetabrainDecisionMessage({ event, watchersCount });
    case 'METABRAIN_CONVICTION_JUMP': return buildMetabrainConvictionMessage({ event, watchersCount });
    default: return null;
  }
}
