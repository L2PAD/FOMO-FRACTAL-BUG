/**
 * Correlation Engine — Stage 7
 *
 * Converts cluster overlap scores into penalties and block decisions.
 *
 * Overlap thresholds:
 *   < 0.45       → OK (no penalty)
 *   0.45 – 0.65  → light penalty
 *   0.65 – 0.85  → strong penalty
 *   > 0.85       → BLOCK
 */
import type { ClusterOverlap, CorrelationResult } from '../types/portfolio.types.js';

// ══════════════════════════════════════
// Penalty Mapping
// ══════════════════════════════════════

function overlapToPenalty(overlap: number): { penalty: number; blocked: boolean; reason?: string } {
  if (overlap > 0.85) {
    return {
      penalty: 1.0,
      blocked: true,
      reason: `Cluster overlap ${(overlap * 100).toFixed(0)}% — too similar to existing position, BLOCKED`,
    };
  }
  if (overlap > 0.65) {
    const penalty = 0.3 + (overlap - 0.65) * (0.7 / 0.2); // 0.3 → 1.0 over 0.65→0.85
    return {
      penalty: Math.round(Math.min(penalty, 0.7) * 100) / 100,
      blocked: false,
      reason: `Strong cluster overlap ${(overlap * 100).toFixed(0)}% — size significantly reduced`,
    };
  }
  if (overlap > 0.45) {
    const penalty = 0.05 + (overlap - 0.45) * (0.25 / 0.2); // 0.05 → 0.3 over 0.45→0.65
    return {
      penalty: Math.round(Math.min(penalty, 0.3) * 100) / 100,
      blocked: false,
      reason: `Moderate cluster overlap ${(overlap * 100).toFixed(0)}% — size lightly reduced`,
    };
  }
  return { penalty: 0, blocked: false };
}

// ══════════════════════════════════════
// Main: Compute Correlation
// ══════════════════════════════════════

/**
 * Evaluate correlation penalty based on cluster overlaps.
 * Uses the maximum overlap across all active positions.
 */
export function computeCorrelation(overlaps: ClusterOverlap[]): CorrelationResult {
  if (!overlaps.length) {
    return { penalty: 0, blocked: false, maxOverlap: 0, overlaps };
  }

  const maxOverlap = Math.max(...overlaps.map(o => o.directionAdjustedOverlap));
  const { penalty, blocked, reason } = overlapToPenalty(maxOverlap);

  return {
    penalty,
    blocked,
    reason,
    maxOverlap: Math.round(maxOverlap * 10000) / 10000,
    overlaps,
  };
}
