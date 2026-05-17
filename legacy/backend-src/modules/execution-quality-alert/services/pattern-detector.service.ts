/**
 * Pattern Detector
 *
 * Identifies execution failure patterns:
 *   MISSED_MOVES — waited too long, move happened without you
 *   BAD_ENTRIES  — entered at wrong price / outside optimal zone
 *   HIGH_SLIPPAGE — execution leaked value through slippage
 *   LATE_TIMING  — entered after edge decayed
 *   MIXED        — no single dominant pattern
 */

import type { ExecutionScoreEntry } from '../types/execution-context.types.js';
import type { AnomalyPattern, PatternType } from '../types/execution-anomaly.types.js';

const MISSED_MOVE_THRESHOLD = 0.3;
const BAD_ENTRY_THRESHOLD = 0.35;
const HIGH_SLIPPAGE_THRESHOLD = 0.03;
const LATE_TIMING_THRESHOLD = 0.35;
const DOMINANCE_THRESHOLD = 0.5; // Pattern must be >50% of issues to be dominant

class PatternDetectorService {
  /**
   * Detect the dominant execution failure pattern from recent entries.
   */
  detect(entries: ExecutionScoreEntry[]): AnomalyPattern {
    if (entries.length === 0) {
      return { pattern: 'MIXED', subPatterns: [], dominantIssue: 'No data', details: [] };
    }

    const lowEntries = entries.filter(e => e.score < 0.4);
    if (lowEntries.length === 0) {
      return { pattern: 'MIXED', subPatterns: [], dominantIssue: 'No low scores', details: [] };
    }

    const counts: Record<PatternType, number> = {
      MISSED_MOVES: 0,
      BAD_ENTRIES: 0,
      HIGH_SLIPPAGE: 0,
      LATE_TIMING: 0,
      MIXED: 0,
    };

    const details: string[] = [];

    for (const entry of lowEntries) {
      // Check missed moves (high opportunity cost / WAIT_TOO_LONG)
      if (entry.opportunityReason === 'WAIT_TOO_LONG' || entry.missedMove > MISSED_MOVE_THRESHOLD) {
        counts.MISSED_MOVES++;
      }

      // Check bad entries (low entry score)
      if (entry.entryScore < BAD_ENTRY_THRESHOLD) {
        counts.BAD_ENTRIES++;
      }

      // Check high slippage
      if (entry.slippageLeakage > HIGH_SLIPPAGE_THRESHOLD) {
        counts.HIGH_SLIPPAGE++;
      }

      // Check late timing
      if (entry.timingScore < LATE_TIMING_THRESHOLD) {
        counts.LATE_TIMING++;
      }
    }

    // Find dominant pattern
    const total = lowEntries.length;
    const subPatterns: PatternType[] = [];
    let maxCount = 0;
    let dominant: PatternType = 'MIXED';

    for (const [pattern, count] of Object.entries(counts) as [PatternType, number][]) {
      if (pattern === 'MIXED') continue;
      if (count > 0) subPatterns.push(pattern);
      if (count > maxCount) {
        maxCount = count;
        dominant = pattern;
      }
    }

    // Only set dominant if it's a clear majority
    if (maxCount / total < DOMINANCE_THRESHOLD) {
      dominant = 'MIXED';
    }

    // Build detail strings
    if (counts.MISSED_MOVES > 0) {
      const avgMissed = lowEntries
        .filter(e => e.missedMove > 0)
        .reduce((s, e) => s + e.missedMove, 0) / Math.max(1, counts.MISSED_MOVES);
      details.push(`Missed ${counts.MISSED_MOVES} moves (avg missed: ${(avgMissed * 100).toFixed(1)}%)`);
    }
    if (counts.BAD_ENTRIES > 0) {
      const avgEntry = lowEntries
        .filter(e => e.entryScore < BAD_ENTRY_THRESHOLD)
        .reduce((s, e) => s + e.entryScore, 0) / Math.max(1, counts.BAD_ENTRIES);
      details.push(`${counts.BAD_ENTRIES} bad entries (avg entry score: ${(avgEntry * 100).toFixed(0)}%)`);
    }
    if (counts.HIGH_SLIPPAGE > 0) {
      details.push(`${counts.HIGH_SLIPPAGE} high-slippage executions`);
    }
    if (counts.LATE_TIMING > 0) {
      details.push(`${counts.LATE_TIMING} late-timed entries`);
    }

    const dominantIssue = this.describeDominant(dominant, counts, total);

    return {
      pattern: dominant,
      subPatterns,
      dominantIssue,
      details,
    };
  }

  private describeDominant(pattern: PatternType, counts: Record<PatternType, number>, total: number): string {
    switch (pattern) {
      case 'MISSED_MOVES':
        return `WAIT strategy too conservative — missed ${counts.MISSED_MOVES}/${total} moves`;
      case 'BAD_ENTRIES':
        return `Entry quality consistently poor — ${counts.BAD_ENTRIES}/${total} outside optimal zone`;
      case 'HIGH_SLIPPAGE':
        return `Execution leaking value through slippage — ${counts.HIGH_SLIPPAGE}/${total} cases`;
      case 'LATE_TIMING':
        return `Entering after edge decay — ${counts.LATE_TIMING}/${total} entries too late`;
      default:
        return 'Multiple issues detected — no single dominant pattern';
    }
  }
}

export const patternDetectorService = new PatternDetectorService();
