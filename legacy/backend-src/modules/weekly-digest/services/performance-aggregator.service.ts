/**
 * Performance Aggregator
 *
 * Core metrics: accuracy, edge-weighted accuracy, conviction-weighted accuracy.
 * Splits by time segment (early/mid/late week) and market regime (bull/bear/transition).
 */

import type { WeeklyPerformance, SegmentPerf } from '../types/digest.types.js';

interface ReviewData {
  asset: string;
  correctness: { correctness: string; directionCorrect: boolean; edgeRealized: boolean };
  timing: { timingGrade: string };
  grade?: string;
  traces: TraceData[];
  createdAt?: string;
}

interface TraceData {
  edge: number;
  confidence: number;
  conviction: string;
  action: string;
  dateBucket?: string;
  marketProb?: number;
}

class PerformanceAggregatorService {
  aggregate(reviews: ReviewData[], periodFrom: string, periodTo: string): WeeklyPerformance {
    const total = reviews.length;
    let correct = 0, wrong = 0, mixed = 0;
    let edgeSum = 0, confSum = 0;
    let edgeWeightedCorrect = 0, edgeWeightedTotal = 0;
    let convWeightedCorrect = 0, convWeightedTotal = 0;
    const grades: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, F: 0 };

    const earlyWeek: { correct: number; total: number; edgeSum: number } = { correct: 0, total: 0, edgeSum: 0 };
    const midWeek = { correct: 0, total: 0, edgeSum: 0 };
    const lateWeek = { correct: 0, total: 0, edgeSum: 0 };
    const bull = { correct: 0, total: 0, edgeSum: 0 };
    const bear = { correct: 0, total: 0, edgeSum: 0 };
    const transition = { correct: 0, total: 0, edgeSum: 0 };

    for (const r of reviews) {
      const isCorrect = r.correctness?.correctness === 'CORRECT';
      const isWrong = r.correctness?.correctness === 'WRONG';
      if (isCorrect) correct++;
      else if (isWrong) wrong++;
      else mixed++;

      const bestTrace = r.traces?.[0];
      const edge = Math.abs(bestTrace?.edge || 0);
      const conf = bestTrace?.confidence || 0;
      edgeSum += edge;
      confSum += conf;

      // Edge-weighted accuracy
      edgeWeightedTotal += edge;
      if (isCorrect) edgeWeightedCorrect += edge;

      // Conviction-weighted
      const convWeight = this.convictionWeight(bestTrace?.conviction);
      convWeightedTotal += convWeight;
      if (isCorrect) convWeightedCorrect += convWeight;

      // Grade
      const g = r.grade || 'C';
      if (grades[g] != null) grades[g]++;

      // Time segment
      const dayOfWeek = r.createdAt ? new Date(r.createdAt).getDay() : 3;
      const segment = dayOfWeek <= 2 ? earlyWeek : dayOfWeek <= 4 ? midWeek : lateWeek;
      segment.total++;
      segment.edgeSum += edge;
      if (isCorrect) segment.correct++;

      // Market regime (infer from action + edge direction)
      const action = bestTrace?.action || '';
      const regime = ['YES_NOW', 'YES_SMALL'].includes(action) ? bull :
                     ['NO_NOW', 'NO_SMALL'].includes(action) ? bear : transition;
      regime.total++;
      regime.edgeSum += edge;
      if (isCorrect) regime.correct++;
    }

    const toSegment = (s: typeof earlyWeek): SegmentPerf => ({
      count: s.total,
      accuracy: s.total > 0 ? Math.round((s.correct / s.total) * 100) : 0,
      avgEdge: s.total > 0 ? Math.round((s.edgeSum / s.total) * 10000) / 10000 : 0,
    });

    return {
      period: { from: periodFrom, to: periodTo },
      totalMarkets: total,
      correct, wrong, mixed,
      accuracy: total > 0 ? Math.round((correct / total) * 100) : 0,
      edgeWeightedAccuracy: edgeWeightedTotal > 0 ? Math.round((edgeWeightedCorrect / edgeWeightedTotal) * 100) : 0,
      convictionWeightedAccuracy: convWeightedTotal > 0 ? Math.round((convWeightedCorrect / convWeightedTotal) * 100) : 0,
      avgEdge: total > 0 ? Math.round((edgeSum / total) * 10000) / 10000 : 0,
      avgConfidence: total > 0 ? Math.round((confSum / total) * 100) / 100 : 0,
      avgGrade: this.avgGrade(grades, total),
      gradeDistribution: grades,
      bySegment: {
        earlyWeek: toSegment(earlyWeek),
        midWeek: toSegment(midWeek),
        lateWeek: toSegment(lateWeek),
      },
      byRegime: {
        bull: toSegment(bull),
        bear: toSegment(bear),
        transition: toSegment(transition),
      },
    };
  }

  private convictionWeight(conv?: string): number {
    const w: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };
    return w[conv || ''] || 1;
  }

  private avgGrade(grades: Record<string, number>, total: number): string {
    if (total === 0) return 'N/A';
    const pts: Record<string, number> = { A: 4, B: 3, C: 2, D: 1, F: 0 };
    let sum = 0;
    for (const [g, cnt] of Object.entries(grades)) sum += (pts[g] || 0) * cnt;
    const avg = sum / total;
    if (avg >= 3.5) return 'A';
    if (avg >= 2.5) return 'B';
    if (avg >= 1.5) return 'C';
    if (avg >= 0.5) return 'D';
    return 'F';
  }
}

export const performanceAggregatorService = new PerformanceAggregatorService();
