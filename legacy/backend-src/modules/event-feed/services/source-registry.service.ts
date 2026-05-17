/**
 * Source Registry Service
 *
 * Curated source definitions with trust scores.
 * Tier 1: SEC, official project announcements
 * Tier 2: CoinDesk, TheBlock, Bloomberg Crypto, Blockworks
 * Tier 3: Top curated Twitter accounts
 *
 * MVP: Static registry. No DB persistence needed.
 */

import type { FeedSource, SourceTier, SourceType } from '../types/event-feed.types.js';

const SOURCES: FeedSource[] = [
  // ── TIER 1: Official / Regulatory ──
  { id: 'sec-edgar',      name: 'SEC EDGAR',          tier: 1, type: 'regulatory', trustScore: 0.98, domain: 'sec.gov',              enabled: true },
  { id: 'sec-press',      name: 'SEC Press',          tier: 1, type: 'regulatory', trustScore: 0.97, domain: 'sec.gov',              enabled: true },
  { id: 'cftc',           name: 'CFTC',               tier: 1, type: 'regulatory', trustScore: 0.96, domain: 'cftc.gov',             enabled: true },
  { id: 'fed-minutes',    name: 'Fed Minutes',        tier: 1, type: 'official',   trustScore: 0.99, domain: 'federalreserve.gov',   enabled: true },
  { id: 'treasury',       name: 'US Treasury',        tier: 1, type: 'official',   trustScore: 0.98, domain: 'treasury.gov',         enabled: true },
  { id: 'whitehouse',     name: 'White House',        tier: 1, type: 'official',   trustScore: 0.95, domain: 'whitehouse.gov',       enabled: true },

  // ── TIER 2: Top Crypto Media ──
  { id: 'coindesk',        name: 'CoinDesk',          tier: 2, type: 'news', trustScore: 0.88, domain: 'coindesk.com',         enabled: true },
  { id: 'theblock',        name: 'The Block',         tier: 2, type: 'news', trustScore: 0.90, domain: 'theblock.co',          enabled: true },
  { id: 'blockworks',      name: 'Blockworks',        tier: 2, type: 'news', trustScore: 0.87, domain: 'blockworks.co',        enabled: true },
  { id: 'bloomberg-crypto', name: 'Bloomberg Crypto', tier: 2, type: 'news', trustScore: 0.92, domain: 'bloomberg.com',        enabled: true },
  { id: 'reuters-crypto',  name: 'Reuters Crypto',    tier: 2, type: 'news', trustScore: 0.91, domain: 'reuters.com',          enabled: true },
  { id: 'cointelegraph',   name: 'CoinTelegraph',     tier: 2, type: 'news', trustScore: 0.82, domain: 'cointelegraph.com',    enabled: true },
  { id: 'thedefiant',      name: 'The Defiant',       tier: 2, type: 'news', trustScore: 0.84, domain: 'thedefiant.io',        enabled: true },
  { id: 'dlnews',          name: 'DL News',           tier: 2, type: 'news', trustScore: 0.83, domain: 'dlnews.com',           enabled: true },
  { id: 'decrypt',         name: 'Decrypt',           tier: 2, type: 'news', trustScore: 0.80, domain: 'decrypt.co',           enabled: true },

  // ── TIER 3: Curated Twitter (high-signal accounts) ──
  { id: 'tw-zhusu',        name: 'Zhu Su',            tier: 3, type: 'twitter', trustScore: 0.65, enabled: true },
  { id: 'tw-cobie',        name: 'Cobie',             tier: 3, type: 'twitter', trustScore: 0.72, enabled: true },
  { id: 'tw-hsaka',        name: 'Hsaka',             tier: 3, type: 'twitter', trustScore: 0.68, enabled: true },
  { id: 'tw-lookonchain',  name: 'Lookonchain',       tier: 3, type: 'twitter', trustScore: 0.75, enabled: true },
  { id: 'tw-whale-alert',  name: 'Whale Alert',       tier: 3, type: 'twitter', trustScore: 0.78, enabled: true },
  { id: 'tw-tier10k',      name: 'Tier10K',           tier: 3, type: 'twitter', trustScore: 0.70, enabled: true },
  { id: 'tw-degentrading', name: 'Degen Trading',     tier: 3, type: 'twitter', trustScore: 0.62, enabled: true },
  { id: 'tw-cryptohayes',  name: 'Arthur Hayes',      tier: 3, type: 'twitter', trustScore: 0.74, enabled: true },
  { id: 'tw-inversebrah',  name: 'InverseBrah',       tier: 3, type: 'twitter', trustScore: 0.60, enabled: true },
  { id: 'tw-galaxyhq',     name: 'Galaxy Digital',    tier: 3, type: 'twitter', trustScore: 0.76, enabled: true },
];

class SourceRegistryService {
  private sources: Map<string, FeedSource>;

  constructor() {
    this.sources = new Map(SOURCES.map(s => [s.id, s]));
  }

  getAll(): FeedSource[] {
    return [...this.sources.values()];
  }

  getEnabled(): FeedSource[] {
    return [...this.sources.values()].filter(s => s.enabled);
  }

  getByTier(tier: SourceTier): FeedSource[] {
    return this.getEnabled().filter(s => s.tier === tier);
  }

  getById(id: string): FeedSource | undefined {
    return this.sources.get(id);
  }

  getTrustScore(sourceId: string): number {
    return this.sources.get(sourceId)?.trustScore ?? 0.3;
  }

  getTier(sourceId: string): SourceTier {
    return this.sources.get(sourceId)?.tier ?? 3;
  }

  /**
   * Resolve source from raw event data (best-effort matching).
   * Matches by source name, domain, or partial string.
   */
  resolveSource(sourceName: string, sourceUrl?: string): FeedSource | null {
    const lower = (sourceName || '').toLowerCase();
    const domain = sourceUrl ? new URL(sourceUrl).hostname.replace('www.', '') : '';

    for (const src of this.sources.values()) {
      if (src.id === lower) return src;
      if (src.name.toLowerCase() === lower) return src;
      if (src.domain && domain && domain.includes(src.domain)) return src;
      if (lower.includes(src.name.toLowerCase())) return src;
    }

    return null;
  }
}

export const sourceRegistryService = new SourceRegistryService();
