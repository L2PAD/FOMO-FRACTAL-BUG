/**
 * Event Normalizer Service
 *
 * Converts raw events from different sources into a unified NormalizedEvent format.
 * Source-aware: applies correct trust scores and tiers from the registry.
 * Detects event type and sentiment hint from text.
 */

import { createHash } from 'crypto';
import type { RawFeedEvent, NormalizedEvent, SourceType } from '../types/event-feed.types.js';
import { sourceRegistryService } from './source-registry.service.js';
import { entityLinkerService } from './entity-linker.service.js';

// Event type keywords (reused from news-intelligence pattern)
const EVENT_TYPE_KEYWORDS: Record<string, string[]> = {
  hack:        ['hack', 'hacked', 'exploit', 'breach', 'stolen', 'attack', 'drained', 'vulnerability', 'rug'],
  listing:     ['listing', 'listed', 'delist', 'delisted', 'ipo', 'exchange listing'],
  etf:         ['etf', 'etf filing', 'etf approval', 's-1', 'grayscale etf', 'spot etf'],
  regulation:  ['sec', 'cftc', 'regulation', 'regulatory', 'lawsuit', 'legal', 'ban', 'fine', 'enforcement', 'compliance', 'court', 'bill', 'legislation', 'subpoena'],
  funding:     ['funding', 'raised', 'series a', 'series b', 'investment', 'venture', 'seed round', 'valuation'],
  partnership: ['partnership', 'partners', 'collaboration', 'integrate', 'integration', 'alliance'],
  macro:       ['fed', 'interest rate', 'inflation', 'gdp', 'treasury', 'recession', 'tariff', 'policy', 'jobs report', 'cpi', 'ppi'],
  upgrade:     ['upgrade', 'fork', 'mainnet', 'testnet', 'launch', 'v2', 'update', 'migration', 'deploy', 'airdrop'],
  whale:       ['whale', 'large transfer', 'accumulation', 'moved', 'dormant wallet'],
  price:       ['price', 'rally', 'crash', 'dump', 'pump', 'bull', 'bear', 'breakout', 'ath', 'all-time high', 'liquidation'],
  unlock:      ['unlock', 'vesting', 'token release', 'cliff', 'emission'],
};

const BULLISH_WORDS = [
  'bullish', 'rally', 'surge', 'soar', 'breakout', 'all-time high', 'ath',
  'approval', 'approved', 'adoption', 'accumulation', 'recovery', 'growth',
  'gain', 'breakthrough', 'partnership', 'launch',
];
const BEARISH_WORDS = [
  'bearish', 'crash', 'dump', 'plunge', 'hack', 'exploit', 'stolen',
  'ban', 'lawsuit', 'fine', 'sell-off', 'fear', 'liquidat', 'war',
  'layoff', 'decline', 'drop', 'loss', 'risk', 'fraud', 'rug',
];

class EventNormalizerService {
  /**
   * Normalize a raw event into a unified format.
   */
  normalize(raw: RawFeedEvent): NormalizedEvent {
    // Resolve source from registry
    const registeredSource = sourceRegistryService.resolveSource(raw.sourceName, raw.url);

    const sourceId = registeredSource?.id || raw.sourceId;
    const sourceName = registeredSource?.name || raw.sourceName;
    const sourceType: SourceType = registeredSource?.type || raw.sourceType;
    const sourceTier = registeredSource?.tier || raw.sourceTier;
    const trustScore = registeredSource?.trustScore || this.inferTrustScore(sourceTier);

    // Entity linking
    const { assets, entities } = entityLinkerService.link(
      raw.title, raw.text, raw.rawAssets, raw.rawEntities,
    );

    // Detect event type
    const eventType = this.detectEventType(`${raw.title} ${raw.text}`);

    // Detect sentiment
    const sentimentHint = this.detectSentiment(`${raw.title} ${raw.text}`);

    // Generate stable event ID
    const eventId = this.generateEventId(raw);

    return {
      eventId,
      sourceId,
      sourceName,
      sourceType,
      sourceTier,
      trustScore,
      title: raw.title.trim(),
      text: raw.text.trim(),
      url: raw.url,
      publishedAt: raw.publishedAt,
      entities,
      assets,
      eventType,
      sentimentHint,
    };
  }

  /**
   * Normalize a batch of raw events.
   */
  normalizeBatch(raws: RawFeedEvent[]): NormalizedEvent[] {
    return raws.map(r => this.normalize(r));
  }

  private detectEventType(text: string): string {
    const lower = text.toLowerCase();
    let bestType = 'market';
    let bestScore = 0;

    for (const [type, keywords] of Object.entries(EVENT_TYPE_KEYWORDS)) {
      let score = 0;
      for (const kw of keywords) {
        if (lower.includes(kw)) score++;
      }
      if (score > bestScore) {
        bestScore = score;
        bestType = type;
      }
    }

    return bestType;
  }

  private detectSentiment(text: string): string | null {
    const lower = text.toLowerCase();
    let bull = 0;
    let bear = 0;

    for (const w of BULLISH_WORDS) { if (lower.includes(w)) bull++; }
    for (const w of BEARISH_WORDS) { if (lower.includes(w)) bear++; }

    if (bull > bear && bull >= 2) return 'bullish';
    if (bear > bull && bear >= 2) return 'bearish';
    if (bull > 0 && bear === 0) return 'bullish';
    if (bear > 0 && bull === 0) return 'bearish';
    return null;
  }

  private inferTrustScore(tier: number): number {
    if (tier === 1) return 0.90;
    if (tier === 2) return 0.75;
    return 0.50;
  }

  private generateEventId(raw: RawFeedEvent): string {
    const hash = createHash('sha256')
      .update(`${raw.externalId || ''}:${raw.sourceId}:${raw.title}:${raw.publishedAt?.toISOString() || ''}`)
      .digest('hex')
      .slice(0, 16);
    return `ef_${hash}`;
  }
}

export const eventNormalizerService = new EventNormalizerService();
