/**
 * Entry Quality Engine
 *
 * Main entry assessment: is the entry window open?
 * Combines edge, repricing, spread, depth, chase/miss risk.
 */

import type { EntryQualityAssessment, SpreadRegime, DepthQuality } from '../types/execution.types.js';

class EntryQualityService {
  assess(
    edge: number,
    confidence: number,
    repricing: string,
    spreadRegime: SpreadRegime,
    depthQuality: DepthQuality,
    slippageRisk: number,
    socialSaturation: number,
    marketStage: string,
  ): EntryQualityAssessment & { chaseRisk: number; missRisk: number } {
    const reasons: string[] = [];
    let score = 0;

    // 1. Edge alive (30%)
    const absEdge = Math.abs(edge);
    if (absEdge >= 0.12) {
      score += 0.30;
      reasons.push(`Strong edge ${(absEdge * 100).toFixed(1)}%`);
    } else if (absEdge >= 0.06) {
      score += 0.20;
    } else if (absEdge >= 0.03) {
      score += 0.10;
      reasons.push(`Small edge ${(absEdge * 100).toFixed(1)}% — tight`);
    } else {
      reasons.push(`Minimal edge ${(absEdge * 100).toFixed(1)}% — barely tradeable`);
    }

    // 2. Repricing phase (20%)
    const repricingScores: Record<string, number> = {
      fresh_mispricing: 0.20, pre_event: 0.18,
      active_repricing: 0.12, early_signal: 0.15,
      stalled: 0.08, late_repricing: 0.05,
      overheated: 0.02, crowded: 0.01,
    };
    score += repricingScores[repricing] ?? 0.10;
    if (repricing === 'overheated' || repricing === 'crowded') {
      reasons.push(`Repricing ${repricing} — entry window closing`);
    }

    // 3. Spread regime (15%)
    const spreadScores: Record<SpreadRegime, number> = {
      NARROW: 0.15, NORMAL: 0.10, WIDE: 0.04, BROKEN: 0,
    };
    score += spreadScores[spreadRegime];

    // 4. Depth quality (10%)
    const depthScores: Record<DepthQuality, number> = {
      DEEP: 0.10, OK: 0.07, THIN: 0.03, FRAGILE: 0,
    };
    score += depthScores[depthQuality];

    // 5. Slippage penalty (10%)
    score += (1 - slippageRisk) * 0.10;

    // 6. Confidence (15%)
    score += confidence * 0.15;

    score = Math.min(1, Math.round(score * 100) / 100);

    // Chase risk: high when late repricing + high saturation + moving fast
    let chaseRisk = 0;
    if (['late_repricing', 'overheated', 'crowded'].includes(repricing)) chaseRisk += 0.35;
    if (socialSaturation > 0.6) chaseRisk += 0.25;
    if (spreadRegime === 'WIDE' || spreadRegime === 'BROKEN') chaseRisk += 0.20;
    if (marketStage === 'crowded' || marketStage === 'overheated') chaseRisk += 0.20;
    chaseRisk = Math.min(1, Math.round(chaseRisk * 100) / 100);

    // Miss risk: high when edge is strong + fresh + narrow spread
    let missRisk = 0;
    if (absEdge >= 0.10) missRisk += 0.30;
    if (repricing === 'fresh_mispricing' || repricing === 'early_signal') missRisk += 0.30;
    if (spreadRegime === 'NARROW') missRisk += 0.15;
    if (confidence > 0.6) missRisk += 0.15;
    if (socialSaturation < 0.3) missRisk += 0.10; // early = will move
    missRisk = Math.min(1, Math.round(missRisk * 100) / 100);

    if (chaseRisk > 0.5) reasons.push('High chase risk — market already moving');
    if (missRisk > 0.5) reasons.push('High miss risk — edge may disappear quickly');

    // Entry window
    const entryWindow = score >= 0.70 ? 'OPEN' as const
      : score >= 0.50 ? 'OK' as const
      : score >= 0.30 ? 'WEAK' as const
      : 'CLOSED' as const;

    return { entryQualityScore: score, entryWindow, reasons, chaseRisk, missRisk };
  }
}

export const entryQualityService = new EntryQualityService();
