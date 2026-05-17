/**
 * Relevance Filter Service
 *
 * Scores how relevant each event cluster is to Polymarket prediction markets.
 * High relevance: events that directly affect market resolution (ETF decisions,
 * regulatory actions, price milestones, project launches).
 * Low relevance: generic market commentary, opinion pieces, price predictions.
 *
 * relevanceScore = f(eventType, entities, assets, sourceTier, actionability)
 */

import type { EventCluster } from '../types/event-feed.types.js';

// Event types and their base relevance to prediction markets
const EVENT_TYPE_RELEVANCE: Record<string, number> = {
  etf:         0.95,  // ETF filings/approvals directly affect markets
  regulation:  0.90,  // SEC actions, bills affect market resolution
  hack:        0.85,  // Security events can resolve markets
  listing:     0.80,  // Exchange listings affect price markets
  unlock:      0.80,  // Token unlocks affect price markets
  upgrade:     0.75,  // Protocol upgrades, launches
  macro:       0.70,  // Fed, rates — affect broad crypto markets
  funding:     0.65,  // Funding rounds — moderate relevance
  whale:       0.60,  // Whale movements — informational
  partnership: 0.55,  // Partnerships — moderate
  price:       0.50,  // Price commentary — often noise
  market:      0.40,  // Generic market news
};

// Entities that increase relevance (they appear in Polymarket questions)
const HIGH_RELEVANCE_ENTITIES = new Set([
  'SEC', 'CFTC', 'Federal Reserve', 'BlackRock', 'Grayscale',
  'VanEck', 'Fidelity', 'MicroStrategy', 'Trump', 'SBF',
  'Coinbase', 'Binance', 'White House', 'US Treasury',
]);

// Assets commonly traded on Polymarket
const POLYMARKET_ASSETS = new Set([
  'BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA', 'AVAX', 'DOT',
  'MATIC', 'LINK', 'UNI', 'ARB', 'OP', 'HYPE', 'SUI', 'APT',
]);

class RelevanceFilterService {
  /**
   * Score cluster relevance to Polymarket markets.
   * Returns 0.0–1.0.
   */
  score(cluster: EventCluster): number {
    let score = 0;

    // 1. Event type relevance (40%)
    const typeRelevance = EVENT_TYPE_RELEVANCE[cluster.eventType] ?? 0.40;
    score += typeRelevance * 0.40;

    // 2. Entity match (25%)
    const entityMatch = cluster.entities.some(e => HIGH_RELEVANCE_ENTITIES.has(e));
    score += (entityMatch ? 0.90 : 0.30) * 0.25;

    // 3. Asset match (20%)
    const assetMatch = cluster.assets.some(a => POLYMARKET_ASSETS.has(a));
    score += (assetMatch ? 0.85 : 0.20) * 0.20;

    // 4. Source quality (15%)
    const tierScore = cluster.bestSourceTier === 1 ? 1.0
      : cluster.bestSourceTier === 2 ? 0.75 : 0.45;
    score += tierScore * 0.15;

    return Math.round(Math.min(1, Math.max(0, score)) * 100) / 100;
  }

  /**
   * Score and annotate a list of clusters.
   * Filters out very low relevance (< 0.15) unless they're from Tier 1.
   */
  filterAndScore(clusters: EventCluster[]): EventCluster[] {
    return clusters
      .map(c => {
        const relevanceScore = this.score(c);
        return { ...c, relevanceScore };
      })
      .filter(c => c.relevanceScore >= 0.15 || c.bestSourceTier === 1);
  }
}

export const relevanceFilterService = new RelevanceFilterService();
