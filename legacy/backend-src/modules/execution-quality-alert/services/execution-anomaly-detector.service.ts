/**
 * Execution Anomaly Detector
 *
 * Core detection logic:
 *   executionScore < 0.4 AND occurrences >= 3 AND same context AND within 7 days
 *
 * Enhanced with:
 *   - avgScore, worstScore, consistency, sampleSize
 *   - consistency filter (ignore if scores are too spread)
 *   - suppression check (no duplicate alerts within 24h for same context)
 */

import type { ExecutionScoreEntry } from '../types/execution-context.types.js';
import { anomalyRepo } from '../repositories/execution-anomaly.repository.js';

const SCORE_THRESHOLD = 0.4;
const MIN_OCCURRENCES = 3;
const MIN_CONSISTENCY = 0.3;    // minimum consistency to fire alert
const TIME_WINDOW_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

export interface AnomalyDetectionResult {
  detected: boolean;
  consecutiveLow: number;
  avgScore: number;
  worstScore: number;
  consistency: number;
  sampleSize: number;
  scores: number[];
  reason: string;
}

class ExecutionAnomalyDetectorService {
  /**
   * Analyze entries within a context to detect anomalies.
   * Only considers entries within the 7-day time window.
   */
  detect(entries: ExecutionScoreEntry[]): AnomalyDetectionResult {
    const cutoff = new Date(Date.now() - TIME_WINDOW_MS).toISOString();
    const recent = entries.filter(e => e.timestamp >= cutoff);

    if (recent.length < MIN_OCCURRENCES) {
      return this.noAnomaly(recent.length, 'Insufficient sample size within time window');
    }

    // Count consecutive low scores from the most recent
    const sorted = [...recent].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    let consecutiveLow = 0;
    const lowScores: number[] = [];

    for (const entry of sorted) {
      if (entry.score < SCORE_THRESHOLD) {
        consecutiveLow++;
        lowScores.push(entry.score);
      } else {
        break; // streak broken
      }
    }

    if (consecutiveLow < MIN_OCCURRENCES) {
      return this.noAnomaly(recent.length, `Only ${consecutiveLow} consecutive low scores (need ${MIN_OCCURRENCES})`);
    }

    const scores = lowScores.slice(0, consecutiveLow);
    const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
    const worstScore = Math.min(...scores);

    // Consistency: 1 - normalized std deviation (higher = more consistent)
    const mean = avgScore;
    const variance = scores.reduce((sum, s) => sum + (s - mean) ** 2, 0) / scores.length;
    const stdDev = Math.sqrt(variance);
    const consistency = Math.max(0, 1 - stdDev / SCORE_THRESHOLD);

    if (consistency < MIN_CONSISTENCY) {
      return this.noAnomaly(recent.length, `Low consistency (${(consistency * 100).toFixed(0)}%) — likely noise`);
    }

    return {
      detected: true,
      consecutiveLow,
      avgScore: Math.round(avgScore * 1000) / 1000,
      worstScore: Math.round(worstScore * 1000) / 1000,
      consistency: Math.round(consistency * 100) / 100,
      sampleSize: recent.length,
      scores,
      reason: `${consecutiveLow} consecutive scores below ${SCORE_THRESHOLD} (avg: ${(avgScore * 100).toFixed(1)}%)`,
    };
  }

  /**
   * Check if the context is currently suppressed.
   */
  async isSuppressed(contextKey: string): Promise<boolean> {
    return anomalyRepo.isSuppressed(contextKey);
  }

  private noAnomaly(sampleSize: number, reason: string): AnomalyDetectionResult {
    return {
      detected: false,
      consecutiveLow: 0,
      avgScore: 0,
      worstScore: 0,
      consistency: 0,
      sampleSize,
      scores: [],
      reason,
    };
  }
}

export const anomalyDetectorService = new ExecutionAnomalyDetectorService();
