/**
 * Event Interpreter — the brain of Stage 6.
 *
 * Takes an enriched event + source profile + market context,
 * and produces a multi-channel interpreted signal with:
 * - relevance, direction, confidence
 * - separate probability / confidence / alignment impacts
 * - novelty, already-priced detection
 * - smart human-readable driver text
 *
 * KEY RULE: A bullish news != +probability.
 * News affects DIFFERENT channels differently:
 * - probability: ONLY if resolution-relevant
 * - confidence: if source is trustworthy
 * - alignment: if it confirms other signals
 * - narrative: if it drives hype/attention
 */
import type { EnrichedEvent, InterpretedEvent } from '../types/event.types.js';
import type { SourceProfile } from '../types/source.types.js';
import { computeTrustScore, getChannelWeights } from './source-trust.service.js';
import { computeNovelty } from './novelty.service.js';

type MarketContext = {
  marketId: string;
  asset: string;
  entities: string[];
  eventType: string;
  currentProb: number;
  move6h: number;
  move24h: number;
  volume: number;
  repricingState?: string;
};

/**
 * Interpret a single enriched event against a market context.
 */
export function interpretEvent(
  event: EnrichedEvent,
  source: SourceProfile,
  context: MarketContext,
  recentTexts: string[],
): InterpretedEvent {
  const trustScore = computeTrustScore(source);
  const channels = getChannelWeights(source);
  const novelty = computeNovelty(event.text, recentTexts);
  const relevance = computeRelevance(event, context);
  const direction = computeDirection(event, context);
  const alreadyPriced = computeAlreadyPriced(context);

  // Signal confidence split
  const sourceConfidence = trustScore;
  const interpretationConfidence = computeInterpretationConfidence(event, context);
  const marketRelevanceConfidence = relevance;

  const overallConfidence = (
    sourceConfidence * 0.4 +
    interpretationConfidence * 0.3 +
    marketRelevanceConfidence * 0.3
  );

  // Impact computation — applies channel weights and dampening
  const noveltyDampen = novelty;
  const pricedDampen = 1 - alreadyPriced;
  const dirSign = direction === 'bullish' ? 1 : direction === 'bearish' ? -1 : 0;

  const probImpact = channels.probability * 0.15 * noveltyDampen * pricedDampen * dirSign;
  const confImpact = channels.confidence * 0.12 * noveltyDampen * Math.abs(dirSign || 0.3);
  const alignImpact = channels.alignment * 0.10 * noveltyDampen * pricedDampen * dirSign;

  // Smart driver generation
  const smartDriver = buildSmartDriver(event, source, {
    direction,
    relevance,
    novelty,
    alreadyPriced,
    trustScore,
  });

  return {
    eventId: event.id,
    relevance,
    direction,
    confidence: overallConfidence,

    impact: {
      probability: round(probImpact),
      confidence: round(confImpact),
      alignment: round(alignImpact),
    },

    meta: {
      novelty,
      alreadyPriced,
      timeHorizon: inferTimeHorizon(event),
      resolutionRelevance: channels.probability,
      narrativeRelevance: channels.narrative,
    },

    signalConfidence: {
      sourceConfidence: round(sourceConfidence),
      interpretationConfidence: round(interpretationConfidence),
      marketRelevanceConfidence: round(marketRelevanceConfidence),
    },

    smartDriver,
  };
}

// ---- Private helpers ----

function computeRelevance(event: EnrichedEvent, ctx: MarketContext): number {
  // Entity overlap = strong relevance
  const eventEntities = new Set(event.entities.map(e => e.toUpperCase()));
  const ctxEntities = new Set(ctx.entities.map(e => e.toUpperCase()));

  let entityOverlap = 0;
  for (const e of eventEntities) {
    if (ctxEntities.has(e)) entityOverlap++;
  }

  // Asset match
  const assetMatch = event.asset?.toUpperCase() === ctx.asset?.toUpperCase() ? 0.4 : 0;

  // Tag relevance
  const tagRelevance = computeTagRelevance(event.tags, ctx.eventType);

  const raw = entityOverlap * 0.35 + assetMatch + tagRelevance * 0.25;
  return Math.max(0, Math.min(1, raw));
}

