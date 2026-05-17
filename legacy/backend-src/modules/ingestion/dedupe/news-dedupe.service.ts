/**
 * News Dedupe Service
 * ===================
 * Cross-source deduplication for news articles.
 *
 * Problem: Same news event reported by multiple outlets:
 *   - CoinDesk: "SEC Approves Bitcoin ETF"
 *   - CoinTelegraph: "Bitcoin ETF Gets SEC Approval"
 *   - Decrypt: "SEC Gives Green Light to BTC ETF"
 *
 * Strategy:
 * 1. Hard dedupe: sourceType + externalId (handled by main dedupe service)
 * 2. Headline similarity: normalized title hash within 1-hour window
 * 3. URL domain + path dedupe: same article from different scrapers
 *
 * Returns a dedupe key that groups similar news into the same event.
 */

import { createHash } from 'crypto';
import type { UnifiedTextEvent } from '../ingestion.types.js';

// Noise words to strip for headline comparison
const STOP_WORDS = new Set([
  'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
  'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
  'before', 'after', 'above', 'below', 'and', 'but', 'or', 'nor', 'not',
  'so', 'yet', 'both', 'either', 'neither', 'each', 'every', 'all',
  'any', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'only',
  'own', 'same', 'than', 'too', 'very', 'just', 'because', 'its', 'it',
  'this', 'that', 'these', 'those', 'up', 'out', 'off', 'over', 'under',
  'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
  'why', 'how', 'what', 'which', 'who', 'whom',
]);

class NewsDedupeService {
  /**
   * Build a cross-source dedupe key for a news article.
   * Groups similar headlines from different outlets within the same time window.
   */
  buildNewsDedupeKey(event: UnifiedTextEvent): string {
    // Strategy 1: URL-based (most reliable for same article from different scrapers)
    if (event.url) {
      const urlKey = this.normalizeUrl(event.url);
      if (urlKey) {
        return `news:url:${createHash('sha1').update(urlKey).digest('hex')}`;
      }
    }

    // Strategy 2: Headline-based within 1-hour window
    const title = event.title || event.text.slice(0, 120);
    const normalizedTitle = this.normalizeHeadline(title);

    // 1-hour time bucket for headline grouping
    const hourBucket = new Date(
      Math.floor(event.publishedAt.getTime() / (60 * 60 * 1000)) * (60 * 60 * 1000)
    ).toISOString();

    // Extract key entities (assets + large numbers)
    const entities = this.extractKeyEntities(title);
    const entityKey = entities.sort().join('|');

    const raw = `news:headline:${normalizedTitle}:${entityKey}:${hourBucket}`;
    return createHash('sha1').update(raw).digest('hex');
  }

  /**
   * Normalize headline for comparison:
   * Remove stop words, punctuation, normalize whitespace, lowercase
   */
  private normalizeHeadline(title: string): string {
    return title
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, '')    // remove punctuation
      .split(/\s+/)
      .filter(w => w.length > 1 && !STOP_WORDS.has(w))
      .sort()                           // order-independent comparison
      .join(' ')
      .trim();
  }

  /**
   * Extract URL without query params and fragments
   */
  private normalizeUrl(url: string): string {
    try {
      const u = new URL(url);
      // Remove tracking params
      return `${u.hostname}${u.pathname}`.replace(/\/+$/, '');
    } catch {
      return '';
    }
  }

  /**
   * Extract key entities from title (assets, numbers, proper nouns)
   */
  private extractKeyEntities(title: string): string[] {
    const entities: string[] = [];
    const upper = title.toUpperCase();

    // Crypto tickers
    const tickers = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'AVAX', 'DOT', 'MATIC'];
    for (const t of tickers) {
      if (upper.includes(t)) entities.push(t);
    }

    // Key orgs
    const orgs = ['SEC', 'CFTC', 'FBI', 'DOJ', 'BINANCE', 'COINBASE', 'KRAKEN', 'FTX'];
    for (const o of orgs) {
      if (upper.includes(o)) entities.push(o);
    }

    // Large numbers (prices, amounts)
    const nums = title.match(/\$[\d,.]+[BMK]?/g);
    if (nums) entities.push(...nums.map(n => n.replace(/,/g, '')));

    return entities;
  }
}

export const newsDedupeService = new NewsDedupeService();
