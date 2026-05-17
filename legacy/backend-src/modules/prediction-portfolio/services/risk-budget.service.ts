/**
 * Risk Budget Engine — Stage 7
 *
 * Enforces portfolio-level risk limits:
 *   1. Total exposure: > 2.0 penalty, > 3.0 strong penalty
 *   2. Same entity:    > 1.0 penalty, > 1.5 BLOCK
 *   3. Same theme:     > 1.2 penalty, > 1.8 BLOCK
 */
import type { CandidateCase, ActivePosition, RiskBudgetResult } from '../types/portfolio.types.js';

// ══════════════════════════════════════
// Exposure Aggregation
// ══════════════════════════════════════

function aggregateExposure(positions: ActivePosition[], candidate: CandidateCase) {
  let totalExposure = candidate.baseSizeFraction;
  const entityExposures: Record<string, number> = {};
  const themeExposures: Record<string, number> = {};

  // Accumulate from active positions
  for (const pos of positions) {
    totalExposure += pos.sizeFraction;

    for (const ent of pos.factorProfile.entityFactors) {
      entityExposures[ent] = (entityExposures[ent] || 0) + pos.sizeFraction;
    }
    for (const theme of pos.factorProfile.themeFactors) {
      themeExposures[theme] = (themeExposures[theme] || 0) + pos.sizeFraction;
    }
  }

  // Add candidate's contribution
  for (const ent of candidate.factorProfile.entityFactors) {
    entityExposures[ent] = (entityExposures[ent] || 0) + candidate.baseSizeFraction;
  }
  for (const theme of candidate.factorProfile.themeFactors) {
    themeExposures[theme] = (themeExposures[theme] || 0) + candidate.baseSizeFraction;
  }

  return { totalExposure, entityExposures, themeExposures };
}

// ══════════════════════════════════════
// Main: Evaluate Risk Budget
// ══════════════════════════════════════

export function evaluateRiskBudget(
  candidate: CandidateCase,
  positions: ActivePosition[],
): RiskBudgetResult {
  const { totalExposure, entityExposures, themeExposures } = aggregateExposure(positions, candidate);
  const reasons: string[] = [];
  let penalty = 0;
  let blocked = false;

  // ── 1. Total Exposure ──
  if (totalExposure > 3.0) {
    penalty = Math.max(penalty, 0.5);
    reasons.push(`Total portfolio exposure ${totalExposure.toFixed(2)} exceeds hard limit (3.0)`);
  } else if (totalExposure > 2.0) {
    const p = 0.1 + (totalExposure - 2.0) * (0.4 / 1.0);
    penalty = Math.max(penalty, Math.round(p * 100) / 100);
    reasons.push(`Total portfolio exposure ${totalExposure.toFixed(2)} above soft limit (2.0)`);
  }

  // ── 2. Entity Exposure ──
  for (const [entity, exposure] of Object.entries(entityExposures)) {
    if (entity === 'ENTITY_UNKNOWN') continue;
    if (exposure > 1.5) {
      blocked = true;
      reasons.push(`Entity ${entity.replace('ENTITY_', '')} exposure ${exposure.toFixed(2)} exceeds block limit (1.5)`);
    } else if (exposure > 1.0) {
      const p = 0.15 + (exposure - 1.0) * (0.5 / 0.5);
      penalty = Math.max(penalty, Math.round(p * 100) / 100);
      reasons.push(`Entity ${entity.replace('ENTITY_', '')} concentrated at ${exposure.toFixed(2)}`);
    }
  }

  // ── 3. Theme Exposure ──
  for (const [theme, exposure] of Object.entries(themeExposures)) {
    if (theme === 'GENERIC') continue;
    if (exposure > 1.8) {
      blocked = true;
      reasons.push(`Theme ${theme} exposure ${exposure.toFixed(2)} exceeds block limit (1.8)`);
    } else if (exposure > 1.2) {
      const p = 0.1 + (exposure - 1.2) * (0.4 / 0.6);
      penalty = Math.max(penalty, Math.round(p * 100) / 100);
      reasons.push(`Theme ${theme} crowded at ${exposure.toFixed(2)}`);
    }
  }

  return {
    penalty: Math.min(penalty, 1.0),
    blocked,
    reasons,
    totalExposure: Math.round(totalExposure * 100) / 100,
    entityExposures,
    themeExposures,
  };
}
