/**
 * Execution Anomaly Types
 *
 * Types for anomaly detection, pattern recognition,
 * degradation tracking, and recommendation building.
 */

import type { ExecutionContext } from './execution-context.types.js';

// --- Anomaly ---

export type AnomalySeverity = 'WARNING' | 'CRITICAL';

export interface ExecutionAnomaly {
  anomalyId: string;
  type: 'EXECUTION_ANOMALY';
  contextKey: string;
  context: ExecutionContext;
  asset: string;
  consecutiveLow: number;
  avgScore: number;
  worstScore: number;
  scores: number[];
  consistency: number;        // 0-1, how consistent the low scores are
  sampleSize: number;
  severity: AnomalySeverity;
  pattern: AnomalyPattern;
  degradation: DegradationResult;
  styleAnalysis: StyleAnalysisResult;
  recommendation: Recommendation;
  confidenceDriftContribution: number; // 0-1, how much overconfidence contributed
  suppressedUntil: string;    // ISO timestamp — no new alerts for this context until then
  acknowledged: boolean;
  timestamp: string;
}

// --- Pattern ---

export type PatternType = 'MISSED_MOVES' | 'BAD_ENTRIES' | 'HIGH_SLIPPAGE' | 'LATE_TIMING' | 'MIXED';

export interface AnomalyPattern {
  pattern: PatternType;
  subPatterns: PatternType[];
  dominantIssue: string;
  details: string[];
}

// --- Degradation ---

export type DegradationState = 'DEGRADING' | 'NOISE' | 'STABLE' | 'IMPROVING';

export interface DegradationResult {
  state: DegradationState;
  slope: number;              // negative = degrading
  trendStrength: number;      // 0-1
  windowDays: number;
}

// --- Style Analysis ---

export interface StyleAnalysisResult {
  currentStyle: string;
  currentAvgScore: number;
  bestStyle: string;
  bestAvgScore: number;
  worstStyle: string;
  worstAvgScore: number;
  delta: number;              // bestAvgScore - currentAvgScore
  allStyles: { style: string; avgScore: number; count: number }[];
}

// --- Recommendation ---

export type SuggestedAction =
  | 'SWITCH_STYLE'
  | 'ADJUST_TIMING'
  | 'REDUCE_WAIT'
  | 'USE_MARKET'
  | 'USE_LIMIT'
  | 'REDUCE_SIZE'
  | 'PAUSE_CONTEXT'
  | 'NO_CHANGE';

export interface Recommendation {
  suggestedAction: SuggestedAction;
  from: string;
  to: string;
  reason: string;
  confidence: number;         // 0-1
  details: string[];
}

// --- Alert Format (Telegram/UI) ---

export interface FormattedAlert {
  title: string;
  contextLine: string;
  issueLine: string;
  patternLines: string[];
  currentStyleLine: string;
  suggestedLine: string;
  whyLines: string[];
  confidenceLine: string;
  fullText: string;           // Pre-formatted for Telegram
  htmlText: string;           // HTML formatted for Telegram
}
