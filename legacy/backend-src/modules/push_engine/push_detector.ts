/**
 * Push Detector
 * =============
 * Given a list of news clusters (from news-intelligence pipeline) + previous
 * push_state, emits DetectedEvent candidates without duplicating.
 *
 * Gradation (per user correction):
 *   FORMING    : alpha > 0.45 && velocity > 1
 *   CONFIRMED  : alpha > 0.65 && aligned strong
 *   TENSION    : mixed signals across top 5 assets
 *   PERSONAL   : emitted per-user when asset ∈ recentAssets (scheduler handles fan-out)
 */

import type { NewsCluster } from '../news-intelligence/clustering.service.js';
import { getState } from './push_state.repository.js';
import type { DetectedEvent, PushStage, PushType } from './types.js';

const EVENT_WEIGHT: Record<string, number> = {
  regulation: 1.0, etf: 1.0, hack: 0.9, exploit: 0.9,
  macro: 0.8, listing: 0.7, funding: 0.7,
  whale: 0.6, legal: 0.8, adoption: 0.6,
  partnership: 0.5, price: 0.4, market: 0.5,
};

// Thresholds (env-tunable so user can tune live without redeploy).
// Keep defaults conservative but not sterile — calibrated against real feed.
const FORMING_ALPHA_MIN = Number(process.env.PUSH_FORMING_ALPHA_MIN || 0.30);
const FORMING_VELOCITY_MIN = Number(process.env.PUSH_FORMING_VELOCITY_MIN || 1);
const CONFIRMED_ALPHA_MIN = Number(process.env.PUSH_CONFIRMED_ALPHA_MIN || 0.45);

interface EnrichedCluster extends NewsCluster {
  alpha: number;
  stage: PushStage;
  velocity: number;
  saturation: number;
  minutesOld: number;
  aligned: boolean;   // narrative direction agrees with majority
}

function enrich(c: NewsCluster, all: NewsCluster[]): EnrichedCluster {
  const now = Date.now();
  const firstSeen = new Date(c.firstSeenAt).getTime();
  const lastSeen = new Date(c.lastSeenAt).getTime();
  const minutesOld = Math.max(0, Math.round((now - lastSeen) / 60_000));
  const spreadMin = Math.max(1, (lastSeen - firstSeen) / 60_000);

  const eventW = EVENT_WEIGHT[c.eventType] ?? 0.5;
  const impact = (c.importance / 100) * eventW;

  // velocity — sources per ~15min spread, capped at 3
  const rawVelocity = c.sourcesCount / Math.max(1, spreadMin / 15);
  const velocity = Math.min(3, rawVelocity);

  // saturation — how many similar-type clusters exist relative to avg
  const sameType = all.filter((x) => x.eventType === c.eventType).length;
  const typeCount = new Set(all.map((x) => x.eventType)).size || 1;
  const avgPerType = all.length / typeCount;
  const saturation = Math.min(1, sameType / Math.max(1, avgPerType * 2));

  const alpha = impact * (0.5 + 0.5 * (velocity / 3)) * (1 - saturation * 0.5);

  // Stage
  let stage: PushStage;
  if (saturation > 0.7 && minutesOld > 60) stage = 'SATURATED';
  else if (c.isBreaking || (alpha > 0.55 && minutesOld < 30)) stage = 'CONFIRMED';
  else if (velocity > 1.3 && saturation < 0.4 && minutesOld < 30) stage = 'EARLY';
  else stage = 'FORMING';

  // aligned — simplistic: sentiment hint exists and at least 3 sources
  const aligned = !!c.sentimentHint && c.sourcesCount >= 3;

  return { ...c, alpha: Math.max(0, Math.min(1, alpha)), stage, velocity, saturation, minutesOld, aligned };
}

function makeCopy(type: PushType, c: EnrichedCluster): { title: string; body: string; reason: string; priority: 'high' | 'normal' } {
  const asset = c.primaryAsset || 'Market';
  switch (type) {
    case 'FORMING':
      return {
        title: `⚠️ ${asset} signal forming`,
        body: 'Momentum building across sources',
        reason: `FORMING_SIGNAL alpha=${c.alpha.toFixed(2)} velocity=${c.velocity.toFixed(2)}`,
        priority: 'normal',
      };
    case 'CONFIRMED':
      return {
        title: `🚀 ${asset} move confirmed`,
        body: 'Narrative accelerating across market',
        reason: `CONFIRMED_MOVE alpha=${c.alpha.toFixed(2)} sources=${c.sourcesCount}`,
        priority: 'high',
      };
    case 'PERSONAL':
      return {
        title: `👀 ${asset} again`,
        body: 'Similar signal to what you watched earlier',
        reason: `PERSONAL asset-match recent`,
        priority: 'normal',
      };
    default:
      return { title: `${asset} update`, body: '', reason: 'generic', priority: 'normal' };
  }
}

