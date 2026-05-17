/**
 * Cluster Engine — Stage 7
 *
 * Computes weighted overlap between a candidate market and each active position.
 * Direction-aware: same direction amplifies overlap, opposite reduces it.
 *
 * Overlap formula:
 *   raw = asset*0.25 + theme*0.20 + catalyst*0.15 + deadline*0.10 + resolution*0.10 + entity*0.20
 *   direction-adjusted: same direction → *1.2, opposite → *0.6
 */
import type { FactorProfile, CandidateCase, ActivePosition, ClusterOverlap } from '../types/portfolio.types.js';

// ══════════════════════════════════════
// Axis Weights (sum = 1.0)
// ══════════════════════════════════════

const WEIGHTS = {
  asset:      0.25,
  theme:      0.20,
  catalyst:   0.15,
  deadline:   0.10,
  resolution: 0.10,
  entity:     0.20,
} as const;

// ══════════════════════════════════════
// Set Intersection Score
// ══════════════════════════════════════

function intersectionScore(a: string[], b: string[]): number {
  if (!a.length || !b.length) return 0;
  const setB = new Set(b);
  const intersection = a.filter(x => setB.has(x)).length;
  const union = new Set([...a, ...b]).size;
  return union > 0 ? intersection / union : 0;
}

// ══════════════════════════════════════
// Compute Overlap Between Two Profiles
// ══════════════════════════════════════

function computeProfileOverlap(
  candidate: FactorProfile,
  position: FactorProfile,
): { raw: number; breakdown: ClusterOverlap['breakdown'] } {
  const breakdown = {
    asset:      intersectionScore(candidate.assetFactors, position.assetFactors),
    theme:      intersectionScore(candidate.themeFactors, position.themeFactors),
    catalyst:   intersectionScore(candidate.catalystFactors, position.catalystFactors),
    deadline:   intersectionScore(candidate.deadlineFactors, position.deadlineFactors),
    resolution: intersectionScore(candidate.resolutionFactors, position.resolutionFactors),
    entity:     intersectionScore(candidate.entityFactors, position.entityFactors),
  };

  const raw =
    breakdown.asset      * WEIGHTS.asset +
    breakdown.theme      * WEIGHTS.theme +
    breakdown.catalyst   * WEIGHTS.catalyst +
    breakdown.deadline   * WEIGHTS.deadline +
    breakdown.resolution * WEIGHTS.resolution +
    breakdown.entity     * WEIGHTS.entity;

  return { raw: Math.round(raw * 10000) / 10000, breakdown };
}

// ══════════════════════════════════════
// Direction-Aware Adjustment
// ══════════════════════════════════════

function adjustForDirection(
  rawOverlap: number,
  candidateDir: string,
  positionDir: string,
): number {
  if (candidateDir === 'neutral' || positionDir === 'neutral') return rawOverlap;
  if (candidateDir === positionDir) return Math.min(1, rawOverlap * 1.2);
  return rawOverlap * 0.6;
}

// ══════════════════════════════════════
// Main: Compute Cluster Overlaps
// ══════════════════════════════════════

/**
 * Compute overlap of a candidate with every active position.
 */
export function computeClusterOverlaps(
  candidate: CandidateCase,
  positions: ActivePosition[],
): ClusterOverlap[] {
  return positions.map(pos => {
    const { raw, breakdown } = computeProfileOverlap(
      candidate.factorProfile,
      pos.factorProfile,
    );

    const dirAdjusted = adjustForDirection(raw, candidate.direction, pos.direction);

    return {
      positionMarketId: pos.marketId,
      rawOverlap: raw,
      directionAdjustedOverlap: Math.round(dirAdjusted * 10000) / 10000,
      breakdown,
    };
  });
}

/**
 * Get the maximum direction-adjusted overlap from a set of cluster overlaps.
 */
export function getMaxOverlap(overlaps: ClusterOverlap[]): number {
  if (!overlaps.length) return 0;
  return Math.max(...overlaps.map(o => o.directionAdjustedOverlap));
}
