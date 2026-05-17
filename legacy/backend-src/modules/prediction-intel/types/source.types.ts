/**
 * Source Trust Types
 */
export type SourceType =
  | 'official'    // SEC, Binance announcements, BlackRock filings
  | 'primary'     // Company blogs, official filings
  | 'high_signal' // Verified analysts, known insiders
  | 'media'       // CoinTelegraph, Bloomberg, Reuters
  | 'social'      // Twitter, Reddit
  | 'exchange'    // Exchange-generated signals (internal)
  | 'onchain'     // Onchain-derived signals (internal)
  | 'sentiment'   // Sentiment-derived signals (internal)
  | 'system'      // System-generated events
  | 'noise'       // Unverified, low-quality

export type SourceTrustProfile = {
  officiality: number        // 0-1: how official is this source
  historicalAccuracy: number // 0-1: how often was it right
  speed: number              // 0-1: how early does it report
  hypeFactor: number         // 0-1: how much hype does it generate
  specificity: number        // 0-1: how specific are its claims
  resolutionRelevance: number // 0-1: does it affect market resolution
}

export type SourceProfile = {
  sourceId: string
  name: string
  type: SourceType
  trust: SourceTrustProfile
}

/**
 * Default source profiles for known source types.
 * These serve as fallbacks when no specific source is identified.
 */
export const DEFAULT_SOURCE_PROFILES: Record<SourceType, SourceTrustProfile> = {
  official: {
    officiality: 0.95,
    historicalAccuracy: 0.85,
    speed: 0.3,
    hypeFactor: 0.05,
    specificity: 0.9,
    resolutionRelevance: 0.9,
  },
  primary: {
    officiality: 0.7,
    historicalAccuracy: 0.7,
    speed: 0.5,
    hypeFactor: 0.1,
    specificity: 0.75,
    resolutionRelevance: 0.6,
  },
  high_signal: {
    officiality: 0.3,
    historicalAccuracy: 0.65,
    speed: 0.8,
    hypeFactor: 0.2,
    specificity: 0.6,
    resolutionRelevance: 0.3,
  },
  media: {
    officiality: 0.2,
    historicalAccuracy: 0.55,
    speed: 0.7,
    hypeFactor: 0.5,
    specificity: 0.45,
    resolutionRelevance: 0.25,
  },
  social: {
    officiality: 0.05,
    historicalAccuracy: 0.3,
    speed: 0.9,
    hypeFactor: 0.75,
    specificity: 0.2,
    resolutionRelevance: 0.05,
  },
  exchange: {
    officiality: 0.4,
    historicalAccuracy: 0.6,
    speed: 0.5,
    hypeFactor: 0.1,
    specificity: 0.7,
    resolutionRelevance: 0.4,
  },
  onchain: {
    officiality: 0.5,
    historicalAccuracy: 0.55,
    speed: 0.6,
    hypeFactor: 0.05,
    specificity: 0.8,
    resolutionRelevance: 0.35,
  },
  sentiment: {
    officiality: 0.05,
    historicalAccuracy: 0.4,
    speed: 0.85,
    hypeFactor: 0.65,
    specificity: 0.15,
    resolutionRelevance: 0.1,
  },
  system: {
    officiality: 0.3,
    historicalAccuracy: 0.5,
    speed: 0.5,
    hypeFactor: 0.0,
    specificity: 0.5,
    resolutionRelevance: 0.2,
  },
  noise: {
    officiality: 0.0,
    historicalAccuracy: 0.15,
    speed: 0.5,
    hypeFactor: 0.85,
    specificity: 0.05,
    resolutionRelevance: 0.0,
  },
}
