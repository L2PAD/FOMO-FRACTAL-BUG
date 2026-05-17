/**
 * Digest Comparison Service
 *
 * Compares current week vs previous week across all dimensions.
 * Produces: system state, weighted deltas, regime breakdown,
 * execution style changes, biggest drivers, confidence drift.
 *
 * Reads in 10-15 seconds — this is the operator's control panel.
 */

import type {
  WeeklyDigest, DigestComparison, WeeklyChange, RegimeComparison,
  ExecutionStyleDelta, SystemState,
} from '../types/digest.types.js';

const IMPACT_WEIGHTS: Record<string, number> = {
  accuracy: 0.25,
  executionScore: 0.25,
  timingQuality: 0.20,
  missedOpportunities: 0.15,
  sourceQuality: 0.10,
  confidenceDrift: 0.05,
};

const THRESHOLD = 3; // ±3% for IMPROVED/DEGRADED classification

class DigestComparisonService {
  compare(current: WeeklyDigest, previous: WeeklyDigest): DigestComparison {
    const metricDeltas = this.buildMetricDeltas(current, previous);
    const regimeComparison = this.buildRegimeComparison(current, previous);
    const executionDeltas = this.buildExecutionDeltas(current, previous);
    const overallChangeScore = this.computeOverallScore(metricDeltas);
    const systemState = this.determineSystemState(overallChangeScore, metricDeltas);
    const confidenceDrift = this.buildConfidenceDrift(current, previous);
    const drivers = this.extractDrivers(current, previous, metricDeltas, regimeComparison, executionDeltas);

    // Biggest improvement/degradation
    const sorted = [...metricDeltas].sort((a, b) => b.delta - a.delta);
    const improvements = sorted.filter(d => d.direction === 'UP');
    const degradations = sorted.filter(d => d.direction === 'DOWN');
    const biggestImprovement = improvements.length > 0
      ? `${improvements[0].metric}: +${improvements[0].delta.toFixed(1)}%`
      : 'No significant improvements';
    const biggestDegradation = degradations.length > 0
      ? `${degradations[degradations.length - 1].metric}: ${degradations[degradations.length - 1].delta.toFixed(1)}%`
      : 'No significant degradations';

    return {
      systemState,
      overallChangeScore: Math.round(overallChangeScore * 100) / 100,
      metricDeltas,
      regimeComparison,
      executionDeltas,
      biggestImprovement,
      biggestDegradation,
      drivers,
      confidenceDrift,
    };
  }

  private buildMetricDeltas(cur: WeeklyDigest, prev: WeeklyDigest): WeeklyChange[] {
    const deltas: WeeklyChange[] = [];

    // Accuracy
    deltas.push(this.delta('Accuracy', prev.performance.accuracy, cur.performance.accuracy, 'accuracy'));

    // Edge-weighted accuracy
    deltas.push(this.delta('Edge-Weighted', prev.performance.edgeWeightedAccuracy, cur.performance.edgeWeightedAccuracy, 'accuracy'));

    // Execution quality
    const prevExec = prev.executionQuality?.avgScore ?? 0;
    const curExec = cur.executionQuality?.avgScore ?? 0;
    if (prevExec > 0 || curExec > 0) {
      deltas.push(this.delta('Execution Quality', prevExec * 100, curExec * 100, 'executionScore'));
    }

    // Timing quality
    deltas.push(this.delta('Timing Quality', prev.timing.avgTimingQuality * 100, cur.timing.avgTimingQuality * 100, 'timingQuality'));

    // Late entry %
    deltas.push(this.delta('Late Entry %', prev.timing.lateEntryPct, cur.timing.lateEntryPct, 'timingQuality', true));

    // Decision quality
    deltas.push(this.delta('Decision Quality', prev.decisionQuality.decisionQualityScore * 100, cur.decisionQuality.decisionQualityScore * 100, 'accuracy'));

    // Missed opportunities
    const prevMissed = prev.missedOpportunities?.length ?? 0;
    const curMissed = cur.missedOpportunities?.length ?? 0;
    deltas.push(this.delta('Missed Opportunities', prevMissed, curMissed, 'missedOpportunities', true));

    // Avg confidence
    deltas.push(this.delta('Avg Confidence', prev.performance.avgConfidence * 100, cur.performance.avgConfidence * 100, 'confidenceDrift'));

    // Slippage leakage
    const prevLeak = (prev.executionQuality?.avgSlippageLeakage ?? 0) * 100;
    const curLeak = (cur.executionQuality?.avgSlippageLeakage ?? 0) * 100;
    if (prevLeak > 0 || curLeak > 0) {
      deltas.push(this.delta('Slippage Leakage', prevLeak, curLeak, 'executionScore', true));
    }

    return deltas;
  }

