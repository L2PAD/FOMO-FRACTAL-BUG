/**
 * Calibration Review Service
 *
 * Checks: Was the system overconfident or underconfident?
 * Good calibration = when we say 70%, it resolves YES ~70% of the time.
 */

import type { CalibrationReview, DecisionTrace, ResolvedMarket } from '../types/outcome-lab.types.js';

class CalibrationReviewService {
  review(trace: DecisionTrace, resolved: ResolvedMarket): CalibrationReview {
    const notes: string[] = [];
    const outcomeProb = resolved.outcome === 'YES' ? 1 : 0;

    const avgFairProb = trace.fairProb;
    const errorScore = Math.abs(avgFairProb - outcomeProb);

    // Overconfidence: predicted high prob for YES but resolved NO, or vice versa
    const overconfidenceScore = resolved.outcome === 'YES'
      ? Math.max(0, (1 - avgFairProb) - 0.1) // penalize if fairProb was too low for YES
      : Math.max(0, avgFairProb - 0.1);        // penalize if fairProb was too high for NO

    // Calibration quality
    let calibrationQuality: CalibrationReview['calibrationQuality'];

    if (errorScore < 0.15) {
      calibrationQuality = 'WELL_CALIBRATED';
      notes.push(`Fair probability ${(avgFairProb * 100).toFixed(0)}% was close to outcome — well calibrated`);
    } else if (errorScore < 0.30) {
      // Determine direction of miscalibration
      if (resolved.outcome === 'YES' && avgFairProb < 0.5) {
        calibrationQuality = 'UNDERCONFIDENT';
        notes.push(`System was too bearish (${(avgFairProb * 100).toFixed(0)}% fair) for YES outcome`);
      } else if (resolved.outcome === 'NO' && avgFairProb > 0.5) {
        calibrationQuality = 'OVERCONFIDENT';
        notes.push(`System was too bullish (${(avgFairProb * 100).toFixed(0)}% fair) for NO outcome`);
      } else {
        calibrationQuality = 'WELL_CALIBRATED';
        notes.push('Moderate calibration error but in the right direction');
      }
    } else {
      // Large error
      if (resolved.outcome === 'YES' && avgFairProb < 0.35) {
        calibrationQuality = 'UNDERCONFIDENT';
        notes.push(`MAJOR underconfidence: system gave ${(avgFairProb * 100).toFixed(0)}% but resolved YES`);
      } else if (resolved.outcome === 'NO' && avgFairProb > 0.65) {
        calibrationQuality = 'OVERCONFIDENT';
        notes.push(`MAJOR overconfidence: system gave ${(avgFairProb * 100).toFixed(0)}% but resolved NO`);
      } else {
        calibrationQuality = 'POOR';
        notes.push(`Large calibration error: ${(errorScore * 100).toFixed(0)}% off`);
      }
    }

    // Context
    if (trace.confidence > 0.7 && errorScore > 0.3) {
      notes.push('High confidence with large error — needs confidence adjustment');
    }
    if (trace.alignment < 0.4 && errorScore < 0.2) {
      notes.push('Low alignment but good calibration — individual modules cancelling out correctly');
    }

    return {
      calibrationQuality,
      avgFairProb: Math.round(avgFairProb * 1000) / 1000,
      actualOutcomeProb: outcomeProb,
      errorScore: Math.round(errorScore * 1000) / 1000,
      overconfidenceScore: Math.round(overconfidenceScore * 1000) / 1000,
      notes,
    };
  }
}

export const calibrationReviewService = new CalibrationReviewService();
