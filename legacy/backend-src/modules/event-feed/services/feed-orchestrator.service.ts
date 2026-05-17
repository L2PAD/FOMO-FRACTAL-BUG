/**
 * Feed Orchestrator Service
 *
 * Main pipeline:
 *   raw events (MongoDB) → normalize → cluster → relevance filter → priority score → feed
 *
 * Sources: notification_events + raw_events (existing data).
 * MVP: reads from what we have, no external scraping.
 */

import { getDb } from '../../../db/mongodb.js';
import type {
  RawFeedEvent, NormalizedEvent, EventCluster,
  FeedResult, FeedQuery, SourceType,
} from '../types/event-feed.types.js';
import { sourceRegistryService } from './source-registry.service.js';
import { eventNormalizerService } from './event-normalizer.service.js';
import { eventClusterService } from './event-cluster.service.js';
import { relevanceFilterService } from './relevance-filter.service.js';
import { priorityScorerService } from './priority-scorer.service.js';

class FeedOrchestratorService {
  /**
   * Build the curated event feed.
   */
  async buildFeed(query: FeedQuery = {}): Promise<FeedResult> {
    const hoursBack = query.hoursBack ?? 24;
    const limit = query.limit ?? 30;
    const since = new Date(Date.now() - hoursBack * 3600 * 1000);

    // Step 1: Fetch raw events from all available sources in MongoDB
    const rawEvents = await this.fetchRawEvents(since, query.asset);

    // Step 2: Normalize
    const normalized = eventNormalizerService.normalizeBatch(rawEvents);

    // Step 3: Cluster (dedup)
    let clusters = eventClusterService.cluster(normalized);

    // Step 4: Relevance filter
    clusters = relevanceFilterService.filterAndScore(clusters);

    // Step 5: Priority scoring
    clusters = priorityScorerService.scoreAndRank(clusters);

    // Step 6: Apply filters
    if (query.eventType) {
      clusters = clusters.filter(c => c.eventType === query.eventType);
    }
    if (query.minPriority) {
      clusters = clusters.filter(c => c.priority >= query.minPriority!);
    }
    if (query.priorityBand) {
      clusters = clusters.filter(c => c.priorityBand === query.priorityBand);
    }

    // Count before limiting
    const criticalCount = clusters.filter(c => c.priorityBand === 'critical').length;
    const highCount = clusters.filter(c => c.priorityBand === 'high').length;
    const mediumCount = clusters.filter(c => c.priorityBand === 'medium').length;
    const lowCount = clusters.filter(c => c.priorityBand === 'low').length;

    // Step 7: Limit
    const limited = clusters.slice(0, limit);

    // Strip heavy event arrays for response (keep top 3 per cluster)
    const lightClusters = limited.map(c => ({
      ...c,
      events: c.events.slice(0, 3).map(e => ({
        eventId: e.eventId,
        sourceId: e.sourceId,
        sourceName: e.sourceName,
        sourceTier: e.sourceTier,
        title: e.title,
        url: e.url,
        publishedAt: e.publishedAt,
      })),
    }));

    return {
      clusters: lightClusters as EventCluster[],
      meta: {
        totalRawEvents: rawEvents.length,
        totalNormalized: normalized.length,
        totalClusters: clusters.length,
        criticalCount,
        highCount,
        mediumCount,
        lowCount,
        timeRangeHours: hoursBack,
        compressionRatio: rawEvents.length > 0 && clusters.length > 0
          ? Math.round((rawEvents.length / clusters.length) * 10) / 10
          : 1,
        generatedAt: new Date(),
      },
    };
  }

  /**
   * Get feed for a specific asset (used by prediction pipeline).
   */
  async getFeedForAsset(asset: string, hoursBack: number = 24): Promise<EventCluster[]> {
    const result = await this.buildFeed({ asset, hoursBack, limit: 20 });
    return result.clusters;
  }

  /**
   * Get related events for entities (replaces _gather_related_events in Python).
   */
  async getRelatedEvents(
    entities: string[],
    eventType: string,
    hoursBack: number = 48,
  ): Promise<{ title: string; text: string; source: string; source_type: string; source_quality: number; relevance_score: number }[]> {
    const result = await this.buildFeed({ hoursBack, limit: 30 });

    // Filter clusters that match any entity or asset
    const entitySet = new Set(entities.map(e => e.toLowerCase()));
    const relevant = result.clusters.filter(c => {
      const clusterEntities = [...c.entities, ...c.assets].map(e => e.toLowerCase());
      return clusterEntities.some(e => entitySet.has(e));
    });

    // Convert to legacy format for Python adapter
    return relevant.flatMap(c => c.events.slice(0, 2).map(e => ({
      title: e.title,
      text: (e as any).text || e.title,
      source: e.sourceName,
      source_type: (e as any).sourceType || 'news',
      source_quality: c.avgTrustScore,
      relevance_score: c.relevanceScore,
    })));
  }

