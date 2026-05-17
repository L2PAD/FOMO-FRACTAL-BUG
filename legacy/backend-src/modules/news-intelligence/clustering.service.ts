/**
 * News Clustering Service v3
 * ==========================
 * Improved clustering with:
 *  - Stronger title normalization (numbers, filler removal)
 *  - Lower Jaccard threshold (0.18) for more aggressive merging
 *  - EventType compatibility boost in similarity
 *  - Asset overlap boost in similarity
 *  - Wider time buckets (6h)
 *  - Better named entity extraction
 *
 * Strategy:
 * 1. Normalize titles (lowercase, remove noise, sort key tokens)
 * 2. Group by: entity keys + asset + time_bucket(24h wide / 6h narrow)
 * 3. Fuzzy matching: Jaccard on token sets (threshold 0.18) + type/asset boosts
 * 4. Output: clusters with sourcesCount, firstSeenAt, representative title
 *
 * NO AI, NO OpenAI, NO NLP libraries. Pure algorithmic approach.
 */

import { createHash } from 'crypto';

// Stop words for title normalization (expanded)
const STOP_WORDS = new Set([
  'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
  'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
  'before', 'after', 'and', 'but', 'or', 'nor', 'not', 'so', 'yet',
  'both', 'either', 'neither', 'each', 'every', 'all', 'any', 'few',
  'more', 'most', 'other', 'some', 'no', 'only', 'own', 'same', 'than',
  'too', 'very', 'just', 'because', 'its', 'it', 'this', 'that', 'these',
  'those', 'up', 'out', 'off', 'over', 'under', 'again', 'then', 'once',
  'here', 'there', 'when', 'where', 'why', 'how', 'what', 'which', 'who',
  'says', 'said', 'new', 'report', 'reports', 'according', 'amid',
  'also', 'like', 'get', 'got', 'gets', 'getting', 'much', 'still', 'even',
  'now', 'while', 'since', 'about', 'around', 'back', 'well', 'way',
  'come', 'came', 'make', 'made', 'take', 'took', 'set', 'keep', 'let',
  'put', 'see', 'seem', 'show', 'try', 'ask', 'need', 'first',
  'last', 'long', 'great', 'little', 'next', 'look', 'right', 'big',
  'high', 'low', 'old', 'year', 'day', 'week', 'month', 'time',
  'could', 'going', 'really', 'think', 'know', 'want', 'give', 'use',
  'find', 'tell', 'help', 'thing', 'people', 'world', 'hand', 'part',
  'eye', 'place', 'case', 'point', 'company', 'number', 'group',
  'may', 'might', 'says', 'data', 'latest', 'today', 'top', 'heres',
  'dont', 'cant', 'wont', 'isnt', 'arent', 'wasnt', 'werent',
]);

// Event type keywords (same as before)
const EVENT_TYPE_KEYWORDS: Record<string, string[]> = {
  hack:        ['hack', 'hacked', 'exploit', 'breach', 'stolen', 'attack', 'drained', 'vulnerability'],
  listing:     ['listing', 'listed', 'delist', 'delisted', 'exchange listing', 'ipo'],
  etf:         ['etf', 'etf filing', 'etf approval', 'etf application', 's-1', 'grayscale'],
  regulation:  ['sec', 'cftc', 'regulation', 'regulatory', 'lawsuit', 'legal', 'ban', 'fine', 'enforcement', 'compliance', 'court', 'act', 'bill', 'legislation'],
  funding:     ['funding', 'raised', 'raise', 'series a', 'series b', 'investment', 'venture', 'seed round', 'valuation'],
  partnership: ['partnership', 'partners', 'collaboration', 'integrate', 'integration', 'alliance'],
  macro:       ['fed', 'interest rate', 'inflation', 'gdp', 'treasury', 'recession', 'gold', 'war', 'tariff', 'iran', 'china', 'trump', 'policy'],
  upgrade:     ['upgrade', 'fork', 'mainnet', 'testnet', 'launch', 'v2', 'update', 'migration', 'deploy'],
  whale:       ['whale', 'large transfer', 'accumulation', 'wallet', 'shark'],
  price:       ['price', 'rally', 'crash', 'dump', 'pump', 'bull', 'bear', 'breakout', 'support', 'resistance', 'ath', 'all-time'],
  adoption:    ['adoption', 'accept', 'payment', 'merchant', 'mainstream'],
};

