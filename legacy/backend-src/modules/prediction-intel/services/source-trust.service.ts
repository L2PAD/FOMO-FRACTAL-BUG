/**
 * Source Trust Service
 *
 * Computes multi-dimensional trust scores for event sources.
 * Maps source identifiers to trust profiles with channel-specific weights.
 */
import {
  SourceProfile,
  SourceType,
  SourceTrustProfile,
  DEFAULT_SOURCE_PROFILES,
} from '../types/source.types.js';

/**
 * Known source profiles — manually curated high-value sources.
 * Extended dynamically by source learning (Stage 8).
 */
const KNOWN_SOURCES: Record<string, SourceProfile> = {
  sec: {
    sourceId: 'sec',
    name: 'SEC',
    type: 'official',
    trust: { officiality: 0.98, historicalAccuracy: 0.95, speed: 0.1, hypeFactor: 0.0, specificity: 0.95, resolutionRelevance: 0.95 },
  },
  blackrock: {
    sourceId: 'blackrock',
    name: 'BlackRock',
    type: 'official',
    trust: { officiality: 0.95, historicalAccuracy: 0.85, speed: 0.2, hypeFactor: 0.05, specificity: 0.9, resolutionRelevance: 0.85 },
  },
  binance: {
    sourceId: 'binance',
    name: 'Binance',
    type: 'official',
    trust: { officiality: 0.9, historicalAccuracy: 0.8, speed: 0.4, hypeFactor: 0.1, specificity: 0.85, resolutionRelevance: 0.7 },
  },
  coinbase: {
    sourceId: 'coinbase',
    name: 'Coinbase',
    type: 'official',
    trust: { officiality: 0.88, historicalAccuracy: 0.78, speed: 0.35, hypeFactor: 0.1, specificity: 0.8, resolutionRelevance: 0.65 },
  },
  cointelegraph: {
    sourceId: 'cointelegraph',
    name: 'CoinTelegraph',
    type: 'media',
    trust: { officiality: 0.2, historicalAccuracy: 0.58, speed: 0.8, hypeFactor: 0.6, specificity: 0.5, resolutionRelevance: 0.3 },
  },
  bloomberg: {
    sourceId: 'bloomberg',
    name: 'Bloomberg',
    type: 'media',
    trust: { officiality: 0.5, historicalAccuracy: 0.72, speed: 0.6, hypeFactor: 0.25, specificity: 0.7, resolutionRelevance: 0.55 },
  },
};

/**
 * Map notification_events source field to SourceType
 */
function resolveSourceType(source: string): SourceType {
  const s = source.toLowerCase();
  if (s === 'exchange') return 'exchange';
  if (s === 'onchain') return 'onchain';
  if (s === 'sentiment') return 'sentiment';
  if (s === 'system') return 'system';
  // Check known high-trust sources
  if (KNOWN_SOURCES[s]) return KNOWN_SOURCES[s].type;
  return 'noise';
}

/**
 * Get or build a SourceProfile for a given source identifier.
 */
export function getSourceProfile(sourceId: string): SourceProfile {
  const id = sourceId.toLowerCase();
  if (KNOWN_SOURCES[id]) return KNOWN_SOURCES[id];

  const type = resolveSourceType(id);
  return {
    sourceId: id,
    name: sourceId,
    type,
    trust: { ...DEFAULT_SOURCE_PROFILES[type] },
  };
}

/**
 * Compute a single trust score from a multi-dimensional profile.
 */
export function computeTrustScore(profile: SourceProfile): number {
  const t = profile.trust;
  const score =
    t.officiality * 0.25 +
    t.historicalAccuracy * 0.20 +
    t.specificity * 0.15 +
    t.resolutionRelevance * 0.20 -
    t.hypeFactor * 0.10 +
    t.speed * 0.10;

  return Math.max(0, Math.min(1, score));
}

/**
 * Get channel-specific weights for a source.
 * Different sources affect different channels differently.
 */
export function getChannelWeights(profile: SourceProfile): {
  probability: number;
  confidence: number;
  alignment: number;
  narrative: number;
} {
  const t = profile.trust;
  return {
    probability: t.resolutionRelevance,        // only resolution-relevant sources affect P
    confidence: t.historicalAccuracy * 0.7 + t.officiality * 0.3,
    alignment: t.specificity * 0.5 + t.officiality * 0.3 + t.historicalAccuracy * 0.2,
    narrative: t.hypeFactor * 0.6 + t.speed * 0.4,
  };
}
