/**
 * News Importance Scoring v3
 * ==========================
 * Improved scoring with:
 *  - Calibrated thresholds for realistic HIGH distribution (5-15%)
 *  - "Exclusive scoop" bonus for Tier A single-source fresh events
 *  - Stronger velocity detection
 *  - Better noise calibration
 *
 * Components (0–100):
 *   Source Tier      (0–22)
 *   Multi-source     (0–20)
 *   Recency          (0–18)
 *   Event Type       (0–20)
 *   Asset Relevance  (0–8)
 *   Velocity         (0–12)
 *   × Noise Penalty  (0.5–1.0)
 *   + Exclusive Bonus (0–8)
 *
 * NO AI, NO ML. Pure deterministic scoring.
 */

import type { NewsCluster } from './clustering.service.js';

// ── Importance Components ───────────────────────────────────────

function getSourceTierPoints(tier: string, additionalSources: number): number {
  let base: number;
  switch (tier) {
    case 'A': base = 22; break;
    case 'B': base = 15; break;
    case 'C': base = 8;  break;
    default:  base = 5;
  }
  // Diminishing returns for additional sources
  return base + Math.min(5, additionalSources * 2);
}

function getMultiSourcePoints(uniqueSources: number): number {
  // P3: Use logarithmic scaling — duplicates from same source don't inflate importance
  // log2(1) = 0, log2(2) = 1, log2(3) = 1.58, log2(5) = 2.32
  if (uniqueSources <= 1) return 0;
  
  // Logarithmic with cap at 20
  const logPoints = Math.log2(uniqueSources) * 8.6;  // log2(5) * 8.6 ≈ 20
  return Math.min(20, Math.round(logPoints));
}

/**
 * P2: Cluster Purity multiplier.
 * Boosts multi-source clusters, penalizes weak single-source clusters.
 * Returns a multiplier (0.0 – 1.3).
 */
function getClusterPurityMultiplier(cluster: NewsCluster, bestTier: string): number {
  const uniqueSources = cluster.sourcesCount;
  
  // ═══ SINGLE SOURCE ═══
  if (uniqueSources === 1) {
    // Single Tier C → heavy penalty (likely noise)
    if (bestTier === 'C') return 0.3;
    // Single Tier B → mild penalty
    if (bestTier === 'B') return 0.7;
    // Single Tier A → slight penalty (could be exclusive scoop)
    return 0.9;
  }
  
  // ═══ MULTI-SOURCE BOOST ═══
  if (uniqueSources >= 3) return 1.2;  // strong boost
  if (uniqueSources >= 2) return 1.1;  // moderate boost
  
  return 1.0;
}

/**
 * P2: Sentiment conflict penalty.
 * If cluster has conflicting sentiment signals, reduce confidence.
 * Returns multiplier (0.7 – 1.0).
 */
function getSentimentConflictPenalty(cluster: NewsCluster): number {
  // Check if cluster events have mixed sentiment hints
  if (!cluster.events || cluster.events.length < 2) return 1.0;
  
  const hints = cluster.events
    .map(e => (e as any).sentimentHint)
    .filter(Boolean);
  
  if (hints.length < 2) return 1.0;
  
  const hasPositive = hints.some(h => h === 'positive' || h === 'bullish');
  const hasNegative = hints.some(h => h === 'negative' || h === 'bearish');
  
  // Conflicting signals → reduce confidence
  if (hasPositive && hasNegative) return 0.7;
  
  return 1.0;
}

function getRecencyPoints(minutesSinceFirstSeen: number): number {
  if (minutesSinceFirstSeen <= 15)  return 18;
  if (minutesSinceFirstSeen <= 45)  return 16;
  if (minutesSinceFirstSeen <= 120) return 14;
  if (minutesSinceFirstSeen <= 360) return 10;
  if (minutesSinceFirstSeen <= 720) return 6;
  if (minutesSinceFirstSeen <= 1440) return 3;
  return 1;
}

function getEventTypePoints(eventType: string): number {
  switch (eventType) {
    case 'exploit':
    case 'hack':        return 20;
    case 'regulation':
    case 'etf':         return 18;
    case 'listing':
    case 'delisting':   return 16;
    case 'funding':
    case 'macro':       return 14;
    case 'upgrade':
    case 'partnership': return 11;
    case 'whale':       return 9;
    case 'market':      return 7;
    case 'price':       return 5;
    default:            return 4;
  }
}

function getAssetRelevancePoints(assets: string[]): number {
  if (!assets?.length) return 2;
  if (assets.includes('BTC') || assets.includes('ETH')) return 8;
  if (assets.length >= 3) return 7;
  if (assets.length >= 2) return 6;
  return 4;
}

function getVelocityPoints(eventsCount: number, ageMinutes: number): number {
  if (ageMinutes <= 0) return eventsCount >= 2 ? 12 : 3;
  const velocity = (eventsCount / ageMinutes) * 60; // events per hour
  if (velocity >= 6) return 12;
  if (velocity >= 4) return 10;
  if (velocity >= 2) return 7;
  if (velocity >= 1) return 4;
  if (eventsCount >= 2) return 3;
  return 0;
}

/**
 * Exclusive scoop bonus: single-source Tier A/B fresh stories
 * with critical event types deserve a boost even without multi-source.
 */