// Time bucket: 6 hours (wider window for grouping)
const TIME_BUCKET_MS = 6 * 60 * 60 * 1000;

// Jaccard similarity threshold for cluster merge (lowered for more aggressive merging)
const SIMILARITY_THRESHOLD = 0.18;

// Minimum shared tokens for merge consideration
const MIN_SHARED_TOKENS = 2;

export interface RawNewsEvent {
  externalId: string;
  title: string;
  text: string;
  url?: string;
  publishedAt: Date;
  publisher: { name: string; domain: string };
  assetMentions: string[];
  raw: { feedTier?: string; categories?: any[] };
}

export interface NewsCluster {
  clusterId: string;
  title: string;
  eventType: string;
  primaryAsset: string | null;
  assets: string[];
  importance: number;
  importanceBand: 'high' | 'medium' | 'low';
  feedRankScore: number;
  isBreaking: boolean;
  sourcesCount: number;
  sources: string[];
  firstSeenAt: Date;
  lastSeenAt: Date;
  events: ClusterEvent[];
  sentimentHint: string | null;
  representativeUrl: string | null;
  representativeSource: string | null;
}

export interface ClusterEvent {
  externalId: string;
  title: string;
  url?: string;
  publisher: string;
  tier: string;
  publishedAt: Date;
}

class NewsClusteringService {
  /**
   * Build clusters from raw news events.
   * Three-pass approach:
   *   Pass 1: Group by entity keys (named entities + assets + time)
   *   Pass 2: Merge similar groups using enhanced Jaccard
   *   Pass 3: Final merge pass for stragglers
   */
  buildClusters(events: RawNewsEvent[]): NewsCluster[] {
    if (events.length === 0) return [];

    // Step 1: Build initial groups by entity+asset+time_bucket
    const groups = this.buildInitialGroups(events);

    // Step 2: Merge similar groups using enhanced Jaccard
    const clusters = this.mergeSimilarClusters(groups);

    // Step 3: Second merge pass — catch remaining duplicates
    return this.secondPassMerge(clusters);
  }

  /**
   * Build initial groups by extracting key entities from titles.
   */
  private buildInitialGroups(events: RawNewsEvent[]): Map<string, RawNewsEvent[]> {
    const groupMap = new Map<string, RawNewsEvent[]>();
    const entityToGroup = new Map<string, string>();

    for (const event of events) {
      const keys = this.buildGroupKeys(event);
      let targetGroupKey: string | null = null;

      for (const key of keys) {
        if (key.startsWith('unique:')) continue;
        const existing = entityToGroup.get(key);
        if (existing && groupMap.has(existing)) {
          targetGroupKey = existing;
          break;
        }
      }

      if (targetGroupKey) {
        groupMap.get(targetGroupKey)!.push(event);
        for (const key of keys) {
          if (!key.startsWith('unique:')) {
            entityToGroup.set(key, targetGroupKey);
          }
        }
      } else {
        const primaryKey = keys.find(k => !k.startsWith('unique:')) || keys[0];
        groupMap.set(primaryKey, [event]);
        for (const key of keys) {
          if (!key.startsWith('unique:')) {
            entityToGroup.set(key, primaryKey);
          }
        }
      }
    }

    return groupMap;
  }