  private delta(metric: string, prev: number, current: number, weightKey: string, invertDirection = false): WeeklyChange {
    const rawDelta = Math.round((current - prev) * 10) / 10;
    const deltaPercent = prev !== 0 ? Math.round(((current - prev) / Math.abs(prev)) * 1000) / 10 : 0;

    let direction: 'UP' | 'DOWN' | 'STABLE';
    if (Math.abs(rawDelta) < THRESHOLD) {
      direction = 'STABLE';
    } else if (invertDirection) {
      direction = rawDelta > 0 ? 'DOWN' : 'UP'; // Higher = worse for inverted metrics
    } else {
      direction = rawDelta > 0 ? 'UP' : 'DOWN';
    }

    const weight = IMPACT_WEIGHTS[weightKey] || 0.1;
    const impact: 'HIGH' | 'MEDIUM' | 'LOW' =
      Math.abs(rawDelta) > 10 ? 'HIGH' :
      Math.abs(rawDelta) > 5 ? 'MEDIUM' : 'LOW';

    return {
      metric, prev: Math.round(prev * 10) / 10, current: Math.round(current * 10) / 10,
      delta: rawDelta, deltaPercent, direction, impact,
    };
  }

  private buildRegimeComparison(cur: WeeklyDigest, prev: WeeklyDigest): RegimeComparison[] {
    const regimes = ['bull', 'bear', 'transition'] as const;
    const result: RegimeComparison[] = [];

    for (const r of regimes) {
      const prevR = prev.performance.byRegime[r];
      const curR = cur.performance.byRegime[r];
      if (!prevR || !curR) continue;
      if (prevR.count === 0 && curR.count === 0) continue;

      const accDelta = curR.accuracy - prevR.accuracy;

      // Execution by regime (from reviews if available)
      const prevExec = 0; // Will be populated if we had regime-specific execution data
      const curExec = 0;

      result.push({
        regime: r.toUpperCase(),
        prevAccuracy: prevR.accuracy,
        currentAccuracy: curR.accuracy,
        delta: Math.round(accDelta * 10) / 10,
        direction: Math.abs(accDelta) < THRESHOLD ? 'STABLE' : accDelta > 0 ? 'UP' : 'DOWN',
        prevExecScore: prevExec,
        currentExecScore: curExec,
        execDelta: curExec - prevExec,
      });
    }

    return result;
  }

  private buildExecutionDeltas(cur: WeeklyDigest, prev: WeeklyDigest): ExecutionStyleDelta[] {
    const curEq = cur.executionQuality;
    const prevEq = prev.executionQuality;
    if (!curEq && !prevEq) return [];

    const styles: ExecutionStyleDelta[] = [];

    // Compare best/worst styles
    const curBest = curEq?.bestStyle;
    const prevBest = prevEq?.bestStyle;
    const curWorst = curEq?.worstStyle;
    const prevWorst = prevEq?.worstStyle;

    if (curBest) {
      const prevScore = prevBest?.style === curBest.style ? prevBest.avgScore : 0;
      const delta = Math.round((curBest.avgScore - prevScore) * 100) / 100;
      styles.push({
        style: curBest.style,
        prevScore: Math.round(prevScore * 100) / 100,
        currentScore: Math.round(curBest.avgScore * 100) / 100,
        delta,
        direction: Math.abs(delta) < 0.03 ? 'STABLE' : delta > 0 ? 'UP' : 'DOWN',
        note: `Best performing style (${(curBest.avgScore * 100).toFixed(0)}%)`,
      });
    }

    if (curWorst && curWorst.style !== curBest?.style) {
      const prevScore = prevWorst?.style === curWorst.style ? prevWorst.avgScore : 0;
      const delta = Math.round((curWorst.avgScore - prevScore) * 100) / 100;
      styles.push({
        style: curWorst.style,
        prevScore: Math.round(prevScore * 100) / 100,
        currentScore: Math.round(curWorst.avgScore * 100) / 100,
        delta,
        direction: Math.abs(delta) < 0.03 ? 'STABLE' : delta > 0 ? 'UP' : 'DOWN',
        note: `Worst performing style (${(curWorst.avgScore * 100).toFixed(0)}%)`,
      });
    }

    // Missed move comparison
    const prevMissed = (prevEq?.avgMissedMove ?? 0) * 100;
    const curMissed = (curEq?.avgMissedMove ?? 0) * 100;
    if (prevMissed > 0 || curMissed > 0) {
      const delta = Math.round((curMissed - prevMissed) * 10) / 10;
      styles.push({
        style: 'MISSED_MOVES',
        prevScore: Math.round(prevMissed * 10) / 10,
        currentScore: Math.round(curMissed * 10) / 10,
        delta,
        direction: Math.abs(delta) < 1 ? 'STABLE' : delta > 0 ? 'DOWN' : 'UP', // Higher missed = worse
        note: delta > 0 ? `Missed moves increased (+${delta.toFixed(1)}%)` : `Missed moves decreased (${delta.toFixed(1)}%)`,
      });
    }

    return styles;
  }

