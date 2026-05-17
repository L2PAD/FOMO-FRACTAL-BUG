/**
 * Sentiment Reliability Types
 * ============================
 * 
 * BLOCK S1: Unified Reliability Index (URI) types.
 * 
 * URI combines all guards into single source of truth:
 * - DataHealth (parser)
 * - DriftHealth (PSI)
 * - CapitalHealth (equity/DD)
 * - CalibrationHealth (shadow performance)
 */

export type ReliabilityLevel = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';

export interface ReliabilityComponents {
  dataHealth: number;         // 0..1, from Parser Health Guard
  driftHealth: number;        // 0..1, from Drift Monitor
  capitalHealth: number;      // 0..1, from Capital/Risk layer
  calibrationHealth: number;  // 0..1, from Shadow stats
}

export interface ReliabilityActions {
  workersBlocked: boolean;
  trainingBlocked: boolean;
  promotionBlocked: boolean;
  confidenceMultiplier: number;
  sizeMultiplier: number;
  safeMode: boolean;           // F3: output becomes NEUTRAL when true
}

export interface SentimentReliabilityStatus {
  uriScore: number;           // 0..1
  level: ReliabilityLevel;
  components: ReliabilityComponents;
  reasons: string[];
  actions: ReliabilityActions;
  safeMode: boolean;          // F3: direct flag
  asOf: string;               // ISO timestamp
}

// URI thresholds
export const URI_THRESHOLDS = {
  OK: 0.75,
  WARN: 0.60,
  DEGRADED: 0.40,
};

// URI weights
export const URI_WEIGHTS = {
  dataHealth: 0.30,
  driftHealth: 0.30,
  capitalHealth: 0.25,
  calibrationHealth: 0.15,
};

console.log('[Sentiment-ML] Reliability Types loaded (BLOCK S1)');