  /**
   * Build multiple candidate group keys.
   * Uses more entity patterns + wider time buckets.
   */
  private buildGroupKeys(event: RawNewsEvent): string[] {
    const title = event.title || event.text.slice(0, 120);
    const wideBucket = Math.floor(new Date(event.publishedAt).getTime() / (24 * 60 * 60 * 1000));
    const narrowBucket = Math.floor(new Date(event.publishedAt).getTime() / TIME_BUCKET_MS);
    const asset = event.assetMentions[0] || 'GEN';

    const entities = this.extractNamedEntities(title);
    const tokens = this.normalizeTitle(title);

    const keys: string[] = [];

    // Key 1: Entity-based (wide time bucket + neighbor)
    if (entities.length > 0) {
      for (const entity of entities) {
        keys.push(`ent:${entity}:${wideBucket}`);
        keys.push(`ent:${entity}:${wideBucket - 1}`);
      }
    }

    // Key 2: Asset + EventType compound key
    if (asset !== 'GEN') {
      const eventType = this.detectEventType(title);
      keys.push(`asset_type:${asset}:${eventType}:${narrowBucket}`);
      keys.push(`asset_type:${asset}:${eventType}:${narrowBucket - 1}`);
    }

    // Key 3: Top 3 content tokens (narrow bucket)
    if (tokens.length >= 3) {
      keys.push(`tok:${tokens.slice(0, 3).join('+')}:${narrowBucket}`);
      keys.push(`tok:${tokens.slice(0, 3).join('+')}:${narrowBucket - 1}`);
    }

    // Key 4: Top 2 content tokens + asset (wider match)
    if (tokens.length >= 2 && asset !== 'GEN') {
      keys.push(`tok2:${tokens.slice(0, 2).join('+')}:${asset}:${narrowBucket}`);
    }

    // Key 5: Fallback — unique event
    keys.push(`unique:${event.externalId}`);

    return keys;
  }

  /**
   * Extract named entities from title (expanded patterns).
   */
  private extractNamedEntities(title: string): string[] {
    const entities: string[] = [];

    const ENTITY_PATTERNS: [string, RegExp][] = [
      // Compound entities
      ['grayscale_hype_etf', /grayscale.*(?:hype|hyperliquid).*(?:etf|filing|s-1)/i],
      ['grayscale_hype_etf', /grayscale.*(?:etf|filing|s-1).*(?:hype|hyperliquid)/i],
      ['grayscale_hype_etf', /(?:hype|hyperliquid).*(?:etf|filing)/i],
      ['grayscale_zcash', /grayscale.*(?:zcash|zec)/i],
      ['morgan_stanley_btc_etf', /morgan.*stanley.*(?:btc|bitcoin).*etf/i],
      ['stablecoin_bill', /stablecoin.*(?:bill|act|law)|(?:bill|act|law).*stablecoin|genius act/i],
      ['crypto_bill', /crypto.*(?:bill|act|law)|(?:bill|act|law).*crypto|clarity.*act/i],
      ['bitcoin_mining', /bitcoin.*min(?:ing|er)|min(?:ing|er).*bitcoin|mining.*difficult/i],
      ['bitcoin_etf', /bitcoin.*etf|btc.*etf|etf.*bitcoin|etf.*btc/i],
      ['ethereum_whales', /ethereum.*whale|eth.*whale|whale.*ethereum|whale.*eth/i],
      ['bitcoin_options', /bitcoin.*option|btc.*option|option.*bitcoin/i],
      ['bitcoin_reserve', /bitcoin.*reserve|strategic.*reserve|reserve.*bitcoin/i],
      ['crypto_jobs', /crypto.*(?:job|layoff|cut|fired)|(?:job|layoff|cut).*crypto/i],
      ['fed_rate', /fed(?:eral)?.*(?:rate|cut|hike|pause)|interest.*rate.*(?:cut|hike)/i],
      ['iran_war', /iran.*(?:attack|strike|war|missile|nuclear)|(?:attack|war|strike).*iran/i],
      // Simple entities
      ['kalshi', /kalshi/i],
      ['sbf', /bankman.?fried|\bsbf\b/i],
      ['sec_action', /\bsec\b(?!ond|urity|ure|tor).*(?:sues|charges|action|enforcement|fine)/i],
      ['coinbase', /coinbase/i],
      ['binance', /binance/i],
      ['blackrock', /blackrock/i],
      ['microstrategy', /microstrategy|strategy.*bitcoin|saylor/i],
      ['vaneck', /vaneck/i],
      ['iran', /\biran\b/i],
      ['fed', /\bfed\b|federal reserve/i],
      ['ripple', /ripple|\bxrp\b/i],
      ['solana', /solana|\bsol\b/i],
      ['tron', /\btron\b|\btrx\b/i],
      ['trump', /trump/i],
    ];

    for (const [name, pattern] of ENTITY_PATTERNS) {
      if (pattern.test(title)) {
        entities.push(name);
      }
    }

    return entities;
  }