  /**
   * Get feed stats for monitoring.
   */
  async getStats(): Promise<{
    sources: { tier1: number; tier2: number; tier3: number; total: number };
    feed: { totalRaw: number; totalClusters: number; breaking: number; critical: number; high: number };
    topClusters: { title: string; priority: number; band: string; sources: number; assets: string[] }[];
  }> {
    const allSources = sourceRegistryService.getAll();
    const feed = await this.buildFeed({ hoursBack: 24, limit: 50 });

    return {
      sources: {
        tier1: allSources.filter(s => s.tier === 1).length,
        tier2: allSources.filter(s => s.tier === 2).length,
        tier3: allSources.filter(s => s.tier === 3).length,
        total: allSources.length,
      },
      feed: {
        totalRaw: feed.meta.totalRawEvents,
        totalClusters: feed.meta.totalClusters,
        breaking: feed.clusters.filter(c => c.isBreaking).length,
        critical: feed.meta.criticalCount,
        high: feed.meta.highCount,
      },
      topClusters: feed.clusters.slice(0, 10).map(c => ({
        title: c.canonicalTitle.slice(0, 100),
        priority: c.priority,
        band: c.priorityBand,
        sources: c.sourcesCount,
        assets: c.assets,
      })),
    };
  }

  /**
   * Fetch raw events from MongoDB (notification_events + raw_events).
   */
  private async fetchRawEvents(since: Date, asset?: string): Promise<RawFeedEvent[]> {
    const events: RawFeedEvent[] = [];

    try {
      const db = getDb();

      // Source 1: notification_events
      const neFilter: Record<string, any> = {};
      if (asset) {
        neFilter['$or'] = [
          { assets: asset },
          { entities: { $in: [asset] } },
          { title: { $regex: asset, $options: 'i' } },
          { 'data.symbol': asset.toUpperCase() },
        ];
      }

      const neDocs = await db.collection('notification_events')
        .find(neFilter, { projection: { _id: 0 } })
        .sort({ timestamp: -1, created_at: -1 })
        .limit(300)
        .toArray();

      for (const d of neDocs) {
        const ts = d.created_at ? new Date(d.created_at) : (d.timestamp ? new Date(d.timestamp) : new Date());
        if (ts < since) continue;

        events.push({
          externalId: d.id || d.event_id || `ne_${Math.random().toString(36).slice(2, 10)}`,
          sourceId: (d.source || 'internal').toLowerCase(),
          sourceName: d.source || 'Internal Signal',
          sourceType: this.inferSourceType(d.source || '', d.type || ''),
          sourceTier: 3,
          title: d.title || d.text || '',
          text: d.message || d.description || d.text || '',
          url: d.url || undefined,
          publishedAt: ts,
          rawEntities: d.entities || [],
          rawAssets: d.assets || (d.data?.symbol ? [d.data.symbol] : []),
        });
      }

      // Source 2: raw_events (from news ingestion)
      const reFilter: Record<string, any> = {
        publishedAt: { $gte: since },
      };
      if (asset) {
        reFilter.assetMentions = asset.toUpperCase();
      }

      const reDocs = await db.collection('raw_events')
        .find(reFilter, { projection: { _id: 0 } })
        .sort({ publishedAt: -1 })
        .limit(300)
        .toArray();

      for (const d of reDocs) {
        events.push({
          externalId: d.externalId || `re_${Math.random().toString(36).slice(2, 10)}`,
          sourceId: d.source?.id || d.publisher?.name?.toLowerCase() || 'unknown',
          sourceName: d.source?.name || d.publisher?.name || 'Unknown',
          sourceType: 'news' as SourceType,
          sourceTier: this.parseTier(d.source?.tier || d.raw?.feedTier),
          title: d.title || '',
          text: d.text || d.content || '',
          url: d.url || undefined,
          publishedAt: new Date(d.publishedAt),
          rawEntities: [],
          rawAssets: d.assetMentions || [],
        });
      }
    } catch (err: any) {
      console.error(`[EventFeed] Error fetching raw events: ${err.message}`);
    }

    // Sort by published date descending
    events.sort((a, b) => b.publishedAt.getTime() - a.publishedAt.getTime());

    return events;
  }

  private inferSourceType(source: string, type: string): SourceType {
    const lower = `${source} ${type}`.toLowerCase();
    if (lower.includes('twitter') || lower.includes('tweet')) return 'twitter';
    if (lower.includes('sec') || lower.includes('cftc') || lower.includes('regulatory')) return 'regulatory';
    if (lower.includes('official') || lower.includes('announcement')) return 'official';
    if (lower.includes('onchain') || lower.includes('chain')) return 'onchain';
    return 'news';
  }

  private parseTier(tier: string | undefined): 1 | 2 | 3 {
    if (!tier) return 3;
    if (tier === 'A' || tier === '1') return 1;
    if (tier === 'B' || tier === '2') return 2;
    return 3;
  }
}

export const feedOrchestratorService = new FeedOrchestratorService();
