/**
 * Analytics Client (Growth Layer G1)
 * ==================================
 * Fire-and-forget tracking for 10 core events:
 *   signal_hero_view, signal_hero_tap,
 *   edge_open, edge_paywall_view, edge_paywall_click,
 *   missed_seen, missed_click, return_after_missed,
 *   share_click, share_complete
 *
 * Strategy:
 *  - Attempt direct POST to /api/mobile/analytics/track
 *  - On failure, push to in-memory queue; flush on next event (1-step retry)
 *  - Batch endpoint used when queue > 3 events
 *  - Dedupe by (event + signalId + 5s window)
 */
import { api } from './api/api-client';

export type AnalyticsEvent =
  | 'signal_hero_view'
  | 'signal_hero_tap'
  | 'edge_open'
  | 'edge_paywall_view'
  | 'edge_paywall_click'
  | 'missed_seen'
  | 'missed_click'
  | 'return_after_missed'
  | 'share_click'
  | 'share_complete';

export interface TrackPayload {
  signalId?: string | null;
  asset?: string | null;
  source?: string | null;
  priority?: string | null;
  context?: Record<string, any>;
}

interface QueuedEvent extends TrackPayload {
  event: AnalyticsEvent;
  clientTs: number;
}

// ── Dedupe cache ──────────────────────────────────────────────
const dedupe = new Map<string, number>();
const DEDUPE_WINDOW_MS = 5_000;

function dedupeKey(ev: AnalyticsEvent, p: TrackPayload): string {
  return `${ev}|${p.signalId || ''}|${p.asset || ''}|${(p.context as any)?.screen || ''}`;
}

function shouldDrop(ev: AnalyticsEvent, p: TrackPayload): boolean {
  const key = dedupeKey(ev, p);
  const last = dedupe.get(key) || 0;
  const now = Date.now();
  if (now - last < DEDUPE_WINDOW_MS) return true;
  dedupe.set(key, now);
  // Prune map when too large
  if (dedupe.size > 200) {
    const cutoff = now - DEDUPE_WINDOW_MS * 4;
    for (const [k, v] of dedupe) {
      if (v < cutoff) dedupe.delete(k);
    }
  }
  return false;
}

// ── Retry queue ───────────────────────────────────────────────
const queue: QueuedEvent[] = [];
const MAX_QUEUE = 30;

async function flushQueue(): Promise<void> {
  if (!queue.length) return;
  const batch = queue.splice(0, queue.length);
  try {
    await api.post('/api/mobile/analytics/batch', { events: batch });
  } catch {
    // Put back (up to MAX_QUEUE)
    queue.unshift(...batch.slice(0, Math.max(0, MAX_QUEUE - queue.length)));
  }
}

/**
 * Fire-and-forget event track.
 * Never throws. Never blocks UI.
 */
export function track(event: AnalyticsEvent, payload: TrackPayload = {}): void {
  if (shouldDrop(event, payload)) return;

  const evt: QueuedEvent = {
    event,
    clientTs: Date.now(),
    signalId: payload.signalId || null,
    asset: payload.asset || null,
    source: payload.source || null,
    priority: payload.priority || null,
    context: payload.context || {},
  };

  // Direct send first; queue only on failure.
  api
    .post('/api/mobile/analytics/track', evt)
    .then(() => {
      if (queue.length) void flushQueue();
    })
    .catch(() => {
      if (queue.length < MAX_QUEUE) queue.push(evt);
    });
}

/** Convenience: track with explicit error suppression (already silent). */
export const Analytics = { track };
export default Analytics;