  /**
   * Merge candidate groups using enhanced similarity.
   */
  private mergeSimilarClusters(candidateMap: Map<string, RawNewsEvent[]>): NewsCluster[] {
    const entries = Array.from(candidateMap.entries());
    const merged = new Set<number>();
    const clusters: NewsCluster[] = [];

    for (let i = 0; i < entries.length; i++) {
      if (merged.has(i)) continue;

      let groupEvents = [...entries[i][1]];

      for (let j = i + 1; j < entries.length; j++) {
        if (merged.has(j)) continue;

        const sim = this.enhancedSimilarity(groupEvents, entries[j][1]);
        if (sim >= SIMILARITY_THRESHOLD) {
          groupEvents.push(...entries[j][1]);
          merged.add(j);
        }
      }

      merged.add(i);
      clusters.push(this.buildCluster(groupEvents));
    }

    return clusters;
  }

  /**
   * Second merge pass: catch remaining near-duplicates among built clusters.
   * Compares cluster titles directly with higher threshold.
   */
  private secondPassMerge(clusters: NewsCluster[]): NewsCluster[] {
    if (clusters.length <= 1) return clusters;

    const merged = new Set<number>();
    const result: NewsCluster[] = [];

    for (let i = 0; i < clusters.length; i++) {
      if (merged.has(i)) continue;

      let current = clusters[i];

      for (let j = i + 1; j < clusters.length; j++) {
        if (merged.has(j)) continue;

        const other = clusters[j];

        // Check time proximity (must be within 8h)
        const timeDiff = Math.abs(current.firstSeenAt.getTime() - other.firstSeenAt.getTime());
        if (timeDiff > 8 * 60 * 60 * 1000) continue;

        // Compare cluster titles (Jaccard on tokens)
        const tokensA = new Set(this.normalizeTitle(current.title));
        const tokensB = new Set(this.normalizeTitle(other.title));
        const intersection = [...tokensA].filter(t => tokensB.has(t));
        const union = new Set([...tokensA, ...tokensB]);
        const jaccard = union.size > 0 ? intersection.length / union.size : 0;

        // Boost: same event type → lower threshold needed
        const sameType = current.eventType === other.eventType;
        // Boost: shared assets
        const sharedAssets = current.assets.some(a => other.assets.includes(a));

        let effectiveThreshold = 0.30;
        if (sameType) effectiveThreshold -= 0.08;
        if (sharedAssets) effectiveThreshold -= 0.05;

        if (jaccard >= effectiveThreshold && intersection.length >= MIN_SHARED_TOKENS) {
          // Merge: combine events from both clusters
          const allEvents = [...current.events, ...other.events];
          // Deduplicate by externalId
          const seen = new Set<string>();
          const deduped: ClusterEvent[] = [];
          for (const ev of allEvents) {
            if (!seen.has(ev.externalId)) {
              seen.add(ev.externalId);
              deduped.push(ev);
            }
          }

          // Rebuild merged cluster properties
          const sourceSet = new Set(deduped.map(e => e.publisher));
          const assetSet = new Set([...current.assets, ...other.assets]);
          deduped.sort((a, b) => new Date(a.publishedAt).getTime() - new Date(b.publishedAt).getTime());

          current = {
            ...current,
            events: deduped,
            sourcesCount: sourceSet.size,
            sources: Array.from(sourceSet),
            assets: Array.from(assetSet),
            firstSeenAt: deduped[0].publishedAt,
            lastSeenAt: deduped[deduped.length - 1].publishedAt,
          };

          merged.add(j);
        }
      }

      merged.add(i);
      result.push(current);
    }

    return result;
  }

