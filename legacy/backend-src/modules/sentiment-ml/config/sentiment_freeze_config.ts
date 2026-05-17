/**
 * Sentiment Module Freeze Configuration
 * ======================================
 * 
 * v1.0.0 FROZEN CONFIGURATION
 * 
 * This file contains the immutable configuration snapshot for the Sentiment module.
 * DO NOT MODIFY these values without creating a new version file.
 * 
 * Purpose:
 * - Protect proven configuration from accidental changes
 * - Document the exact parameters that achieved institutional-grade reliability
 * - Enable safe replication to other modules
 */

// ═══════════════════════════════════════════════════════════════
// FREEZE FLAG
// ═══════════════════════════════════════════════════════════════

export const SENTIMENT_FROZEN = process.env.SENTIMENT_FROZEN === 'true';

// ═══════════════════════════════════════════════════════════════
// IMMUTABLE CONFIG SNAPSHOT v1.0 (2025-12-17)
// ═══════════════════════════════════════════════════════════════

export const SENTIMENT_CONFIG_SNAPSHOT_V1 = Object.freeze({
  version: '1.0.0',
  frozenAt: '2025-12-17',
  freezeAuditVerdict: 'PASS',
  
  // Feature mode indicator
  featureMode: 'CORE_ONLY',
  featureModeNote: 'Connections layer unavailable - model operates on core features only',
  
  // Drift PSI features monitored
  driftFeatures: Object.freeze({
    features: ['bias', 'absBias', 'confidence', 'eventsCountLog'],
    weights: Object.freeze({
      bias: 0.40,
      absBias: 0.15,
      confidence: 0.30,
      eventsCountLog: 0.10,
    }),
  }),
  
  // Reliability thresholds
  reliability: Object.freeze({
    uriWeights: Object.freeze({
      dataHealth: 0.30,
      driftHealth: 0.25,
      capitalHealth: 0.25,
      calibrationHealth: 0.20,
    }),
    thresholds: Object.freeze({
      OK: 0.75,
      WARN: 0.60,
      DEGRADED: 0.40,
    }),
  }),
  
  // Drift stabilization config
  driftStabilizer: Object.freeze({
    emaAlpha: 0.2,
    psiOkMax: 0.15,
    psiWarnMax: 0.30,
    psiDegradedMax: 0.50,
    persistWarn: 3,
    persistDegraded: 2,
    persistCritical: 1,
  }),
  
  // Capital gates for promotion
  capitalGates: Object.freeze({
    promotion: Object.freeze({
      minCapitalHealth: 0.70,
      maxDD: 0.15,
      minExpectancy: 0,
      minSharpe: 0.10,
      minURI: 0.60,
    }),
    rollback: Object.freeze({
      maxDD: 0.20,
      maxCapitalHealth: 0.50,
    }),
  }),
  
  // Lifecycle settings
  lifecycle: Object.freeze({
    promotionCooldownDays: 56,
    sustainedWindows: 3,
    minEdgeDelta: 0.02,
  }),
  
  // Risk/regime settings
  risk: Object.freeze({
    regimeFilterVersion: 'regime.v1.1',
    chopThresholds: Object.freeze({
      atrPercentileFloor: 0.25,
      volumePercentileFloor: 0.20,
      rangePercentileFloor: 0.20,
    }),
  }),
});

// ═══════════════════════════════════════════════════════════════
// FREEZE GUARDS
// ═══════════════════════════════════════════════════════════════

/**
 * Check if a lifecycle mutation should be blocked.
 */
export function shouldBlockSentimentMutation(operation: string): boolean {
  if (!SENTIMENT_FROZEN) return false;
  
  const blockedOperations = [
    'retrain',
    'promote',
    'rollback',
    'schema_change',
    'config_update',
    'baseline_create',
  ];
  
  return blockedOperations.some(op => operation.toLowerCase().includes(op));
}

/**
 * Get the current freeze status for admin display.
 */
export function getSentimentFreezeStatus(): {
  frozen: boolean;
  version: string;
  featureMode: string;
  allowedOperations: string[];
  blockedOperations: string[];
} {
  return {
    frozen: SENTIMENT_FROZEN,
    version: SENTIMENT_CONFIG_SNAPSHOT_V1.version,
    featureMode: SENTIMENT_CONFIG_SNAPSHOT_V1.featureMode,
    allowedOperations: ['inference', 'monitoring', 'read_config', 'read_metrics', 'safe_mode'],
    blockedOperations: SENTIMENT_FROZEN 
      ? ['retrain', 'promote', 'rollback', 'schema_change', 'config_update', 'baseline_create']
      : [],
  };
}

console.log(`[Sentiment-ML] Freeze config loaded: FROZEN=${SENTIMENT_FROZEN}, featureMode=${SENTIMENT_CONFIG_SNAPSHOT_V1.featureMode}`);