function getExclusiveBonus(cluster: NewsCluster, bestTier: string, ageMinutes: number): number {
  if (cluster.sourcesCount > 1) return 0; // Not exclusive
  if (ageMinutes > 180) return 0; // Too old

  const criticalTypes = new Set(['hack', 'exploit', 'regulation', 'etf', 'listing', 'funding']);
  const isCritical = criticalTypes.has(cluster.eventType);

  if (bestTier === 'A' && isCritical && ageMinutes <= 60) return 8;
  if (bestTier === 'A' && isCritical) return 5;
  if (bestTier === 'A' && ageMinutes <= 60) return 4;
  if (bestTier === 'B' && isCritical && ageMinutes <= 60) return 3;
  return 0;
}

function getNoisePenalty(cluster: NewsCluster, bestTier: string): number {
  const ageMinutes = (Date.now() - cluster.firstSeenAt.getTime()) / 60000;

  // Harsh penalty: single Tier C source, old, no asset
  if (cluster.sourcesCount === 1 && bestTier === 'C' && ageMinutes > 360 && !cluster.primaryAsset) return 0.5;
  if (cluster.sourcesCount === 1 && bestTier === 'C' && ageMinutes > 360) return 0.6;
  if (cluster.events.length === 1 && !cluster.primaryAsset && bestTier === 'C') return 0.7;
  if (cluster.sourcesCount === 1 && bestTier === 'C') return 0.85;
  return 1.0;
}

// ── Importance Bands ────────────────────────────────────────────

export type ImportanceBand = 'high' | 'medium' | 'low';

export function getImportanceBand(score: number): ImportanceBand {
  if (score >= 65) return 'high';
  if (score >= 40) return 'medium';
  return 'low';
}

// ── Breaking Detection ──────────────────────────────────────────

export function computeIsBreaking(
  importanceScore: number,
  uniqueSources: number,
  minutesSinceFirstSeen: number,
): boolean {
  // Breaking: high importance + multi-source + recent
  if (importanceScore >= 65 && uniqueSources >= 2 && minutesSinceFirstSeen <= 120) return true;
  // Also breaking: very high importance even with 1 source (Tier A exclusive scoop)
  if (importanceScore >= 75 && minutesSinceFirstSeen <= 60) return true;
  return false;
}

// ── Feed Rank Score ─────────────────────────────────────────────

function getFreshnessScore(minutes: number): number {
  if (minutes <= 10)  return 100;
  if (minutes <= 30)  return 90;
  if (minutes <= 60)  return 75;
  if (minutes <= 180) return 55;
  if (minutes <= 360) return 35;
  if (minutes <= 720) return 15;
  return 5;
}

function getSourceDiversityScore(uniqueSources: number): number {
  return Math.min(100, uniqueSources * 25);
}

// ── Helper ──────────────────────────────────────────────────────

function getBestTier(cluster: NewsCluster): string {
  const order = ['A', 'B', 'C'];
  let best = 'C';
  for (const event of cluster.events) {
    const tier = event.tier || 'C';
    if (order.indexOf(tier) < order.indexOf(best)) best = tier;
  }
  return best;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

// ── Main Scoring Service ────────────────────────────────────────

class NewsScoringService {
  /**
   * Score a cluster. Returns importanceScore (0–100).
   * Mutates cluster in place.
   */
  scoreCluster(cluster: NewsCluster): number {
    const bestTier = getBestTier(cluster);
    const additionalSources = Math.max(0, cluster.sourcesCount - 1);
    const ageMinutes = (Date.now() - cluster.firstSeenAt.getTime()) / 60000;

    // Components
    const tierPts      = getSourceTierPoints(bestTier, additionalSources);
    const multiPts     = getMultiSourcePoints(cluster.sourcesCount);
    const recencyPts   = getRecencyPoints(ageMinutes);
    const eventPts     = getEventTypePoints(cluster.eventType);
    const assetPts     = getAssetRelevancePoints(cluster.assets);
    const velocityPts  = getVelocityPoints(cluster.events.length, ageMinutes);
    const noise        = getNoisePenalty(cluster, bestTier);
    const exclusive    = getExclusiveBonus(cluster, bestTier, ageMinutes);

    const raw = (tierPts + multiPts + recencyPts + eventPts + assetPts + velocityPts) * noise + exclusive;
    
    // P2: Apply cluster purity multiplier + sentiment conflict penalty
    const purity = getClusterPurityMultiplier(cluster, bestTier);
    const sentimentConflict = getSentimentConflictPenalty(cluster);
    
    const importanceScore = clamp(Math.round(raw * purity * sentimentConflict), 0, 100);

    // Breaking
    const isBreaking = computeIsBreaking(importanceScore, cluster.sourcesCount, ageMinutes);

    // Feed rank score
    const freshness = getFreshnessScore(ageMinutes);
    const sourceDiversity = getSourceDiversityScore(cluster.sourcesCount);
    const breakingBoost = isBreaking ? 100 : 0;

    const feedRankScore = Math.round(
      importanceScore * 0.60 +
      freshness * 0.22 +
      sourceDiversity * 0.08 +
      breakingBoost * 0.10
    );

    // Mutate cluster
    cluster.importance = importanceScore;
    cluster.importanceBand = getImportanceBand(importanceScore);
    cluster.isBreaking = isBreaking;
    cluster.feedRankScore = feedRankScore;

    return importanceScore;
  }

  /**
   * Score and sort all clusters by feedRankScore.
   */
  scoreAndRank(clusters: NewsCluster[]): NewsCluster[] {
    for (const cluster of clusters) {
      this.scoreCluster(cluster);
    }

    // Sort: breaking first, then by feedRankScore desc
    clusters.sort((a, b) => {
      if (a.isBreaking !== b.isBreaking) return a.isBreaking ? -1 : 1;
      return (b.feedRankScore ?? 0) - (a.feedRankScore ?? 0);
    });

    return clusters;
  }
}

export const newsScoringService = new NewsScoringService();