  /**
   * Enhanced similarity: Jaccard + type/asset boosts.
   */
  private enhancedSimilarity(groupA: RawNewsEvent[], groupB: RawNewsEvent[]): number {
    const tokensA = new Set<string>();
    const tokensB = new Set<string>();

    for (const e of groupA) {
      for (const t of this.normalizeTitle(e.title || '')) tokensA.add(t);
    }
    for (const e of groupB) {
      for (const t of this.normalizeTitle(e.title || '')) tokensB.add(t);
    }

    // Time proximity check (must be within 6h)
    const timesA = groupA.map(e => new Date(e.publishedAt).getTime());
    const timesB = groupB.map(e => new Date(e.publishedAt).getTime());
    const minA = Math.min(...timesA);
    const maxB = Math.max(...timesB);
    const minB = Math.min(...timesB);
    const maxA = Math.max(...timesA);

    const timeDiff = Math.min(Math.abs(maxA - minB), Math.abs(maxB - minA));
    if (timeDiff > 6 * 60 * 60 * 1000) return 0;

    // Asset overlap
    const assetsA = new Set(groupA.flatMap(e => e.assetMentions));
    const assetsB = new Set(groupB.flatMap(e => e.assetMentions));
    const hasCommonAsset = assetsA.size === 0 || assetsB.size === 0 ||
      [...assetsA].some(a => assetsB.has(a));

    if (!hasCommonAsset && assetsA.size > 0 && assetsB.size > 0) return 0;

    // Jaccard similarity on tokens
    const intersection = [...tokensA].filter(t => tokensB.has(t));
    const union = new Set([...tokensA, ...tokensB]);
    let jaccard = union.size > 0 ? intersection.length / union.size : 0;

    // Minimum shared tokens gate
    if (intersection.length < MIN_SHARED_TOKENS) return 0;

    // Boost: same event type detected
    const typeA = this.detectEventType(groupA.map(e => e.title).join(' '));
    const typeB = this.detectEventType(groupB.map(e => e.title).join(' '));
    if (typeA === typeB && typeA !== 'market') jaccard += 0.05;

    // Boost: shared assets
    if (hasCommonAsset && assetsA.size > 0 && assetsB.size > 0) jaccard += 0.04;

    return jaccard;
  }

  /**
   * Build a NewsCluster from a group of events.
   */
  private buildCluster(events: RawNewsEvent[]): NewsCluster {
    events.sort((a, b) => new Date(a.publishedAt).getTime() - new Date(b.publishedAt).getTime());

    const firstEvent = events[0];
    const lastEvent = events[events.length - 1];

    const sourceSet = new Set(events.map(e => e.publisher.name));
    const sources = Array.from(sourceSet);

    const assetSet = new Set(events.flatMap(e => e.assetMentions));
    const assets = Array.from(assetSet);
    const primaryAsset = this.pickPrimaryAsset(events);

    const bestTitle = this.pickBestTitle(events);
    const bestEvent = this.pickBestEvent(events);

    const combinedText = events.map(e => `${e.title} ${e.text}`).join(' ');
    const eventType = this.detectEventType(combinedText);

    const firstSeenAt = new Date(firstEvent.publishedAt);
    const lastSeenAt = new Date(lastEvent.publishedAt);
    const clusterId = createHash('sha256')
      .update(`${bestTitle}:${primaryAsset}:${firstSeenAt.toISOString()}`)
      .digest('hex')
      .slice(0, 16);

    const sentimentHint = this.detectSentimentHint(combinedText);

    return {
      clusterId,
      title: bestTitle,
      eventType,
      primaryAsset,
      assets,
      importance: 0,
      importanceBand: 'low' as const,
      feedRankScore: 0,
      isBreaking: false,
      sourcesCount: sources.length,
      sources,
      firstSeenAt,
      lastSeenAt,
      events: events.map(e => ({
        externalId: e.externalId,
        title: e.title,
        url: e.url,
        publisher: e.publisher.name,
        tier: e.raw.feedTier || 'C',
        publishedAt: new Date(e.publishedAt),
      })),
      sentimentHint,
      representativeUrl: bestEvent?.url || null,
      representativeSource: bestEvent?.publisher.name || null,
    };
  }

