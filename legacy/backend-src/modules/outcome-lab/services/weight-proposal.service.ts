/**
 * Weight Proposal Service
 *
 * Generates proposals for weight adjustments based on outcome reviews.
 * NOT auto-tune — proposals only. Human/system decides whether to apply.
 */

import type {
  WeightProposal, OutcomeReview,
  SourceAttribution, CalibrationReview, TimingReview,
} from '../types/outcome-lab.types.js';

class WeightProposalService {
  propose(
    reviews: OutcomeReview[],
  ): WeightProposal {
    const sourceAdjustments: WeightProposal['sourceAdjustments'] = [];
    const timingAdjustments: WeightProposal['timingAdjustments'] = [];
    const calibrationAdjustments: WeightProposal['calibrationAdjustments'] = [];

    if (reviews.length < 2) {
      return { sourceAdjustments, timingAdjustments, calibrationAdjustments };
    }

    // ── Source Adjustments ──
    const sourceStats = new Map<string, { helpful: number; harmful: number; total: number; avgImpact: number }>();

    for (const r of reviews) {
      for (const sa of r.sourceAttributions) {
        if (!sourceStats.has(sa.source)) {
          sourceStats.set(sa.source, { helpful: 0, harmful: 0, total: 0, avgImpact: 0 });
        }
        const s = sourceStats.get(sa.source)!;
        s.total++;
        if (sa.helpful) s.helpful++;
        else s.harmful++;
        s.avgImpact = (s.avgImpact * (s.total - 1) + sa.impactScore) / s.total;
      }
    }

    for (const [source, stats] of sourceStats) {
      if (stats.total < 2) continue;
      const helpRate = stats.helpful / stats.total;

      if (helpRate >= 0.75) {
        sourceAdjustments.push({
          source,
          currentWeight: 1.0,
          proposedWeight: 1.15,
          reason: `${source} was helpful in ${(helpRate * 100).toFixed(0)}% of cases (${stats.total} samples) — increase trust`,
        });
      } else if (helpRate <= 0.30) {
        sourceAdjustments.push({
          source,
          currentWeight: 1.0,
          proposedWeight: 0.75,
          reason: `${source} was misleading in ${((1 - helpRate) * 100).toFixed(0)}% of cases — decrease trust`,
        });
      }
    }

    // ── Timing Adjustments ──
    const timingStats = {
      early: 0, good: 0, ok: 0, late: 0, bad: 0, total: reviews.length,
      missedCount: 0,
    };

    for (const r of reviews) {
      const tq = r.timing.timingQuality.toLowerCase();
      if (tq in timingStats) (timingStats as any)[tq]++;
      if (r.missedOpportunity.missed) timingStats.missedCount++;
    }

    if (timingStats.late + timingStats.bad > timingStats.total * 0.4) {
      timingAdjustments.push({
        parameter: 'entry_confidence_threshold',
        currentValue: 0.50,
        proposedValue: 0.40,
        reason: `${((timingStats.late + timingStats.bad) / timingStats.total * 100).toFixed(0)}% of entries were late/bad — lower confidence threshold to enter earlier`,
      });
    }

    if (timingStats.missedCount > timingStats.total * 0.3) {
      timingAdjustments.push({
        parameter: 'edge_threshold_for_action',
        currentValue: 0.05,
        proposedValue: 0.03,
        reason: `${((timingStats.missedCount / timingStats.total) * 100).toFixed(0)}% were missed opportunities — lower edge threshold`,
      });
    }

    // ── Calibration Adjustments ──
    const calStats = { overconfident: 0, underconfident: 0, well: 0, poor: 0 };

    for (const r of reviews) {
      const cq = r.calibration.calibrationQuality;
      if (cq === 'OVERCONFIDENT') calStats.overconfident++;
      else if (cq === 'UNDERCONFIDENT') calStats.underconfident++;
      else if (cq === 'WELL_CALIBRATED') calStats.well++;
      else calStats.poor++;
    }

    if (calStats.overconfident > reviews.length * 0.4) {
      calibrationAdjustments.push({
        parameter: 'confidence_dampening',
        adjustment: -0.10,
        reason: `System was overconfident in ${((calStats.overconfident / reviews.length) * 100).toFixed(0)}% of cases — reduce confidence output`,
      });
    }

    if (calStats.underconfident > reviews.length * 0.4) {
      calibrationAdjustments.push({
        parameter: 'confidence_boost',
        adjustment: 0.08,
        reason: `System was underconfident in ${((calStats.underconfident / reviews.length) * 100).toFixed(0)}% of cases — increase confidence output`,
      });
    }

    return { sourceAdjustments, timingAdjustments, calibrationAdjustments };
  }
}

export const weightProposalService = new WeightProposalService();
