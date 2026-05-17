/**
 * News Intelligence Pipeline v2
 * ==============================
 * Orchestrates: raw_events → clustering → scoring → ranked feed
 *
 * Reads from raw_events (sourceType: 'news'), never from ML collections.
 * NO AI, NO OpenAI. Pure algorithmic processing.
 */

import mongoose from 'mongoose';
import { newsClusteringService, type RawNewsEvent, type NewsCluster } from './clustering.service.js';
import { newsScoringService, getImportanceBand } from './scoring.service.js';

export interface FeedQuery {
  limit?: number;
  hoursBack?: number;
  asset?: string;
  eventType?: string;
  breakingOnly?: boolean;
  importanceBand?: 'high' | 'medium' | 'low';
  page?: number;
}

export interface NewsFeedResult {
  clusters: NewsCluster[];
  meta: {
    totalRawEvents: number;
    totalClusters: number;
    breakingCount: number;
    highCount: number;
    mediumCount: number;
    lowCount: number;
    timeRangeHours: number;
    compressionRatio: number;
    page: number;
    limit: number;
    generatedAt: Date;
  };
}

class NewsIntelligencePipeline {
  /**
   * Build the ranked news feed.
   */
  async buildFeed(query: FeedQuery = {}): Promise<NewsFeedResult> {
    const limit = query.limit ?? 20;
    const hoursBack = query.hoursBack ?? 24;
    const page = query.page ?? 1;
    const since = new Date(Date.now() - hoursBack * 60 * 60 * 1000);

    // Step 1: Fetch raw news events
    const rawEvents = await this.fetchRawNewsEvents(since, query.asset);

    // Step 2: Cluster
    let clusters = newsClusteringService.buildClusters(rawEvents);

    // Step 3: Score and rank
    clusters = newsScoringService.scoreAndRank(clusters);

    // Count before filtering
    const totalClusters = clusters.length;
    const breakingCount = clusters.filter(c => c.isBreaking).length;
    const highCount = clusters.filter(c => c.importanceBand === 'high').length;
    const mediumCount = clusters.filter(c => c.importanceBand === 'medium').length;
    const lowCount = clusters.filter(c => c.importanceBand === 'low').length;

    // Step 4: Filter
    if (query.eventType) {
      clusters = clusters.filter(c => c.eventType === query.eventType);
    }
    if (query.breakingOnly) {
      clusters = clusters.filter(c => c.isBreaking);
    }
    if (query.importanceBand) {
      clusters = clusters.filter(c => c.importanceBand === query.importanceBand);
    }

    // Step 5: Paginate
    const offset = (page - 1) * limit;
    const paginated = clusters.slice(offset, offset + limit);

    const compressionRatio = rawEvents.length > 0 && totalClusters > 0
      ? Math.round((rawEvents.length / totalClusters) * 10) / 10
      : 1;

    return {
      clusters: paginated,
      meta: {
        totalRawEvents: rawEvents.length,
        totalClusters,
        breakingCount,
        highCount,
        mediumCount,
        lowCount,
        timeRangeHours: hoursBack,
        compressionRatio,
        page,
        limit,
        generatedAt: new Date(),
      },
    };
  }

  /**
   * Get cluster stats for monitoring.
   */
  async getClusterStats(): Promise<{
    totalRawNews: number;
    totalClusters: number;
    avgClusterSize: number;
    singleSourceClusters: number;
    multiSourceClusters: number;
    breakingCount: number;
    eventTypeDistribution: Record<string, number>;
    importanceDistribution: { high: number; medium: number; low: number };
    compressionRatio: number;
    topClusters: { title: string; importance: number; band: string; sources: number; type: string }[];
  }> {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const rawEvents = await this.fetchRawNewsEvents(since);
    let clusters = newsClusteringService.buildClusters(rawEvents);
    clusters = newsScoringService.scoreAndRank(clusters);

    const eventTypes: Record<string, number> = {};
    let high = 0, medium = 0, low = 0;

    for (const c of clusters) {
      eventTypes[c.eventType] = (eventTypes[c.eventType] || 0) + 1;
      if (c.importanceBand === 'high') high++;
      else if (c.importanceBand === 'medium') medium++;
      else low++;
    }

    const singleSource = clusters.filter(c => c.sourcesCount === 1).length;
    const multiSource = clusters.filter(c => c.sourcesCount > 1).length;
    const avgSize = clusters.length > 0
      ? Math.round((rawEvents.length / clusters.length) * 10) / 10
      : 0;

    const topClusters = clusters.slice(0, 10).map(c => ({
      title: c.title.slice(0, 80),
      importance: c.importance,
      band: c.importanceBand,
      sources: c.sourcesCount,
      type: c.eventType,
    }));

    return {
      totalRawNews: rawEvents.length,
      totalClusters: clusters.length,
      avgClusterSize: avgSize,
      singleSourceClusters: singleSource,
      multiSourceClusters: multiSource,
      breakingCount: clusters.filter(c => c.isBreaking).length,
      eventTypeDistribution: eventTypes,
      importanceDistribution: { high, medium, low },
      compressionRatio: clusters.length > 0
        ? Math.round((rawEvents.length / clusters.length) * 10) / 10 : 1,
      topClusters,
    };
  }

  /**
   * Fetch raw news events from MongoDB.
   */
  private async fetchRawNewsEvents(since: Date, asset?: string): Promise<RawNewsEvent[]> {
    const db = mongoose.connection.db;
    if (!db) return [];

    const filter: Record<string, any> = {
      sourceType: 'news',
      publishedAt: { $gte: since },
    };

    if (asset) {
      filter.assetMentions = asset.toUpperCase();
    }

    const docs = await db.collection('raw_events')
      .find(filter, {
        projection: {
          _id: 0,
          externalId: 1,
          title: 1,
          text: 1,
          url: 1,
          publishedAt: 1,
          publisher: 1,
          assetMentions: 1,
          raw: 1,
        },
      })
      .sort({ publishedAt: -1 })
      .limit(500)
      .toArray();

    return docs.map(d => ({
      externalId: d.externalId,
      title: d.title || '',
      text: d.text || '',
      url: d.url,
      publishedAt: new Date(d.publishedAt),
      publisher: d.publisher || { name: 'Unknown', domain: '' },
      assetMentions: d.assetMentions || [],
      raw: d.raw || {},
    }));
  }
}

export const newsIntelligencePipeline = new NewsIntelligencePipeline();
