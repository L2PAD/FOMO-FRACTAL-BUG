/**
 * Event Cluster Service
 *
 * Deduplication + clustering of normalized events.
 * One real-world event = one cluster, regardless of how many sources report it.
 *
 * Strategy:
 *   1. Group by asset + eventType + time bucket (4h)
 *   2. Within groups, merge by Jaccard similarity on title tokens
 *   3. Second pass: merge remaining near-duplicates across groups
 *
 * Pure algorithmic — no AI.
 */

import { createHash } from 'crypto';
import type { NormalizedEvent, EventCluster, SourceTier } from '../types/event-feed.types.js';

const TIME_BUCKET_MS = 4 * 60 * 60 * 1000; // 4 hours
const JACCARD_THRESHOLD = 0.20;
const MIN_SHARED_TOKENS = 2;

const STOP_WORDS = new Set([
  'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'can', 'to', 'of', 'in', 'for', 'on',
  'with', 'at', 'by', 'from', 'as', 'into', 'and', 'but', 'or', 'not',
  'so', 'yet', 'both', 'either', 'each', 'all', 'any', 'some', 'no',
  'only', 'than', 'too', 'very', 'just', 'also', 'now', 'its', 'it',
  'this', 'that', 'these', 'those', 'up', 'out', 'off', 'over', 'under',
  'says', 'said', 'new', 'report', 'reports', 'according', 'amid',
  'like', 'get', 'got', 'much', 'still', 'even', 'while', 'since',
  'about', 'back', 'well', 'way', 'first', 'last', 'time', 'day',
  'week', 'month', 'year', 'latest', 'today', 'top', 'heres',
]);

class EventClusterService {
  /**
   * Cluster normalized events into deduplicated event clusters.
   */
  cluster(events: NormalizedEvent[]): EventCluster[] {
    if (!events.length) return [];

    // Pass 1: Group by asset+type+time
    const groups = this.buildGroups(events);

    // Pass 2: Merge similar within groups
    const clusters = this.mergeGroups(groups);

    // Pass 3: Cross-group dedup
    return this.crossGroupMerge(clusters);
  }

  private buildGroups(events: NormalizedEvent[]): Map<string, NormalizedEvent[]> {
    const groups = new Map<string, NormalizedEvent[]>();

    for (const ev of events) {
      const bucket = Math.floor(ev.publishedAt.getTime() / TIME_BUCKET_MS);
      const asset = ev.assets[0] || 'GEN';
      const key = `${asset}:${ev.eventType}:${bucket}`;

      // Also try adjacent bucket
      const keys = [key, `${asset}:${ev.eventType}:${bucket - 1}`];

      let placed = false;
      for (const k of keys) {
        if (groups.has(k)) {
          // Check similarity with existing group
          const existing = groups.get(k)!;
          const sim = this.titleSimilarity(ev.title, existing[0].title);
          if (sim >= JACCARD_THRESHOLD) {
            existing.push(ev);
            placed = true;
            break;
          }
        }
      }

      if (!placed) {
        groups.set(key, [ev]);
      }
    }

    return groups;
  }

  private mergeGroups(groups: Map<string, NormalizedEvent[]>): EventCluster[] {
    const entries = Array.from(groups.values());
    const merged = new Set<number>();
    const clusters: EventCluster[] = [];

    for (let i = 0; i < entries.length; i++) {
      if (merged.has(i)) continue;

      let groupEvents = [...entries[i]];

      for (let j = i + 1; j < entries.length; j++) {
        if (merged.has(j)) continue;

        // Compare representative titles
        const titleA = groupEvents[0].title;
        const titleB = entries[j][0].title;
        const sim = this.titleSimilarity(titleA, titleB);

        // Boost if same event type + shared asset
        const sameType = groupEvents[0].eventType === entries[j][0].eventType;
        const sharedAsset = groupEvents[0].assets.some(a => entries[j][0].assets.includes(a));
        let threshold = JACCARD_THRESHOLD;
        if (sameType) threshold -= 0.05;
        if (sharedAsset) threshold -= 0.03;

        if (sim >= threshold) {
          groupEvents.push(...entries[j]);
          merged.add(j);
        }
      }

      merged.add(i);
      clusters.push(this.buildCluster(groupEvents));
    }

    return clusters;
  }

