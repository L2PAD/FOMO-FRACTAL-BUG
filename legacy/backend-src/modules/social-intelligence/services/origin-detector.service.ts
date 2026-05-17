/**
 * Layer 2 — Origin Detector
 *
 * Finds the first CREDIBLE signal, not just the earliest.
 * score = timeRank * 0.4 + trust * 0.4 + nonRepost * 0.2
 * If trust < 0.3 and better candidate exists → skip.
 */
import type { SocialEvent, SocialCluster } from '../types/social.types.js';
import type { AccountProfile } from '../types/account.types.js';

export type OriginResult = {
  originEventId: string | null;
  originAuthorId: string | null;
  originAuthorName: string | null;
  originTimestamp: number | null;
  confidence: number;
  trustScore: number;
};

function getAccountTrust(event: SocialEvent, profiles: Map<string, AccountProfile>): number {
  const profile = profiles.get(event.authorId);
  if (profile) return profile.trustScore;

  // Heuristic trust based on platform + source patterns
  if (event.platform === 'news') return 0.6;
  const name = (event.authorName || '').toLowerCase();
  if (name.includes('official') || name.includes('sec') || name.includes('binance')) return 0.8;
  if (name.includes('news') || name.includes('desk') || name.includes('bloomberg')) return 0.7;
  return 0.35;
}

export function detectOrigin(cluster: SocialCluster, profiles: Map<string, AccountProfile>): OriginResult {
  if (!cluster.events.length) {
    return { originEventId: null, originAuthorId: null, originAuthorName: null, originTimestamp: null, confidence: 0, trustScore: 0 };
  }

  const sorted = [...cluster.events].sort((a, b) => a.timestamp - b.timestamp);
  const earliest = sorted[0].timestamp;
  const latest = sorted[sorted.length - 1].timestamp;
  const timeRange = Math.max(1, latest - earliest);

  // Score each event
  const candidates = sorted
    .filter(ev => !ev.repostOfId) // exclude pure reposts
    .map(ev => {
      const trust = getAccountTrust(ev, profiles);
      const timeRank = 1 - ((ev.timestamp - earliest) / timeRange);
      const nonRepost = ev.repostOfId ? 0 : (ev.quotedEventId ? 0.5 : 1);
      const score = timeRank * 0.4 + trust * 0.4 + nonRepost * 0.2;
      return { event: ev, trust, score };
    })
    .sort((a, b) => b.score - a.score);

  if (!candidates.length) {
    // Fallback to earliest
    const ev = sorted[0];
    return {
      originEventId: ev.id,
      originAuthorId: ev.authorId,
      originAuthorName: ev.authorName,
      originTimestamp: ev.timestamp,
      confidence: 0.3,
      trustScore: getAccountTrust(ev, profiles),
    };
  }

  const best = candidates[0];

  // If best trust < 0.3 and there's a better trusted candidate, skip to it
  if (best.trust < 0.3 && candidates.length > 1) {
    const betterTrusted = candidates.find(c => c.trust >= 0.3);
    if (betterTrusted) {
      return {
        originEventId: betterTrusted.event.id,
        originAuthorId: betterTrusted.event.authorId,
        originAuthorName: betterTrusted.event.authorName,
        originTimestamp: betterTrusted.event.timestamp,
        confidence: Math.round(betterTrusted.score * 100) / 100,
        trustScore: Math.round(betterTrusted.trust * 100) / 100,
      };
    }
  }

  return {
    originEventId: best.event.id,
    originAuthorId: best.event.authorId,
    originAuthorName: best.event.authorName,
    originTimestamp: best.event.timestamp,
    confidence: Math.round(best.score * 100) / 100,
    trustScore: Math.round(best.trust * 100) / 100,
  };
}
