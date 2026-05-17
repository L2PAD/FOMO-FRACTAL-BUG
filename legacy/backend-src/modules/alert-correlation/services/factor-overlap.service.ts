/**
 * Factor Overlap Service
 *
 * Core correlation logic. Computes how much two or more alerts
 * share common factors (theme, asset, catalyst, entity, deadline, resolution).
 *
 * Weights: theme=0.30, asset=0.25, catalyst=0.20, entity=0.15, deadline=0.05, resolution=0.05
 */

import type { RawAlertRef, FactorOverlapResult } from '../types/correlation.types.js';

const WEIGHTS = {
  theme: 0.30,
  asset: 0.25,
  catalyst: 0.20,
  entity: 0.15,
  deadline: 0.05,
  resolution: 0.05,
};

class FactorOverlapService {
  /**
   * Compute overlap score for a group of alerts.
   */
  compute(alerts: RawAlertRef[]): FactorOverlapResult {
    if (alerts.length < 2) {
      return { overlapScore: 0, dominantSharedFactors: [], assetOverlap: 0, themeOverlap: 0, catalystOverlap: 0, entityOverlap: 0 };
    }

    const allAssets = alerts.map(a => new Set(a.factors?.assetFactors || []));
    const allThemes = alerts.map(a => new Set(a.factors?.themeFactors || []));
    const allCatalysts = alerts.map(a => new Set(a.factors?.catalystFactors || []));
    const allEntities = alerts.map(a => new Set(a.factors?.entityFactors || []));
    const allDeadlines = alerts.map(a => new Set(a.factors?.deadlineFactors || []));
    const allResolutions = alerts.map(a => new Set(a.factors?.resolutionFactors || []));

    const assetOverlap = this.pairwiseOverlap(allAssets);
    const themeOverlap = this.pairwiseOverlap(allThemes);
    const catalystOverlap = this.pairwiseOverlap(allCatalysts);
    const entityOverlap = this.pairwiseOverlap(allEntities);
    const deadlineOverlap = this.pairwiseOverlap(allDeadlines);
    const resolutionOverlap = this.pairwiseOverlap(allResolutions);

    const overlapScore =
      assetOverlap * WEIGHTS.asset +
      themeOverlap * WEIGHTS.theme +
      catalystOverlap * WEIGHTS.catalyst +
      entityOverlap * WEIGHTS.entity +
      deadlineOverlap * WEIGHTS.deadline +
      resolutionOverlap * WEIGHTS.resolution;

    // Find dominant shared factors
    const sharedFactors: string[] = [];
    const sharedThemes = this.findShared(allThemes);
    const sharedAssets = this.findShared(allAssets);
    const sharedCatalysts = this.findShared(allCatalysts);

    for (const t of sharedThemes) sharedFactors.push(`theme:${t}`);
    for (const a of sharedAssets) sharedFactors.push(`asset:${a}`);
    for (const c of sharedCatalysts) sharedFactors.push(`catalyst:${c}`);

    return {
      overlapScore: Math.round(overlapScore * 1000) / 1000,
      dominantSharedFactors: sharedFactors.slice(0, 6),
      assetOverlap: Math.round(assetOverlap * 100) / 100,
      themeOverlap: Math.round(themeOverlap * 100) / 100,
      catalystOverlap: Math.round(catalystOverlap * 100) / 100,
      entityOverlap: Math.round(entityOverlap * 100) / 100,
    };
  }

  /**
   * Average pairwise Jaccard overlap across all sets.
   */
  private pairwiseOverlap(sets: Set<string>[]): number {
    if (sets.length < 2) return 0;

    let totalOverlap = 0;
    let pairs = 0;

    for (let i = 0; i < sets.length; i++) {
      for (let j = i + 1; j < sets.length; j++) {
        totalOverlap += this.jaccard(sets[i], sets[j]);
        pairs++;
      }
    }

    return pairs > 0 ? totalOverlap / pairs : 0;
  }

  private jaccard(a: Set<string>, b: Set<string>): number {
    if (a.size === 0 && b.size === 0) return 0;
    const intersection = new Set([...a].filter(x => b.has(x)));
    const union = new Set([...a, ...b]);
    return union.size > 0 ? intersection.size / union.size : 0;
  }

  private findShared(sets: Set<string>[]): string[] {
    if (sets.length < 2) return [];
    const counts = new Map<string, number>();
    for (const s of sets) {
      for (const item of s) {
        counts.set(item, (counts.get(item) || 0) + 1);
      }
    }
    const threshold = Math.ceil(sets.length * 0.5); // Present in 50%+ of alerts
    return [...counts.entries()]
      .filter(([, c]) => c >= threshold)
      .sort((a, b) => b[1] - a[1])
      .map(([k]) => k);
  }
}

export const factorOverlapService = new FactorOverlapService();
