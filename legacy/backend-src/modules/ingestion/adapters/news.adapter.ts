/**
 * News RSS Adapter
 * ================
 * Fetches articles directly from crypto news RSS feeds,
 * normalizes to UnifiedTextEvent for the ingestion pipeline.
 *
 * ARCHITECTURAL BOUNDARY:
 *   raw_events ONLY. No AI, no clustering, no ML training.
 *   News flows: RSS → adapter → raw_events → intake → sentiment_events
 *
 * Per-feed error isolation: one broken feed does not block others.
 */

import RssParser from 'rss-parser';
import { createHash } from 'crypto';
import type { IngestionAdapter, UnifiedTextEvent, SourceType } from '../ingestion.types.js';
import { newsSourceRegistryService } from '../../news-control/news-source-registry.service.js';

// ── RSS Feed Registry ────────────────────────────────────────────
interface FeedSource {
  id: string;
  name: string;
  url: string;
  tier: 'A' | 'B' | 'C';
  lang: string;
}

// Hardcoded fallback (used if registry unavailable)
const FALLBACK_FEEDS: FeedSource[] = [
  { id: 'coindesk',        name: 'CoinDesk',       url: 'https://www.coindesk.com/arc/outboundfeeds/rss/',  tier: 'A', lang: 'en' },
  { id: 'cointelegraph',   name: 'CoinTelegraph',  url: 'https://cointelegraph.com/rss',                   tier: 'A', lang: 'en' },
  { id: 'theblock',        name: 'TheBlock',       url: 'https://www.theblock.co/rss.xml',                 tier: 'A', lang: 'en' },
  { id: 'decrypt',         name: 'Decrypt',        url: 'https://decrypt.co/feed',                         tier: 'B', lang: 'en' },
  { id: 'cryptoslate',     name: 'CryptoSlate',    url: 'https://cryptoslate.com/feed/',                   tier: 'B', lang: 'en' },
  { id: 'bitcoinmagazine', name: 'BitcoinMagazine',url: 'https://bitcoinmagazine.com/.rss/full/',          tier: 'B', lang: 'en' },
  { id: 'newsbtc',         name: 'NewsBTC',        url: 'https://www.newsbtc.com/feed/',                   tier: 'C', lang: 'en' },
  { id: 'cryptopotato',    name: 'CryptoPotato',   url: 'https://cryptopotato.com/feed/',                  tier: 'C', lang: 'en' },
];

// ── Crypto asset detection ───────────────────────────────────────
const ASSET_MAP: Record<string, string> = {
  bitcoin: 'BTC', ethereum: 'ETH', solana: 'SOL', binance: 'BNB',
  ripple: 'XRP', cardano: 'ADA', dogecoin: 'DOGE', avalanche: 'AVAX',
  polkadot: 'DOT', polygon: 'MATIC', chainlink: 'LINK', uniswap: 'UNI',
  aave: 'AAVE', litecoin: 'LTC', cosmos: 'ATOM', filecoin: 'FIL',
  arbitrum: 'ARB', optimism: 'OP', sui: 'SUI', aptos: 'APT',
  tron: 'TRX', stellar: 'XLM', near: 'NEAR', fantom: 'FTM',
};

const TICKER_LIST = [
  'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'AVAX', 'DOT', 'MATIC',
  'LINK', 'UNI', 'AAVE', 'LTC', 'ATOM', 'FIL', 'ARB', 'OP', 'SUI', 'APT',
  'TRX', 'XLM', 'NEAR', 'FTM',
];

// Minimum text length to accept (filter garbage)
const MIN_TEXT_LENGTH = 30;

// Per-feed fetch timeout (ms)
const FEED_TIMEOUT_MS = 15_000;

// ── Adapter ──────────────────────────────────────────────────────
class NewsRssAdapter implements IngestionAdapter {
  sourceType: SourceType = 'news';
  sourceName = 'rss-news';

  private parser: RssParser;

  constructor() {
    this.parser = new RssParser({
      timeout: FEED_TIMEOUT_MS,
      headers: {
        'User-Agent': 'IntelligenceEngine/1.0 (RSS Aggregator)',
        'Accept': 'application/rss+xml, application/xml, text/xml',
      },
      maxRedirects: 3,
    });
  }

