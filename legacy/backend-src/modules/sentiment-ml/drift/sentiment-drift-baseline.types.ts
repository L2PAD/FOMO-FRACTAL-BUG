/**
 * Sentiment Drift Baseline Types
 * ================================
 * 
 * BLOCK S2: Baseline Versioning types.
 * 
 * Baseline stores feature distributions for PSI comparison.
 * Created ONLY when URI gates pass (prevents anchoring to bad regime).
 */

export type SentWindow = '24H' | '7D' | '30D';
export type BaselineCreateReason = 'AUTO' | 'MANUAL';

export interface FeatureHistogram {
  bins: number[];          // normalized counts, sum=1
  min: number;
  max: number;
  binCount: number;
}

export interface FeatureQuantiles {
  p05: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface FeatureDistribution {
  feature: string;
  hist: FeatureHistogram;
  q: FeatureQuantiles;
  n: number;              // sample count for this feature
}

export interface UriSnapshot {
  score: number;
  status: 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';
  dataHealth: number;
  driftHealth: number;
  capitalHealth: number;
  calibrationHealth: number;
  reasons: string[];
}

export interface SentimentDriftBaselineDoc {
  module: 'sentiment';
  window: SentWindow;
  version: number;
  createdAt: Date;
  reason: BaselineCreateReason;
  notes?: string;
  sampleCount: number;
  source: 'aggregates' | 'samples';
  featureDistributions: Record<string, FeatureDistribution>;
  uriAtCreation: UriSnapshot;
}

// Baseline creation gates
export const BASELINE_GATES = {
  uriMinOk: 0.75,           // URI score minimum for AUTO
  uriMinFloor: 0.60,        // Hard floor for MANUAL
  dataHealthMin: 0.80,
  capitalHealthMin: 0.70,
  calibrationHealthMin: 0.70,
  minSamples: 100,          // Minimum samples for baseline
  cooldownDays: 14,         // Minimum days between baselines
};

// Features to track in baseline
export const BASELINE_FEATURES = [
  'bias',
  'absBias',
  'confidence',
  'eventsCountLog',
] as const;

console.log('[Sentiment-ML] Drift Baseline Types loaded (BLOCK S2)');
