/**
 * Source Quality Service
 * =====================
 * Dynamic source scoring based on real performance metrics.
 * 
 * sourceScore = f(successRate, errorRate, latency, duplicationRate, signalImpact)
 * 
 * signalImpact = how often source appears in HIGH importance clusters.
 * 
 * Updates periodically (every 30 min) and caches results.
 * Used by scoring.service.ts to weight importance.
 */

import mongoose from 'mongoose';

export interface SourceQualityScore {
  sourceId: string;
  sourceName: string;
  staticTier: 'A' | 'B' | 'C';    // From registry
  dynamicTier: 'A' | 'B' | 'C';   // Computed from performance
  sourceScore: number;              // 0.0 – 1.0
  
  // Component scores (0.0 – 1.0)
  reliabilityScore: number;    // f(successRate, errorRate)
  latencyScore: number;        // f(avgLatencyMs)
  signalImpactScore: number;   // f(highClusterRate)
  duplicationScore: number;    // f(unique content ratio)
  
  // Raw metrics
  metrics: {
    totalFetches: number;
    successRate: number;
    avgLatencyMs: number;
    consecutiveFailures: number;
    highClusterHits: number;    // Times source appeared in HIGH clusters
    totalClusterHits: number;   // Total cluster participations
    highClusterRate: number;    // highClusterHits / totalClusterHits
  };
  
  lastUpdatedAt: Date;
}

// Weights for composite score
const W_RELIABILITY = 0.30;
const W_LATENCY = 0.10;
const W_SIGNAL_IMPACT = 0.45;  // Key factor per user request
const W_DUPLICATION = 0.15;

class SourceQualityService {
  private cache: Map<string, SourceQualityScore> = new Map();
  private lastRefreshAt = 0;
  private readonly REFRESH_INTERVAL_MS = 30 * 60 * 1000; // 30 min
  private timer: NodeJS.Timeout | null = null;

