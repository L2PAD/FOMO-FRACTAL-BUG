/**
 * News Health Service
 * ===================
 * Aggregates health metrics for the news ingestion pipeline.
 * Provides: total/active sources, event flow rates, error rates,
 * top/failing sources, alerts.
 *
 * CONTROL LAYER — no AI, no clustering, no ML impact.
 */

import mongoose from 'mongoose';
import { newsSourceRegistryService } from './news-source-registry.service.js';

const METRICS_COLLECTION = 'ingestion_runs';
const RAW_EVENTS_COLLECTION = 'raw_events';

// Thresholds
const RATE_GUARD_THRESHOLD = 200;    // events per 5 min → warning
const EMPTY_WINDOW_MINUTES = 60;     // 0 events in window → alert

export interface NewsHealthSnapshot {
  totalSources: number;
  activeSources: number;
  healthySources: number;
  unhealthySources: number;

  lastRunAt: Date | null;
  lastSuccessAt: Date | null;

  eventsLast1h: number;
  eventsLast6h: number;
  eventsLast24h: number;

  errorRate: number;
  avgLatencyMs: number;
  dedupeRate: number;

  topSources: { name: string; articles: number; tier: string }[];
  failingSources: { name: string; error: string; consecutiveFailures: number }[];

  alerts: NewsAlert[];
}

export interface NewsAlert {
  type: 'rate_guard' | 'empty_feed' | 'source_failure' | 'high_error_rate';
  severity: 'warning' | 'critical';
  message: string;
  timestamp: Date;
}

