/**
 * Decision Quality
 *
 * Distinguishes: correct result ≠ good decision.
 * Grades: high-quality decisions, lucky wins, bad-but-correct, skillful losses.
 */

import type { DecisionQuality } from '../types/digest.types.js';

interface ReviewData {
  correctness: { correctness: string; directionCorrect: boolean; edgeRealized: boolean; confidenceJustified: boolean };
  timing: { timingGrade?: string };
  calibration: { calibrationQuality?: string; overconfidenceScore?: number };
  grade?: string;
  traces: { edge: number; confidence: number; conviction: string }[];
}

class DecisionQualityService {
  analyze(reviews: ReviewData[]): DecisionQuality {
    let highQuality = 0, luckyWins = 0, badButCorrect = 0, skillfulLosses = 0;

    for (const r of reviews) {
      const isCorrect = r.correctness?.correctness === 'CORRECT';
      const goodReasoning = this.hasGoodReasoning(r);

      if (isCorrect && goodReasoning) {
        highQuality++;
      } else if (isCorrect && !goodReasoning) {
        // Correct outcome but weak reasoning = lucky
        luckyWins++;
        badButCorrect++;
      } else if (!isCorrect && goodReasoning) {
        // Wrong outcome but solid reasoning = skillful loss
        skillfulLosses++;
      }
      // Wrong outcome + bad reasoning = just bad (not counted separately)
    }

    const total = reviews.length || 1;
    const qualityScore = (highQuality + skillfulLosses * 0.5) / total;

    return {
      highQualityDecisions: highQuality,
      luckyWins,
      badButCorrect,
      skillfulLosses,
      totalDecisions: reviews.length,
      decisionQualityScore: Math.round(qualityScore * 100) / 100,
    };
  }

  private hasGoodReasoning(r: ReviewData): boolean {
    let score = 0;

    // Confidence was justified
    if (r.correctness?.confidenceJustified) score += 1;

    // Edge was meaningful
    const bestTrace = r.traces?.[0];
    if (bestTrace && Math.abs(bestTrace.edge) >= 0.06) score += 1;

    // Timing was decent
    const tg = (r.timing?.timingGrade || '').toLowerCase();
    if (['excellent', 'early', 'good'].includes(tg)) score += 1;

    // Calibration was reasonable
    if (r.calibration?.calibrationQuality !== 'POOR') score += 1;

    // Grade was B or above
    if (['A', 'B'].includes(r.grade || '')) score += 1;

    return score >= 3; // At least 3/5 indicators
  }
}

export const decisionQualityService = new DecisionQualityService();
