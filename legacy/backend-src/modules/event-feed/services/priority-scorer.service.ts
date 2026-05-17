/**
 * Priority Scorer Service
 *
 * Final priority scoring for event clusters.
 * priority = f(sourceTier, recency, entityMatch, novelty, multiSource, relevance)
 *
 * Bands:
 *   critical (0.80+): Tier 1 source, high relevance, fresh, multi-source
 *   high     (0.60+): Tier 2 source, good relevance, recent
 *   medium   (0.40+): Single source, moderate relevance
 *   low      (<0.40): Noise, old, generic
 */

import type { EventCluster } from '../types/event-feed.types.js';

class PriorityScorerService {
  /**
   * Score and rank clusters by priority.
   * Mutates cluster.priority, cluster.priorityBand, cluster.isBreaking.
   */
  scoreAndRank(clusters: EventCluster[]): EventCluster[] {
    const now = Date.now();

    for (const c of clusters) {
      let score = 0;

      // 1. Source tier (25%)
      const tierScore = c.bestSourceTier === 1 ? 1.0
        : c.bestSourceTier === 2 ? 0.75 : 0.45;
      score += tierScore * 0.25;

      // 2. Recency (20%)
      const ageMs = now - c.firstSeenAt.getTime();
      const ageHours = ageMs / (1000 * 60 * 60);
      const recencyScore = ageHours < 1 ? 1.0
        : ageHours < 4 ? 0.85
        : ageHours < 12 ? 0.65
        : ageHours < 24 ? 0.45
        : 0.20;
      score += recencyScore * 0.20;

      // 3. Multi-source confirmation (15%)
      const multiSourceScore = c.sourcesCount >= 3 ? 1.0
        : c.sourcesCount === 2 ? 0.70
        : 0.30;
      score += multiSourceScore * 0.15;

      // 4. Relevance to Polymarket (20%)
      score += c.relevanceScore * 0.20;

      // 5. Trust score (10%)
      score += c.avgTrustScore * 0.10;

      // 6. Event type urgency (10%)
      const urgencyMap: Record<string, number> = {
        hack: 1.0, regulation: 0.90, etf: 0.85, unlock: 0.80,
        listing: 0.75, macro: 0.70, upgrade: 0.65, funding: 0.50,
        whale: 0.45, partnership: 0.40, price: 0.35, market: 0.25,
      };
      score += (urgencyMap[c.eventType] ?? 0.30) * 0.10;

      c.priority = Math.round(Math.min(1, Math.max(0, score)) * 100) / 100;

      // Assign band
      if (c.priority >= 0.80) c.priorityBand = 'critical';
      else if (c.priority >= 0.60) c.priorityBand = 'high';
      else if (c.priority >= 0.40) c.priorityBand = 'medium';
      else c.priorityBand = 'low';

      // Breaking: critical priority + less than 2h old + multi-source
      c.isBreaking = c.priority >= 0.75 && ageHours < 2 && c.sourcesCount >= 2;
    }

    // Sort by priority descending
    clusters.sort((a, b) => b.priority - a.priority);

    return clusters;
  }
}

export const priorityScorerService = new PriorityScorerService();