class NewsHealthService {
  /**
   * Build comprehensive health snapshot.
   */
  async getHealth(): Promise<NewsHealthSnapshot> {
    const db = mongoose.connection.db;
    if (!db) {
      return this.emptySnapshot();
    }

    const sources = await newsSourceRegistryService.getAll();
    const alerts: NewsAlert[] = [];

    // Source stats
    const totalSources = sources.length;
    const activeSources = sources.filter(s => s.enabled).length;
    const healthySources = sources.filter(s => s.healthy && s.enabled).length;
    const unhealthySources = sources.filter(s => !s.healthy && s.enabled).length;

    // Top sources (by total articles)
    const topSources = sources
      .filter(s => s.totalArticles > 0)
      .sort((a, b) => b.totalArticles - a.totalArticles)
      .slice(0, 5)
      .map(s => ({ name: s.name, articles: s.totalArticles, tier: s.tier }));

    // Failing sources
    const failingSources = sources
      .filter(s => s.consecutiveFailures > 0)
      .sort((a, b) => b.consecutiveFailures - a.consecutiveFailures)
      .map(s => ({
        name: s.name,
        error: s.lastError || 'Unknown',
        consecutiveFailures: s.consecutiveFailures,
      }));

    // Add source failure alerts
    for (const s of sources) {
      if (s.consecutiveFailures >= 3 && s.enabled) {
        alerts.push({
          type: 'source_failure',
          severity: 'critical',
          message: `${s.name}: ${s.consecutiveFailures} consecutive failures. Last error: ${s.lastError}`,
          timestamp: s.lastErrorAt || new Date(),
        });
      }
    }

    // Ingestion run metrics
    const metricsCol = db.collection(METRICS_COLLECTION);
    const now = Date.now();
    const oneHourAgo = new Date(now - 60 * 60 * 1000);
    const sixHoursAgo = new Date(now - 6 * 60 * 60 * 1000);

    // Last news run
    const lastRun = await metricsCol.findOne(
      { source: 'rss-news' },
      { sort: { finishedAt: -1 }, projection: { _id: 0 } }
    );

    const lastSuccess = await metricsCol.findOne(
      { source: 'rss-news', inserted: { $gt: 0 } },
      { sort: { finishedAt: -1 }, projection: { _id: 0 } }
    );

    // News runs in last hour
    const newsRuns1h = await metricsCol
      .find({ source: 'rss-news', startedAt: { $gte: oneHourAgo } })
      .toArray();

    let totalFetched1h = 0;
    let totalInserted1h = 0;
    let totalDuplicated1h = 0;
    let totalErrors1h = 0;
    let totalLatency1h = 0;

    for (const run of newsRuns1h) {
      totalFetched1h += run.fetched || 0;
      totalInserted1h += run.inserted || 0;
      totalDuplicated1h += run.duplicated || 0;
      totalErrors1h += run.errors || 0;
      totalLatency1h += run.durationMs || 0;
    }

    const errorRate = totalFetched1h > 0 ? Math.round((totalErrors1h / totalFetched1h) * 100) / 100 : 0;
    const dedupeRate = totalFetched1h > 0 ? Math.round((totalDuplicated1h / totalFetched1h) * 100) / 100 : 0;
    const avgLatencyMs = newsRuns1h.length > 0 ? Math.round(totalLatency1h / newsRuns1h.length) : 0;

    // Count news events by time window
    const eventsCol = db.collection(RAW_EVENTS_COLLECTION);
    const eventsLast1h = await eventsCol.countDocuments({
      sourceType: 'news',
      ingestedAt: { $gte: oneHourAgo },
    });
    const eventsLast6h = await eventsCol.countDocuments({
      sourceType: 'news',
      ingestedAt: { $gte: sixHoursAgo },
    });
    const eventsLast24h = await eventsCol.countDocuments({
      sourceType: 'news',
      ingestedAt: { $gte: new Date(now - 24 * 60 * 60 * 1000) },
    });

    // Rate guard alert
    if (totalInserted1h > RATE_GUARD_THRESHOLD * 12) {
      alerts.push({
        type: 'rate_guard',
        severity: 'warning',
        message: `High insertion rate: ${totalInserted1h} events in last hour (threshold: ${RATE_GUARD_THRESHOLD * 12}/hr)`,
        timestamp: new Date(),
      });
    }

    // Empty feed alert
    const emptyWindowMs = EMPTY_WINDOW_MINUTES * 60 * 1000;
    const lastSuccessTime = lastSuccess?.finishedAt ? new Date(lastSuccess.finishedAt).getTime() : 0;
    if (lastSuccessTime > 0 && (now - lastSuccessTime) > emptyWindowMs) {
      alerts.push({
        type: 'empty_feed',
        severity: 'warning',
        message: `No new articles ingested for ${Math.round((now - lastSuccessTime) / 60000)} minutes`,
        timestamp: new Date(),
      });
    }

    // High error rate alert
    if (errorRate > 0.1) {
      alerts.push({
        type: 'high_error_rate',
        severity: errorRate > 0.3 ? 'critical' : 'warning',
        message: `Error rate ${(errorRate * 100).toFixed(1)}% in last hour`,
        timestamp: new Date(),
      });
    }

    // Avg latency from sources
    const enabledSources = sources.filter(s => s.enabled && s.avgLatencyMs > 0);
    const sourceAvgLatency = enabledSources.length > 0
      ? Math.round(enabledSources.reduce((a, s) => a + s.avgLatencyMs, 0) / enabledSources.length)
      : avgLatencyMs;

    return {
      totalSources,
      activeSources,
      healthySources,
      unhealthySources,
      lastRunAt: lastRun?.finishedAt ?? null,
      lastSuccessAt: lastSuccess?.finishedAt ?? null,
      eventsLast1h,
      eventsLast6h,
      eventsLast24h,
      errorRate,
      avgLatencyMs: sourceAvgLatency,
      dedupeRate,
      topSources,
      failingSources,
      alerts,
    };
  }

  private emptySnapshot(): NewsHealthSnapshot {
    return {
      totalSources: 0, activeSources: 0, healthySources: 0, unhealthySources: 0,
      lastRunAt: null, lastSuccessAt: null,
      eventsLast1h: 0, eventsLast6h: 0, eventsLast24h: 0,
      errorRate: 0, avgLatencyMs: 0, dedupeRate: 0,
      topSources: [], failingSources: [], alerts: [],
    };
  }
}

export const newsHealthService = new NewsHealthService();
