/**
 * Learning Extractor
 *
 * Produces human-readable lessons, mistakes, and improvements.
 * The most important output layer — this is what the operator reads.
 */

import type { WeeklyPerformance, TimingAnalysis, EdgeAttribution, DecisionQuality, CalibrationAnalysis, MarketPattern, MissedOpportunity, WeeklyChange, ExecutionQuality } from '../types/digest.types.js';

interface ExtractorInput {
  performance: WeeklyPerformance;
  timing: TimingAnalysis;
  edgeAttribution: EdgeAttribution;
  decisionQuality: DecisionQuality;
  calibration: CalibrationAnalysis;
  bestPatterns: MarketPattern[];
  worstPatterns: MarketPattern[];
  missedOpportunities: MissedOpportunity[];
  prevPerformance?: WeeklyPerformance | null;
  prevTiming?: TimingAnalysis | null;
  executionQuality?: ExecutionQuality;
}

class LearningExtractorService {
  extract(input: ExtractorInput): { lessons: string[]; mistakes: string[]; improvements: string[]; changes: WeeklyChange[] } {
    const lessons: string[] = [];
    const mistakes: string[] = [];
    const improvements: string[] = [];
    const changes: WeeklyChange[] = [];

    const { performance: perf, timing, edgeAttribution: ea, decisionQuality: dq, calibration: cal } = input;

    // --- Lessons ---
    if (perf.accuracy >= 70) lessons.push(`Strong overall accuracy (${perf.accuracy}%) — system reasoning is well-calibrated`);
    if (perf.edgeWeightedAccuracy > perf.accuracy + 5) lessons.push(`Edge-weighted accuracy (${perf.edgeWeightedAccuracy}%) > raw accuracy — bigger bets are better quality`);
    if (timing.lateEntryPct > 30) lessons.push(`Late entries account for ${timing.lateEntryPct}% — timing needs improvement`);
    if (timing.avgTimingQuality > 0.7) lessons.push(`Timing quality is strong (${(timing.avgTimingQuality * 100).toFixed(0)}%) — early detection is working`);
    if (input.bestPatterns.length > 0) lessons.push(`Strongest area: ${input.bestPatterns[0].pattern} (${input.bestPatterns[0].accuracy}% accuracy)`);
    if (ea.project > 0.1) lessons.push('Project intelligence is contributing positive alpha');
    if (ea.social < -0.05) lessons.push('Social layer is adding noise — consider reducing weight');
    if (dq.decisionQualityScore > 0.6) lessons.push(`Decision quality is high (${(dq.decisionQualityScore * 100).toFixed(0)}%) — reasoning matches outcomes`);

    // --- Mistakes ---
    if (dq.luckyWins > 0) mistakes.push(`${dq.luckyWins} lucky win${dq.luckyWins > 1 ? 's' : ''} detected — correct outcome but weak reasoning`);
    if (cal.overconfident > cal.wellCalibrated) mistakes.push('System is overconfident — calibration needs tightening');
    if (input.worstPatterns.length > 0 && input.worstPatterns[0].accuracy < 40) {
      mistakes.push(`Weak in ${input.worstPatterns[0].pattern} markets (${input.worstPatterns[0].accuracy}%) — consider avoiding or reducing size`);
    }
    if (timing.lateEntryPct > 40) mistakes.push(`${timing.lateEntryPct}% late entries — systematic timing issue`);
    if (input.missedOpportunities.length > 0) {
      const top = input.missedOpportunities[0];
      mistakes.push(`Missed ${top.asset} (${(top.missedEdge * 100).toFixed(0)}% edge) — ${top.reason}`);
    }
    if (perf.edgeWeightedAccuracy < perf.accuracy - 10) mistakes.push('Bigger bets have worse outcomes — sizing/conviction mismatch');

    // --- Improvements ---
    if (ea.intelligence > 0.1) improvements.push('Case intelligence producing consistent alpha — continue current approach');
    if (perf.byRegime.bull.accuracy > perf.byRegime.bear.accuracy + 20) improvements.push('Much stronger in bull setups — consider bull-biased allocation');
    if (perf.bySegment.earlyWeek.accuracy > perf.bySegment.lateWeek.accuracy + 15) improvements.push('Early-week signals are stronger — act faster on Monday-Tuesday signals');
    if (cal.driftDirection === 'DOWN') improvements.push('Confidence decreasing — system becoming more conservative');
    if (cal.driftDirection === 'UP') improvements.push('Confidence increasing — watch for overconfidence creep');

    // --- Execution Quality insights ---
    const eq = input.executionQuality;
    if (eq && eq.totalEvaluated > 0) {
      if (eq.avgScore >= 0.7) lessons.push(`Execution quality is strong (${(eq.avgScore * 100).toFixed(0)}%, grade ${eq.avgGrade})`);
      if (eq.avgScore < 0.5) mistakes.push(`Execution quality is poor (${(eq.avgScore * 100).toFixed(0)}%, grade ${eq.avgGrade}) — need to improve order execution`);
      for (const l of eq.executionLessons.slice(0, 2)) {
        improvements.push(l);
      }
    }

    // --- What Changed (vs previous week) ---
    if (input.prevPerformance) {
      const prev = input.prevPerformance;
      changes.push(this.buildChange('Accuracy', prev.accuracy, perf.accuracy, '%'));
      changes.push(this.buildChange('Avg Edge', prev.avgEdge * 100, perf.avgEdge * 100, '%'));
      changes.push(this.buildChange('Avg Confidence', prev.avgConfidence * 100, perf.avgConfidence * 100, '%'));
    }
    if (input.prevTiming) {
      changes.push(this.buildChange('Late Entry %', input.prevTiming.lateEntryPct, timing.lateEntryPct, '%'));
      changes.push(this.buildChange('Timing Quality', input.prevTiming.avgTimingQuality * 100, timing.avgTimingQuality * 100, '%'));
    }

    return {
      lessons: lessons.slice(0, 6),
      mistakes: mistakes.slice(0, 5),
      improvements: improvements.slice(0, 4),
      changes: changes.filter(c => c.direction !== 'STABLE'),
    };
  }

  private buildChange(metric: string, prev: number, current: number, suffix: string): WeeklyChange {
    const delta = Math.round((current - prev) * 10) / 10;
    const deltaPercent = prev !== 0 ? Math.round(((current - prev) / Math.abs(prev)) * 1000) / 10 : 0;
    return {
      metric: `${metric}`,
      prev: Math.round(prev * 10) / 10,
      current: Math.round(current * 10) / 10,
      delta,
      deltaPercent,
      direction: delta > 1 ? 'UP' : delta < -1 ? 'DOWN' : 'STABLE',
      impact: Math.abs(delta) > 10 ? 'HIGH' : Math.abs(delta) > 5 ? 'MEDIUM' : 'LOW',
    };
  }
}

export const learningExtractorService = new LearningExtractorService();