  private crossGroupMerge(clusters: EventCluster[]): EventCluster[] {
    if (clusters.length <= 1) return clusters;

    const merged = new Set<number>();
    const result: EventCluster[] = [];

    for (let i = 0; i < clusters.length; i++) {
      if (merged.has(i)) continue;

      let current = clusters[i];

      for (let j = i + 1; j < clusters.length; j++) {
        if (merged.has(j)) continue;

        const other = clusters[j];

        // Time proximity: within 6h
        const timeDiff = Math.abs(current.firstSeenAt.getTime() - other.firstSeenAt.getTime());
        if (timeDiff > 6 * 60 * 60 * 1000) continue;

        const sim = this.titleSimilarity(current.canonicalTitle, other.canonicalTitle);
        const sameType = current.eventType === other.eventType;
        const sharedAsset = current.assets.some(a => other.assets.includes(a));

        let threshold = 0.28;
        if (sameType) threshold -= 0.06;
        if (sharedAsset) threshold -= 0.04;

        if (sim >= threshold) {
          // Merge
          current = this.mergeClusters(current, other);
          merged.add(j);
        }
      }

      merged.add(i);
      result.push(current);
    }

    return result;
  }

  private buildCluster(events: NormalizedEvent[]): EventCluster {
    events.sort((a, b) => a.publishedAt.getTime() - b.publishedAt.getTime());

    const sourceSet = new Set(events.map(e => e.sourceName));
    const assetSet = new Set(events.flatMap(e => e.assets));
    const entitySet = new Set(events.flatMap(e => e.entities));

    const bestEvent = this.pickBestEvent(events);
    const bestTier = Math.min(...events.map(e => e.sourceTier)) as SourceTier;
    const avgTrust = events.reduce((s, e) => s + e.trustScore, 0) / events.length;

    // Sentiment: majority vote
    const sentiments = events.map(e => e.sentimentHint).filter(Boolean);
    const bullCount = sentiments.filter(s => s === 'bullish').length;
    const bearCount = sentiments.filter(s => s === 'bearish').length;
    const sentimentHint = bullCount > bearCount ? 'bullish' : bearCount > bullCount ? 'bearish' : null;

    const clusterId = createHash('sha256')
      .update(`${bestEvent.title}:${events[0].publishedAt.toISOString()}:${[...assetSet].join(',')}`)
      .digest('hex')
      .slice(0, 16);

    return {
      clusterId,
      canonicalTitle: bestEvent.title,
      eventType: bestEvent.eventType,
      primaryAsset: events.flatMap(e => e.assets)[0] || null,
      assets: [...assetSet],
      entities: [...entitySet],
      sentimentHint,
      sourcesCount: sourceSet.size,
      sources: [...sourceSet],
      bestSourceTier: bestTier,
      avgTrustScore: Math.round(avgTrust * 100) / 100,
      firstSeenAt: events[0].publishedAt,
      lastSeenAt: events[events.length - 1].publishedAt,
      events,
      priority: 0,
      priorityBand: 'low',
      isBreaking: false,
      relevanceScore: 0,
    };
  }

  private mergeClusters(a: EventCluster, b: EventCluster): EventCluster {
    const allEvents = [...a.events, ...b.events];
    // Deduplicate by eventId
    const seen = new Set<string>();
    const deduped: NormalizedEvent[] = [];
    for (const ev of allEvents) {
      if (!seen.has(ev.eventId)) {
        seen.add(ev.eventId);
        deduped.push(ev);
      }
    }
    return this.buildCluster(deduped);
  }

  private pickBestEvent(events: NormalizedEvent[]): NormalizedEvent {
    // Prefer: lower tier → longer title → higher trust
    return [...events].sort((a, b) => {
      const tierDiff = a.sourceTier - b.sourceTier;
      if (tierDiff !== 0) return tierDiff;
      const trustDiff = b.trustScore - a.trustScore;
      if (Math.abs(trustDiff) > 0.05) return trustDiff > 0 ? 1 : -1;
      return (b.title?.length || 0) - (a.title?.length || 0);
    })[0];
  }

  private titleSimilarity(a: string, b: string): number {
    const tokA = new Set(this.tokenize(a));
    const tokB = new Set(this.tokenize(b));
    if (tokA.size === 0 || tokB.size === 0) return 0;

    const intersection = [...tokA].filter(t => tokB.has(t));
    if (intersection.length < MIN_SHARED_TOKENS) return 0;

    const union = new Set([...tokA, ...tokB]);
    return union.size > 0 ? intersection.length / union.size : 0;
  }

  private tokenize(text: string): string[] {
    return text
      .toLowerCase()
      .replace(/https?:\/\/\S+/g, '')
      .replace(/[^a-z\s]/g, '')
      .split(/\s+/)
      .filter(w => w.length > 2 && !STOP_WORDS.has(w))
      .sort();
  }
}

export const eventClusterService = new EventClusterService();