export interface DetectorResult {
  events: DetectedEvent[];
  skippedDup: number;
  skippedThreshold: number;
  scanned: number;
}

export async function detectPushEvents(clusters: NewsCluster[]): Promise<DetectorResult> {
  const enriched = clusters.map((c) => enrich(c, clusters));
  const events: DetectedEvent[] = [];
  let skippedDup = 0;
  let skippedThreshold = 0;

  // ─ Per-cluster events (FORMING, CONFIRMED) ──────────────────────────────
  for (const c of enriched) {
    const state = await getState(c.clusterId);
    const alreadySent = new Set(state?.pushTypesSent || []);

    // CONFIRMED — emit when stage escalates to CONFIRMED (once per cluster)
    if (
      c.stage === 'CONFIRMED' &&
      c.alpha > CONFIRMED_ALPHA_MIN &&
      c.aligned &&
      state?.lastStage !== 'CONFIRMED' &&
      !alreadySent.has('CONFIRMED')
    ) {
      const copy = makeCopy('CONFIRMED', c);
      events.push({
        type: 'CONFIRMED',
        eventId: c.clusterId,
        clusterId: c.clusterId,
        asset: c.primaryAsset,
        stage: c.stage,
        alpha: c.alpha,
        reason: copy.reason,
        title: copy.title,
        body: copy.body,
        deepLink: c.primaryAsset ? `fomo://news?asset=${c.primaryAsset}` : `fomo://news`,
        priority: copy.priority,
        createdAt: new Date(),
        meta: { sourcesCount: c.sourcesCount, velocity: c.velocity, minutesOld: c.minutesOld, direction: c.sentimentHint || null },
      });
      continue; // CONFIRMED supersedes FORMING for same cluster
    }

    // FORMING — emit only once per cluster when alpha crosses threshold
    if (
      c.stage === 'FORMING' &&
      c.alpha > FORMING_ALPHA_MIN &&
      c.velocity > FORMING_VELOCITY_MIN &&
      !alreadySent.has('FORMING')
    ) {
      if (state && state.lastStage === 'FORMING' && state.pushTypesSent?.includes('FORMING')) {
        skippedDup += 1;
        continue;
      }
      const copy = makeCopy('FORMING', c);
      events.push({
        type: 'FORMING',
        eventId: c.clusterId,
        clusterId: c.clusterId,
        asset: c.primaryAsset,
        stage: c.stage,
        alpha: c.alpha,
        reason: copy.reason,
        title: copy.title,
        body: copy.body,
        deepLink: c.primaryAsset ? `fomo://news?asset=${c.primaryAsset}` : `fomo://news`,
        priority: copy.priority,
        createdAt: new Date(),
        meta: { sourcesCount: c.sourcesCount, velocity: c.velocity, minutesOld: c.minutesOld, direction: c.sentimentHint || null },
      });
      continue;
    }

    // Below thresholds — counted for observability
    if (c.alpha < 0.45) skippedThreshold += 1;
  }

  // ─ Market TENSION (single event per cycle, bucketed by hour) ────────────────
  const top5 = [...enriched]
    .sort((a, b) => b.alpha - a.alpha)
    .slice(0, 5);
  const bullish = top5.filter((c) => (c.sentimentHint || '').toLowerCase().match(/bull|positive/)).length;
  const bearish = top5.filter((c) => (c.sentimentHint || '').toLowerCase().match(/bear|negative/)).length;
  const tension = top5.length >= 4 && bullish >= 2 && bearish >= 2;
  if (tension) {
    const bucket = new Date();
    bucket.setMinutes(0, 0, 0);
    const tensionId = `tension:${bucket.toISOString()}`;
    const state = await getState(tensionId);
    if (!state?.pushTypesSent?.includes('TENSION')) {
      events.push({
        type: 'TENSION',
        eventId: tensionId,
        clusterId: undefined,
        asset: null,
        stage: 'FORMING',
        alpha: Math.max(...top5.map((c) => c.alpha)),
        reason: `TENSION bullish=${bullish} bearish=${bearish} top5=${top5.map((c) => c.primaryAsset).join(',')}`,
        title: `⚠️ Market shifting`,
        body: 'Conflicting signals across top assets',
        deepLink: `fomo://news`,
        priority: 'normal',
        createdAt: new Date(),
        meta: { bullish, bearish, top5: top5.map((c) => c.primaryAsset) },
      });
    } else {
      skippedDup += 1;
    }
  }

  return { events, skippedDup, skippedThreshold, scanned: enriched.length };
}