  private computeOverallScore(deltas: WeeklyChange[]): number {
    let weightedSum = 0;
    let totalWeight = 0;

    for (const d of deltas) {
      const weight = this.getWeight(d.metric);
      // Normalize delta: positive = improvement, negative = degradation
      const normalizedDelta = d.direction === 'UP' ? Math.abs(d.delta) :
                              d.direction === 'DOWN' ? -Math.abs(d.delta) : 0;
      weightedSum += normalizedDelta * weight;
      totalWeight += weight;
    }

    return totalWeight > 0 ? weightedSum / totalWeight : 0;
  }

  private getWeight(metric: string): number {
    const map: Record<string, number> = {
      'Accuracy': IMPACT_WEIGHTS.accuracy,
      'Edge-Weighted': IMPACT_WEIGHTS.accuracy * 0.8,
      'Execution Quality': IMPACT_WEIGHTS.executionScore,
      'Timing Quality': IMPACT_WEIGHTS.timingQuality,
      'Late Entry %': IMPACT_WEIGHTS.timingQuality * 0.7,
      'Decision Quality': IMPACT_WEIGHTS.accuracy * 0.9,
      'Missed Opportunities': IMPACT_WEIGHTS.missedOpportunities,
      'Avg Confidence': IMPACT_WEIGHTS.confidenceDrift,
      'Slippage Leakage': IMPACT_WEIGHTS.executionScore * 0.5,
    };
    return map[metric] || 0.1;
  }

  private determineSystemState(score: number, deltas: WeeklyChange[]): SystemState {
    // Check for instability: many metrics moving in different directions
    const upCount = deltas.filter(d => d.direction === 'UP').length;
    const downCount = deltas.filter(d => d.direction === 'DOWN').length;
    const highImpactDown = deltas.filter(d => d.direction === 'DOWN' && d.impact === 'HIGH').length;

    if (upCount >= 2 && downCount >= 2 && Math.abs(upCount - downCount) <= 1) {
      return 'UNSTABLE';
    }

    if (score > 3) return 'IMPROVING';
    if (score < -3) return 'DEGRADING';
    if (highImpactDown >= 2) return 'DEGRADING';
    return 'STABLE';
  }

  private buildConfidenceDrift(cur: WeeklyDigest, prev: WeeklyDigest): DigestComparison['confidenceDrift'] {
    const prevConf = prev.performance.avgConfidence;
    const curConf = cur.performance.avgConfidence;
    const delta = Math.round((curConf - prevConf) * 1000) / 10;

    let direction: 'UP' | 'DOWN' | 'STABLE';
    if (Math.abs(delta) < 2) direction = 'STABLE';
    else direction = delta > 0 ? 'UP' : 'DOWN';

    const interpretation =
      direction === 'UP' ? 'System becoming more aggressive' :
      direction === 'DOWN' ? 'System becoming more conservative' :
      'Confidence stable';

    return { direction, delta, interpretation };
  }

  private extractDrivers(
    cur: WeeklyDigest, prev: WeeklyDigest,
    deltas: WeeklyChange[], regimes: RegimeComparison[], execDeltas: ExecutionStyleDelta[],
  ): string[] {
    const drivers: string[] = [];

    // From metric deltas
    const highImpact = deltas.filter(d => d.impact === 'HIGH' || (d.impact === 'MEDIUM' && d.direction !== 'STABLE'));
    for (const d of highImpact.slice(0, 2)) {
      if (d.direction === 'UP') {
        drivers.push(`${d.metric} improved significantly (+${d.delta.toFixed(1)}%)`);
      } else if (d.direction === 'DOWN') {
        drivers.push(`${d.metric} degraded (${d.delta.toFixed(1)}%)`);
      }
    }

    // From regime comparison
    for (const r of regimes) {
      if (r.direction === 'UP' && r.delta > 10) {
        drivers.push(`Strong improvement in ${r.regime} regime (+${r.delta.toFixed(0)}%)`);
      } else if (r.direction === 'DOWN' && r.delta < -10) {
        drivers.push(`Performance dropped in ${r.regime} regime (${r.delta.toFixed(0)}%)`);
      }
    }

    // From execution deltas
    for (const e of execDeltas) {
      if (e.style !== 'MISSED_MOVES' && Math.abs(e.delta) > 0.05) {
        if (e.direction === 'UP') {
          drivers.push(`${e.style.replace(/_/g, ' ')} execution improved`);
        } else if (e.direction === 'DOWN') {
          drivers.push(`${e.style.replace(/_/g, ' ')} execution degraded`);
        }
      }
    }

    // Pattern-based
    const curBest = cur.patterns.best?.[0];
    const prevBest = prev.patterns.best?.[0];
    if (curBest && prevBest && curBest.pattern !== prevBest.pattern) {
      drivers.push(`Best pattern shifted: ${prevBest.pattern} → ${curBest.pattern}`);
    }

    // Source changes
    const curTop = cur.sources.topSources?.[0];
    const prevTop = prev.sources.topSources?.[0];
    if (curTop && prevTop && curTop.source !== prevTop.source) {
      drivers.push(`Top source changed: ${prevTop.source} → ${curTop.source}`);
    }

    return drivers.slice(0, 6);
  }
}

export const digestComparisonService = new DigestComparisonService();
