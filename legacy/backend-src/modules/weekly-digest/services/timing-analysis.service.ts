/**
 * Timing Analysis
 *
 * Grades entry timing: early/good/ok/late/bad.
 * Computes % late entries, % missed windows, avg timing quality.
 */

import type { TimingAnalysis } from '../types/digest.types.js';

interface ReviewData {
  timing: { timingGrade?: string; entryWindow?: string; missedWindow?: boolean };
  correctness: { correctness: string };
}

class TimingAnalysisService {
  analyze(reviews: ReviewData[]): TimingAnalysis {
    let early = 0, good = 0, ok = 0, late = 0, bad = 0;
    let missedWindows = 0;

    for (const r of reviews) {
      const grade = (r.timing?.timingGrade || 'ok').toLowerCase();

      if (grade === 'excellent' || grade === 'early') early++;
      else if (grade === 'good') good++;
      else if (grade === 'ok' || grade === 'acceptable') ok++;
      else if (grade === 'late') late++;
      else bad++;

      if (r.timing?.missedWindow) missedWindows++;
    }

    const total = reviews.length || 1;
    const qualityScore = total > 0
      ? (early * 1.0 + good * 0.8 + ok * 0.5 + late * 0.2 + bad * 0) / total
      : 0;

    return {
      early,
      good,
      ok,
      late,
      bad,
      avgTimingQuality: Math.round(qualityScore * 100) / 100,
      missedWindowPct: Math.round((missedWindows / total) * 100),
      lateEntryPct: Math.round(((late + bad) / total) * 100),
    };
  }
}

export const timingAnalysisService = new TimingAnalysisService();