  /**
   * Start periodic refresh
   */
  start(): void {
    console.log('[SourceQuality] Starting periodic refresh (30min)');
    // Initial refresh after 30 seconds (let data accumulate)
    setTimeout(() => this.refresh(), 30_000);
    this.timer = setInterval(() => this.refresh(), this.REFRESH_INTERVAL_MS);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  /**
   * Get source score for a given source ID.
   * Returns 0.5 (neutral) if source not found.
   */
  getScore(sourceId: string): number {
    const entry = this.cache.get(sourceId);
    return entry?.sourceScore ?? 0.5;
  }

  /**
   * Get dynamic tier for a given source ID.
   * Falls back to static tier or 'C'.
   */
  getDynamicTier(sourceId: string): 'A' | 'B' | 'C' {
    const entry = this.cache.get(sourceId);
    return entry?.dynamicTier ?? 'C';
  }

  /**
   * Get weight multiplier for importance scoring.
   * Tier A → 1.0, Tier B → 0.7, Tier C → 0.4
   */
  getSourceWeight(sourceId: string): number {
    const tier = this.getDynamicTier(sourceId);
    switch (tier) {
      case 'A': return 1.0;
      case 'B': return 0.7;
      case 'C': return 0.4;
      default: return 0.5;
    }
  }

  /**
   * Get all scores for admin UI
   */
  getAllScores(): SourceQualityScore[] {
    return Array.from(this.cache.values()).sort((a, b) => b.sourceScore - a.sourceScore);
  }

  /**
   * Get summary statistics
   */
  getSummary(): { total: number; tierA: number; tierB: number; tierC: number; avgScore: number; lastRefreshAt: Date | null } {
    const all = this.getAllScores();
    return {
      total: all.length,
      tierA: all.filter(s => s.dynamicTier === 'A').length,
      tierB: all.filter(s => s.dynamicTier === 'B').length,
      tierC: all.filter(s => s.dynamicTier === 'C').length,
      avgScore: all.length > 0 ? Math.round(all.reduce((sum, s) => sum + s.sourceScore, 0) / all.length * 100) / 100 : 0,
      lastRefreshAt: this.lastRefreshAt > 0 ? new Date(this.lastRefreshAt) : null,
    };
  }

  /**
   * Refresh all source scores from MongoDB
   */
  private async refresh(): Promise<void> {
    try {
      const db = mongoose.connection.db;
      if (!db) return;

      // Step 1: Fetch source registry data
      const sources = await db.collection('news_sources').find({}).toArray();
      if (sources.length === 0) return;

      // Step 2: Fetch cluster participation stats (last 24h)
      const highClusterStats = await this.getClusterStats(db);

      // Step 3: Compute scores
      for (const src of sources) {
        const sourceId = src.id as string;
        const staticTier = (src.tier || 'C') as 'A' | 'B' | 'C';

        // Reliability score
        const totalFetches = (src.totalFetches || 0) as number;
        const successRate = totalFetches > 0 ? ((src.totalSuccess || 0) as number / totalFetches) : 0;
        const reliabilityScore = Math.min(1, successRate);

        // Latency score (lower is better)
        const avgLatencyMs = (src.avgLatencyMs || 5000) as number;
        const latencyScore = avgLatencyMs < 1000 ? 1.0 : avgLatencyMs < 3000 ? 0.8 : avgLatencyMs < 5000 ? 0.6 : avgLatencyMs < 10000 ? 0.4 : 0.2;

        // Signal impact score  
        const clusterData = highClusterStats.get(sourceId);
        const highClusterHits = clusterData?.highHits || 0;
        const totalClusterHits = clusterData?.totalHits || 0;
        const highClusterRate = totalClusterHits > 0 ? highClusterHits / totalClusterHits : 0;
        const signalImpactScore = Math.min(1, highClusterRate * 3); // Scale: 33% high rate → 1.0

        // Duplication score (lower duplication → higher score)
        const totalArticles = (src.totalArticles || 0) as number;
        const duplicationScore = totalArticles > 0 ? Math.min(1, 0.5 + (totalArticles > 10 ? 0.5 : totalArticles / 20)) : 0.3;

        // Composite score
        const sourceScore = Math.round((
          W_RELIABILITY * reliabilityScore +
          W_LATENCY * latencyScore +
          W_SIGNAL_IMPACT * signalImpactScore +
          W_DUPLICATION * duplicationScore
        ) * 100) / 100;

        // Dynamic tier assignment
        let dynamicTier: 'A' | 'B' | 'C';
        if (sourceScore >= 0.65) dynamicTier = 'A';
        else if (sourceScore >= 0.35) dynamicTier = 'B';
        else dynamicTier = 'C';

        // Blend with static tier (don't completely override)
        if (staticTier === 'A' && dynamicTier === 'C') dynamicTier = 'B'; // Don't drop Tier A to C
        if (staticTier === 'C' && dynamicTier === 'A' && totalFetches < 10) dynamicTier = 'B'; // Don't promote too fast

        this.cache.set(sourceId, {
          sourceId,
          sourceName: (src.name || sourceId) as string,
          staticTier,
          dynamicTier,
          sourceScore,
          reliabilityScore,
          latencyScore,
          signalImpactScore,
          duplicationScore,
          metrics: {
            totalFetches,
            successRate: Math.round(successRate * 100) / 100,
            avgLatencyMs: Math.round(avgLatencyMs),
            consecutiveFailures: (src.consecutiveFailures || 0) as number,
            highClusterHits,
            totalClusterHits,
            highClusterRate: Math.round(highClusterRate * 100) / 100,
          },
          lastUpdatedAt: new Date(),
        });
      }

      this.lastRefreshAt = Date.now();
      console.log(`[SourceQuality] Refreshed ${this.cache.size} sources. Summary:`, this.getSummary());
    } catch (err: any) {
      console.error(`[SourceQuality] Refresh failed: ${err.message}`);
    }
  }

  /**
   * Get cluster participation stats per source (last 24h).
   * Scans raw_events and correlates with importance scores.
   */
  private async getClusterStats(db: any): Promise<Map<string, { highHits: number; totalHits: number }>> {
    const stats = new Map<string, { highHits: number; totalHits: number }>();

    try {
      // Get recent raw events grouped by source
      const since = new Date(Date.now() - 24 * 60 * 60 * 1000);
      const events = await db.collection('raw_events')
        .find({ sourceType: 'news', createdAt: { $gte: since } })
        .project({ 'source.id': 1, 'source.name': 1, importance: 1, importanceBand: 1 })
        .limit(5000)
        .toArray();

      for (const event of events) {
        const sourceId = event.source?.id || event.source?.name || 'unknown';
        let entry = stats.get(sourceId);
        if (!entry) {
          entry = { highHits: 0, totalHits: 0 };
          stats.set(sourceId, entry);
        }
        entry.totalHits++;
        if (event.importanceBand === 'high' || (event.importance && event.importance >= 65)) {
          entry.highHits++;
        }
      }
    } catch {
      // Non-critical - stats will be empty
    }

    return stats;
  }

  /**
   * Record that a source appeared in a cluster with given importance.
   * Called by pipeline after scoring.
   */
  recordClusterParticipation(sourceId: string, importanceBand: string): void {
    const entry = this.cache.get(sourceId);
    if (!entry) return;
    
    entry.metrics.totalClusterHits++;
    if (importanceBand === 'high') {
      entry.metrics.highClusterHits++;
    }
    entry.metrics.highClusterRate = entry.metrics.totalClusterHits > 0
      ? Math.round((entry.metrics.highClusterHits / entry.metrics.totalClusterHits) * 100) / 100
      : 0;
  }
}

export const sourceQualityService = new SourceQualityService();