function computeTagRelevance(tags: string[], eventType: string): number {
  if (eventType.includes('etf') && tags.includes('etf')) return 1;
  if (eventType.includes('listing') && tags.includes('listing')) return 1;
  if (eventType.includes('launch') && tags.includes('launch')) return 1;
  if (eventType.includes('threshold') && (tags.includes('bullish') || tags.includes('bearish'))) return 0.6;
  if (tags.includes('whale')) return 0.5;
  return 0.1;
}

function computeDirection(event: EnrichedEvent, ctx: MarketContext): 'bullish' | 'bearish' | 'neutral' {
  const text = event.text.toLowerCase();
  const payload = event.payload || {};

  // Explicit direction in payload
  if (payload.direction === 'bullish' || payload.direction === 'bearish') {
    return payload.direction;
  }

  // Keyword-based direction
  const bullishKw = ['bullish', 'inflow', 'approval', 'buy', 'accumulate', 'filed', 'launch'];
  const bearishKw = ['bearish', 'outflow', 'delay', 'sell', 'distribute', 'reject', 'warning', 'risk'];

  const bullishHits = bullishKw.filter(kw => text.includes(kw)).length;
  const bearishHits = bearishKw.filter(kw => text.includes(kw)).length;

  if (bullishHits > bearishHits) return 'bullish';
  if (bearishHits > bullishHits) return 'bearish';
  return 'neutral';
}

function computeAlreadyPriced(ctx: MarketContext): number {
  const move = Math.abs(ctx.move6h || 0);
  if (move > 0.15) return 0.8;
  if (move > 0.10) return 0.6;
  if (move > 0.05) return 0.4;
  if (move > 0.02) return 0.2;
  return 0.1;
}

function computeInterpretationConfidence(event: EnrichedEvent, ctx: MarketContext): number {
  let conf = 0.3;  // base

  // More entities matched = higher confidence
  const eventEntities = new Set(event.entities.map(e => e.toUpperCase()));
  const ctxEntities = new Set(ctx.entities.map(e => e.toUpperCase()));
  for (const e of eventEntities) {
    if (ctxEntities.has(e)) conf += 0.15;
  }

  // Specific severity
  if (event.severity === 'high') conf += 0.1;

  // Has payload with structured data
  if (event.payload && Object.keys(event.payload).length > 2) conf += 0.1;

  return Math.min(1, conf);
}

function inferTimeHorizon(event: EnrichedEvent): 'short' | 'mid' | 'long' {
  const text = event.text.toLowerCase();
  if (text.includes('now') || text.includes('today') || text.includes('urgent')) return 'short';
  if (text.includes('week') || text.includes('month')) return 'mid';
  return 'short';  // default for market events
}

function buildSmartDriver(
  event: EnrichedEvent,
  source: SourceProfile,
  info: { direction: string; relevance: number; novelty: number; alreadyPriced: number; trustScore: number },
): string {
  const parts: string[] = [];

  // Source quality
  if (info.trustScore >= 0.7) parts.push(`High-trust ${source.type} source (${source.name})`);
  else if (info.trustScore >= 0.4) parts.push(`${source.type} source (${source.name})`);
  else parts.push(`Low-trust ${source.type} source`);

  // What it says
  parts.push(`reports ${info.direction} signal`);

  // Key insight
  if (info.novelty < 0.3) parts.push('but this is largely repeated info');
  else if (info.novelty >= 0.8) parts.push('with novel information');

  if (info.alreadyPriced > 0.6) parts.push('and market has likely priced this in');
  else if (info.alreadyPriced < 0.2) parts.push('and market has not yet reacted');

  if (info.relevance < 0.3) parts.push('(low market relevance)');

  return parts.join(', ');
}

function round(n: number): number {
  return Math.round(n * 10000) / 10000;
}
