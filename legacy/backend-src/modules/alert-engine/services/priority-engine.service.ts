/**
 * Priority Engine
 *
 * Computes alert priority score:
 *   edge × 0.35 + confidence × 0.25 + alignment × 0.15 + timing × 0.15 + executionQuality × 0.10
 */

import type { AlertTier } from '../types/alert.types.js';

interface PriorityInput {
  edge: number;
  confidence: number;
  alignment: number;
  entryQualityScore: number;
  repricing: string;
  tier: AlertTier;
}

interface PriorityResult {
  priorityScore: number;
  tier: AlertTier;
}

class PriorityEngineService {
  compute(input: PriorityInput): PriorityResult {
    const absEdge = Math.min(1, Math.abs(input.edge) / 0.15); // normalize to 0-1
    const timingScore = this.getTimingScore(input.repricing);

    const score =
      absEdge * 0.35 +
      input.confidence * 0.25 +
      input.alignment * 0.15 +
      timingScore * 0.15 +
      input.entryQualityScore * 0.10;

    const priorityScore = Math.min(1, Math.round(score * 100) / 100);

    // Tier can be upgraded by priority score
    let tier = input.tier;
    if (priorityScore >= 0.75 && tier === 'MEDIUM') tier = 'HIGH';
    if (priorityScore < 0.40 && tier === 'MEDIUM') tier = 'LOW';

    return { priorityScore, tier };
  }

  private getTimingScore(repricing: string): number {
    const scores: Record<string, number> = {
      fresh_mispricing: 1.0,
      early_repricing: 0.85,
      pre_event: 0.80,
      early_signal: 0.75,
      active_repricing: 0.55,
      stalled: 0.40,
      late_repricing: 0.20,
      overheated: 0.10,
      crowded: 0.05,
    };
    return scores[repricing] ?? 0.30;
  }
}

export const priorityEngineService = new PriorityEngineService();
