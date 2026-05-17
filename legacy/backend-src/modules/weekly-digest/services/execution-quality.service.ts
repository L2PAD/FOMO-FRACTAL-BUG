/**
 * Execution Quality Service (Weekly Digest)
 *
 * Aggregates execution scores from outcome reviews to build the
 * "Execution Quality" block in the weekly digest.
 *
 * Answers: "are we executing well, or just thinking well?"
 */

export interface ExecutionQualityDigest {
  avgScore: number;
  avgGrade: string;
  totalEvaluated: number;
  byDirection: {
    LONG: { count: number; avgScore: number };
    SHORT: { count: number; avgScore: number };
  };
  entryQuality: {
    excellent: number;
    good: number;
    ok: number;
    bad: number;
  };
  timingQuality: {
    excellent: number;
    good: number;
    ok: number;
    late: number;
    bad: number;
  };
  avgSlippageLeakage: number;
  avgMissedMove: number;
  topIssues: string[];
  bestStyle: { style: string; avgScore: number } | null;
  worstStyle: { style: string; avgScore: number } | null;
  executionLessons: string[];
}

class ExecutionQualityService {
  analyze(reviews: any[]): ExecutionQualityDigest {
    const withExec = reviews.filter(r =>
      r.executionQuality || r.trace?.executionQuality
    );

    if (withExec.length === 0) {
      return this.emptyDigest();
    }

    const scores: number[] = [];
    const grades: string[] = [];
    const longScores: number[] = [];
    const shortScores: number[] = [];
    const entryQ: Record<string, number> = { EXCELLENT: 0, GOOD: 0, OK: 0, BAD: 0 };
    const timingQ: Record<string, number> = { EXCELLENT: 0, GOOD: 0, OK: 0, LATE: 0, BAD: 0 };
    const leakages: number[] = [];
    const missedMoves: number[] = [];
    const lessonCounts = new Map<string, number>();
    const styleBuckets = new Map<string, number[]>();

    for (const r of withExec) {
      const eq = r.executionQuality || r.trace?.executionQuality;
      if (!eq) continue;

      const score = eq.score ?? 0;
      scores.push(score);
      grades.push(eq.grade || '');

      if (eq.direction === 'LONG') longScores.push(score);
      else shortScores.push(score);

      const eqKey = (eq.entryQuality || '').toUpperCase();
      if (eqKey in entryQ) entryQ[eqKey]++;

      const tqKey = (eq.timingQuality || '').toUpperCase();
      if (tqKey in timingQ) timingQ[tqKey]++;

      leakages.push(eq.slippageLeakage ?? 0);
      missedMoves.push(eq.missedMove ?? 0);

      // Count lessons for top issues
      for (const l of (eq.lessons || [])) {
        lessonCounts.set(l, (lessonCounts.get(l) || 0) + 1);
      }

      // Style tracking from trace
      const style = r.trace?.recommendation?.entryStyle ||
                    r.trace?.execution?.entryStyle || 'UNKNOWN';
      if (!styleBuckets.has(style)) styleBuckets.set(style, []);
      styleBuckets.get(style)!.push(score);
    }

    const avg = (arr: number[]) => arr.length > 0
      ? Math.round((arr.reduce((a, b) => a + b, 0) / arr.length) * 100) / 100
      : 0;

    // Average grade
    const gradeValues: Record<string, number> = { A: 5, B: 4, C: 3, D: 2, F: 1 };
    const avgGradeNum = grades.length > 0
      ? grades.reduce((s, g) => s + (gradeValues[g] || 3), 0) / grades.length
      : 0;
    const avgGrade = avgGradeNum >= 4.5 ? 'A' : avgGradeNum >= 3.5 ? 'B' :
                     avgGradeNum >= 2.5 ? 'C' : avgGradeNum >= 1.5 ? 'D' : 'F';

    // Top issues (most recurring lessons)
    const sortedLessons = [...lessonCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([l]) => l);

    // Best/worst styles
    let bestStyle: { style: string; avgScore: number } | null = null;
    let worstStyle: { style: string; avgScore: number } | null = null;
    let bestAvg = -1;
    let worstAvg = 2;

    for (const [style, ss] of styleBuckets.entries()) {
      if (ss.length < 1) continue;
      const a = avg(ss);
      if (a > bestAvg) { bestAvg = a; bestStyle = { style, avgScore: a }; }
      if (a < worstAvg) { worstAvg = a; worstStyle = { style, avgScore: a }; }
    }

    // Generate execution-specific lessons
    const executionLessons: string[] = [];
    if (timingQ.LATE + timingQ.BAD > withExec.length * 0.3) {
      executionLessons.push('Late timing is a recurring issue — consider faster execution');
    }
    if (avg(leakages) > 0.02) {
      executionLessons.push(`Average slippage leakage ${(avg(leakages) * 100).toFixed(1)}% — review order sizing`);
    }
    if (avg(missedMoves) > 0.05) {
      executionLessons.push(`Avg missed move ${(avg(missedMoves) * 100).toFixed(1)}% — WAIT strategy may be too conservative`);
    }
    if (bestStyle && worstStyle && bestStyle.style !== worstStyle.style) {
      executionLessons.push(`${bestStyle.style} outperforms ${worstStyle.style} (${(bestStyle.avgScore * 100).toFixed(0)}% vs ${(worstStyle.avgScore * 100).toFixed(0)}%)`);
    }
    if (longScores.length > 0 && shortScores.length > 0) {
      const ld = avg(longScores);
      const sd = avg(shortScores);
      if (Math.abs(ld - sd) > 0.1) {
        const better = ld > sd ? 'LONG' : 'SHORT';
        executionLessons.push(`${better} execution significantly better (${(Math.max(ld, sd) * 100).toFixed(0)}% vs ${(Math.min(ld, sd) * 100).toFixed(0)}%)`);
      }
    }

    return {
      avgScore: avg(scores),
      avgGrade,
      totalEvaluated: withExec.length,
      byDirection: {
        LONG: { count: longScores.length, avgScore: avg(longScores) },
        SHORT: { count: shortScores.length, avgScore: avg(shortScores) },
      },
      entryQuality: {
        excellent: entryQ.EXCELLENT,
        good: entryQ.GOOD,
        ok: entryQ.OK,
        bad: entryQ.BAD,
      },
      timingQuality: {
        excellent: timingQ.EXCELLENT,
        good: timingQ.GOOD,
        ok: timingQ.OK,
        late: timingQ.LATE,
        bad: timingQ.BAD,
      },
      avgSlippageLeakage: avg(leakages),
      avgMissedMove: avg(missedMoves),
      topIssues: sortedLessons,
      bestStyle,
      worstStyle,
      executionLessons: executionLessons.slice(0, 4),
    };
  }

  private emptyDigest(): ExecutionQualityDigest {
    return {
      avgScore: 0, avgGrade: 'N/A', totalEvaluated: 0,
      byDirection: {
        LONG: { count: 0, avgScore: 0 },
        SHORT: { count: 0, avgScore: 0 },
      },
      entryQuality: { excellent: 0, good: 0, ok: 0, bad: 0 },
      timingQuality: { excellent: 0, good: 0, ok: 0, late: 0, bad: 0 },
      avgSlippageLeakage: 0, avgMissedMove: 0,
      topIssues: [], bestStyle: null, worstStyle: null, executionLessons: [],
    };
  }
}

export const executionQualityService = new ExecutionQualityService();
