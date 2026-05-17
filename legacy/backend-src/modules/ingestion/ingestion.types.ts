/**
 * Ingestion Layer — Types
 * =======================
 * Universal event types for multi-source ingestion pipeline.
 * Source-agnostic: twitter, news, telegram, etc.
 */

export type SourceType = 'twitter' | 'news' | 'telegram';

export interface UnifiedTextEvent {
  externalId: string;
  sourceType: SourceType;
  sourceName: string;

  text: string;
  title?: string;
  summary?: string;
  url?: string;

  publishedAt: Date;
  ingestedAt: Date;

  author?: {
    id?: string;
    handle?: string;
    name?: string;
    followers?: number;
    verified?: boolean;
  };

  publisher?: {
    name?: string;
    domain?: string;
  };

  engagement?: {
    likes?: number;
    reposts?: number;
    replies?: number;
    views?: number;
  };

  assetMentions?: string[];
  projectMentions?: string[];

  dedupeKey: string;
  raw: Record<string, any>;
}

export interface IngestionRunResult {
  source: string;
  fetched: number;
  inserted: number;
  duplicated: number;
  errors: number;
  durationMs: number;
  startedAt: Date;
  finishedAt: Date;
}

export interface IngestionAdapter {
  sourceType: SourceType;
  sourceName: string;
  fetch(params?: { limit?: number; sinceMinutes?: number; seedAll?: boolean }): Promise<UnifiedTextEvent[]>;
}
