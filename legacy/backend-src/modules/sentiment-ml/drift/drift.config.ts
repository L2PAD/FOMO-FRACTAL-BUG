/**
 * Drift Stabilizer Configuration
 * ================================
 * 
 * BLOCK S3: Default configuration for drift stabilization.
 */

export interface DriftStabilizerConfig {
  // EMA smoothing factor (0-1, higher = more responsive)
  emaAlpha: number;

  // PSI thresholds for status
  psiOkMax: number;
  psiWarnMax: number;
  psiDegradedMax: number;

  // Persistence thresholds (consecutive runs required)
  persistWarn: number;
  persistDegraded: number;
  persistCritical: number;

  // Baseline age limits (days)
  maxBaselineAgeDays: number;
  baselineAgeWarnDays: number;
}

export const DEFAULT_DRIFT_STABILIZER_CONFIG: DriftStabilizerConfig = {
  emaAlpha: 0.2,
  
  psiOkMax: 0.15,
  psiWarnMax: 0.30,
  psiDegradedMax: 0.50,

  persistWarn: 3,
  persistDegraded: 2,
  persistCritical: 1,

  maxBaselineAgeDays: 45,
  baselineAgeWarnDays: 30,
};

console.log('[Sentiment-ML] Drift Config loaded (BLOCK S3)');