  /**
   * Fetch articles from all RSS feeds, normalize, filter, and return.
   * Uses source registry for enable/disable control and per-source stats tracking.
   */
  async fetch(params?: {
    limit?: number;
    sinceMinutes?: number;
    seedAll?: boolean;
  }): Promise<UnifiedTextEvent[]> {
    const limit = params?.limit ?? 100;
    const sinceMinutes = params?.sinceMinutes ?? 180;
    const cutoff = params?.seedAll
      ? new Date(0)
      : new Date(Date.now() - sinceMinutes * 60 * 1000);

    // Get enabled feeds from registry, fallback to hardcoded
    let feeds: FeedSource[];
    try {
      const registered = await newsSourceRegistryService.getEnabled();
      if (registered.length > 0) {
        feeds = registered.map(s => ({ id: s.id, name: s.name, url: s.url, tier: s.tier, lang: s.lang }));
      } else {
        feeds = FALLBACK_FEEDS;
      }
    } catch {
      feeds = FALLBACK_FEEDS;
    }

    console.log(`[NewsRssAdapter] Fetching from ${feeds.length} feeds (limit=${limit}, since=${sinceMinutes}min)`);

    // Fetch all feeds in batches to avoid overwhelming the system
    // With 120+ feeds, we process in batches of 15 with 500ms between batches
    const BATCH_SIZE = 15;
    const BATCH_DELAY_MS = 500;
    const feedResults: PromiseSettledResult<UnifiedTextEvent[]>[] = [];
    
    for (let i = 0; i < feeds.length; i += BATCH_SIZE) {
      const batch = feeds.slice(i, i + BATCH_SIZE);
      const batchResults = await Promise.allSettled(
        batch.map((feed) => this.fetchOneFeedTracked(feed, cutoff))
      );
      feedResults.push(...batchResults);
      
      // Delay between batches (except last)
      if (i + BATCH_SIZE < feeds.length) {
        await new Promise(r => setTimeout(r, BATCH_DELAY_MS));
      }
    }

    // Collect all articles, log per-feed stats
    const allArticles: UnifiedTextEvent[] = [];
    let successFeeds = 0;
    let failedFeeds = 0;

    for (let i = 0; i < feedResults.length; i++) {
      const result = feedResults[i];
      const feed = feeds[i];
      if (result.status === 'fulfilled') {
        successFeeds++;
        allArticles.push(...result.value);
      } else {
        failedFeeds++;
        console.warn(`[NewsRssAdapter] FAIL ${feed.name}: ${result.reason?.message || result.reason}`);
      }
    }

    console.log(`[NewsRssAdapter] Feeds: ${successFeeds} ok, ${failedFeeds} failed. Raw articles: ${allArticles.length}`);

    // Rate guard: warn if too many articles
    if (allArticles.length > 200) {
      console.warn(`[NewsRssAdapter] RATE GUARD: ${allArticles.length} articles fetched (threshold: 200)`);
    }

    // Sort by publishedAt desc, apply limit
    allArticles.sort((a, b) => b.publishedAt.getTime() - a.publishedAt.getTime());
    const limited = allArticles.slice(0, limit);

    console.log(`[NewsRssAdapter] Returning ${limited.length} articles (after limit)`);
    return limited;
  }

  /**
   * Fetch one feed with stats tracking to the source registry.
   */
  private async fetchOneFeedTracked(feed: FeedSource, cutoff: Date): Promise<UnifiedTextEvent[]> {
    const startMs = Date.now();
    try {
      const articles = await this.fetchOneFeed(feed, cutoff);
      const latencyMs = Date.now() - startMs;
      // Track success — fire-and-forget
      newsSourceRegistryService.recordSuccess(feed.id, articles.length, latencyMs).catch(() => {});
      return articles;
    } catch (err: any) {
      // Track failure — fire-and-forget
      newsSourceRegistryService.recordFailure(feed.id, err.message || String(err)).catch(() => {});
      throw err;
    }
  }

  /**
   * Fetch and parse a single RSS feed.
   */
  private async fetchOneFeed(feed: FeedSource, cutoff: Date): Promise<UnifiedTextEvent[]> {
    const parsed = await this.parser.parseURL(feed.url);
    const items = parsed.items || [];

    const events: UnifiedTextEvent[] = [];

    for (const item of items) {
      const publishedAt = item.pubDate ? new Date(item.pubDate) : new Date(item.isoDate || Date.now());

      // Skip articles older than cutoff
      if (publishedAt < cutoff) continue;

      const title = this.stripHtml(item.title || '').trim();
      const description = this.stripHtml(item.contentSnippet || item.content || item.summary || '').trim();
      const fullText = title ? `${title}. ${description}` : description;

      // Filter garbage: too short
      if (fullText.length < MIN_TEXT_LENGTH) continue;

      const articleUrl = item.link || item.guid || '';
      const externalId = this.buildExternalId(item.guid || articleUrl, feed.name);

      events.push({
        externalId,
        sourceType: 'news',
        sourceName: this.sourceName,

        text: fullText,
        title: title || undefined,
        summary: description.slice(0, 500) || undefined,
        url: articleUrl || undefined,

        publishedAt,
        ingestedAt: new Date(),

        author: item.creator ? { name: item.creator } : undefined,

        publisher: {
          name: feed.name,
          domain: this.extractDomain(articleUrl),
        },

        engagement: { views: 0 },

        assetMentions: this.extractAssets(fullText),
        projectMentions: [],

        dedupeKey: '',   // filled by orchestrator / dedupe service
        raw: {
          feedName: feed.name,
          feedUrl: feed.url,
          feedTier: feed.tier,
          guid: item.guid,
          categories: item.categories || [],
          language: feed.lang,
        },
      });
    }

    return events;
  }

  /**
   * Build a stable externalId from GUID/URL + feed name.
   * This is the primary dedup key at the (sourceType, externalId) level.
   */
  private buildExternalId(guidOrUrl: string, feedName: string): string {
    const raw = `${feedName}::${guidOrUrl}`;
    return createHash('sha256').update(raw).digest('hex').slice(0, 32);
  }

  /**
   * Strip HTML tags from RSS content.
   */
  private stripHtml(html: string): string {
    return html
      .replace(/<[^>]*>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#039;/g, "'")
      .replace(/\s+/g, ' ')
      .trim();
  }

  /**
   * Extract crypto asset mentions from text.
   */
  private extractAssets(text: string): string[] {
    const found = new Set<string>();
    const lower = text.toLowerCase();

    // Check ticker symbols (word boundary)
    for (const ticker of TICKER_LIST) {
      const re = new RegExp(`\\b${ticker}\\b`);
      if (re.test(text)) {
        found.add(ticker);
      }
    }

    // Check full names
    for (const [name, ticker] of Object.entries(ASSET_MAP)) {
      if (lower.includes(name)) {
        found.add(ticker);
      }
    }

    return Array.from(found);
  }

  /**
   * Extract domain from URL.
   */
  private extractDomain(url: string): string {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return '';
    }
  }
}

export const newsAdapter = new NewsRssAdapter();
