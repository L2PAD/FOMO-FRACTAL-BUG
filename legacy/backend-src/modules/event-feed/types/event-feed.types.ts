/**
 * Event Feed Types
 *
 * Core types for the curated event feed pipeline.
 * Entity-first, market-aware, dedup-first.
 */

export type SourceTier = 1 | 2 | 3;

export type SourceType = 'official' | 'news' | 'twitter' | 'onchain' | 'regulatory';

export interface FeedSource {
  id: string;
  name: string;
  tier: SourceTier;
  type: SourceType;
  trustScore: number;       // 0.0–1.0
  domain?: string;
  enabled: boolean;
}

export interface RawFeedEvent {
  externalId: string;
  sourceId: string;
  sourceName: string;
  sourceType: SourceType;
  sourceTier: SourceTier;
  title: string;
  text: string;
  url?: string;
  publishedAt: Date;
  rawEntities?: string[];
  rawAssets?: string[];
  metadata?: Record<string, any>;
}

export interface NormalizedEvent {
  eventId: string;
  sourceId: string;
  sourceName: string;
  sourceType: SourceType;
  sourceTier: SourceTier;
  trustScore: number;
  title: string;
  text: string;
  url?: string;
  publishedAt: Date;
  entities: string[];           // resolved entity names
  assets: string[];             // resolved asset tickers (BTC, ETH, SOL...)
  eventType: string;            // hack, etf, regulation, listing, macro, price, upgrade, funding...
  sentimentHint: string | null; // bullish | bearish | null
}

export interface EventCluster {
  clusterId: string;
  canonicalTitle: string;
  eventType: string;
  primaryAsset: string | null;
  assets: string[];
  entities: string[];
  sentimentHint: string | null;
  sourcesCount: number;
  sources: string[];
  bestSourceTier: SourceTier;
  avgTrustScore: number;
  firstSeenAt: Date;
  lastSeenAt: Date;
  events: NormalizedEvent[];
  priority: number;             // 0.0–1.0 final priority score
  priorityBand: 'critical' | 'high' | 'medium' | 'low';
  isBreaking: boolean;
  relevanceScore: number;       // 0.0–1.0 relevance to Polymarket
}

export interface FeedResult {
  clusters: EventCluster[];
  meta: {
    totalRawEvents: number;
    totalNormalized: number;
    totalClusters: number;
    criticalCount: number;
    highCount: number;
    mediumCount: number;
    lowCount: number;
    timeRangeHours: number;
    compressionRatio: number;
    generatedAt: Date;
  };
}

export interface FeedQuery {
  hoursBack?: number;
  limit?: number;
  asset?: string;
  eventType?: string;
  minPriority?: number;
  priorityBand?: 'critical' | 'high' | 'medium' | 'low';
}