  /**
   * Normalize title into sorted meaningful tokens (improved).
   * Removes numbers, URLs, common filler, possessives.
   */
  normalizeTitle(title: string): string[] {
    return title
      .toLowerCase()
      .replace(/https?:\/\/\S+/g, '')         // Remove URLs
      .replace(/['']/g, '')                     // Remove possessives
      .replace(/\$[a-z]+/gi, '')               // Remove ticker symbols like $BTC
      .replace(/[^a-z\s]/g, '')                // Remove non-alpha (numbers, punctuation)
      .split(/\s+/)
      .filter(w => w.length > 2 && !STOP_WORDS.has(w))
      .sort();
  }

  private pickBestTitle(events: RawNewsEvent[]): string {
    return this.pickBestEvent(events)?.title || events[0]?.text.slice(0, 120) || 'Untitled';
  }

  private pickBestEvent(events: RawNewsEvent[]): RawNewsEvent | null {
    const tierOrder: Record<string, number> = { A: 0, B: 1, C: 2 };
    const sorted = [...events].sort((a, b) => {
      const tierDiff = (tierOrder[a.raw.feedTier || 'C'] || 2) - (tierOrder[b.raw.feedTier || 'C'] || 2);
      if (tierDiff !== 0) return tierDiff;
      return (b.title?.length || 0) - (a.title?.length || 0);
    });
    return sorted[0] || null;
  }

  private pickPrimaryAsset(events: RawNewsEvent[]): string | null {
    const counts = new Map<string, number>();
    for (const e of events) {
      for (const asset of e.assetMentions) {
        counts.set(asset, (counts.get(asset) || 0) + 1);
      }
    }
    if (counts.size === 0) return null;
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0];
  }

  detectEventType(text: string): string {
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

  private detectSentimentHint(text: string): string | null {
    const lower = text.toLowerCase();

    const bullish = ['bullish', 'rally', 'surge', 'soar', 'breakout', 'all-time high', 'ath',
      'approval', 'approved', 'adoption', 'accumulation', 'buy', 'moon',
      'profitable', 'recovery', 'growth', 'gain', 'breakthrough'];
    const bearish = ['bearish', 'crash', 'dump', 'plunge', 'hack', 'exploit', 'stolen',
      'ban', 'lawsuit', 'fine', 'sell-off', 'fear', 'liquidat', 'war',
      'layoff', 'cut', 'weak', 'decline', 'drop', 'loss', 'risk'];

    let bullScore = 0;
    let bearScore = 0;

    for (const w of bullish) { if (lower.includes(w)) bullScore++; }
    for (const w of bearish) { if (lower.includes(w)) bearScore++; }

    if (bullScore > bearScore && bullScore >= 2) return 'bullish';
    if (bearScore > bullScore && bearScore >= 2) return 'bearish';
    if (bullScore > 0 && bearScore === 0) return 'bullish';
    if (bearScore > 0 && bullScore === 0) return 'bearish';
    return null;
  }
}

export const newsClusteringService = new NewsClusteringService();
