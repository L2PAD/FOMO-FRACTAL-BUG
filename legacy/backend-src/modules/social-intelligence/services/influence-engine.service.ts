/**
 * Layer 4 — Influence Engine
 *
 * Determines who is actually important (not followers, but accuracy + early signal).
 * influence = trust*0.4 + earlySignalScore*0.3 + amplificationPower*0.2 - hypeScore*0.1
 */
import type { SocialEvent, SocialCluster } from '../types/social.types.js';
import type { AccountProfile } from '../types/account.types.js';

export type InfluenceResult = {
  weightedInfluence: number;
  highQualityAmplifiers: string[];
  lowQualityAmplifiers: string[];
};

function computeInfluence(profile: AccountProfile): number {
  return (
    profile.trustScore * 0.4 +
    profile.earlySignalScore * 0.3 +
    profile.amplificationPower * 0.2 -
    profile.hypeScore * 0.1
  );
}

function inferProfile(event: SocialEvent): AccountProfile {
  const name = (event.authorName || '').toLowerCase();
  let sourceType: AccountProfile['sourceType'] = 'unknown';
  let trust = 0.3, accuracy = 0.3, early = 0.3, amp = 0.3, hype = 0.5;

  if (name.includes('official') || name.includes('sec') || name.includes('gov')) {
    sourceType = 'official'; trust = 0.9; accuracy = 0.85; early = 0.4; amp = 0.3; hype = 0.1;
  } else if (name.includes('binance') || name.includes('coinbase') || name.includes('kraken')) {
    sourceType = 'exchange'; trust = 0.85; accuracy = 0.8; early = 0.5; amp = 0.6; hype = 0.2;
  } else if (name.includes('bloomberg') || name.includes('reuters') || name.includes('coindesk') || name.includes('theblock')) {
    sourceType = 'media'; trust = 0.7; accuracy = 0.65; early = 0.5; amp = 0.7; hype = 0.3;
  } else if (name.includes('analyst') || name.includes('research')) {
    sourceType = 'analyst'; trust = 0.6; accuracy = 0.55; early = 0.6; amp = 0.4; hype = 0.3;
  } else if (event.platform === 'news') {
    sourceType = 'media'; trust = 0.55; accuracy = 0.5; early = 0.5; amp = 0.5; hype = 0.35;
  } else {
    sourceType = 'social'; trust = 0.3; accuracy = 0.3; early = 0.35; amp = 0.3; hype = 0.6;
  }

  return { accountId: event.authorId, name: event.authorName, sourceType, trustScore: trust, accuracyScore: accuracy, earlySignalScore: early, amplificationPower: amp, hypeScore: hype };
}

export function evaluateInfluence(cluster: SocialCluster, profiles: Map<string, AccountProfile>): InfluenceResult {
  const highQuality: string[] = [];
  const lowQuality: string[] = [];
  let totalInfluence = 0;
  const seen = new Set<string>();

  for (const ev of cluster.events) {
    if (seen.has(ev.authorId)) continue;
    seen.add(ev.authorId);

    const profile = profiles.get(ev.authorId) || inferProfile(ev);
    const inf = computeInfluence(profile);

    if (inf > 0.5) highQuality.push(ev.authorName);
    else lowQuality.push(ev.authorName);

    totalInfluence += inf;
  }

  const avgInfluence = seen.size > 0 ? totalInfluence / seen.size : 0;

  return {
    weightedInfluence: Math.round(Math.min(1, avgInfluence) * 100) / 100,
    highQualityAmplifiers: highQuality.slice(0, 5),
    lowQualityAmplifiers: lowQuality.slice(0, 5),
  };
}
