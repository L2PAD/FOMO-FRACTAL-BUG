/**
 * OnChain V2 — Final Output Contracts
 * =====================================
 * 
 * 🔒 CANONICAL CONTRACT v1.0.0 — FROZEN
 * 
 * FREEZE DATE: 2026-02-22
 * 
 * This is the ONLY output consumers (MetaBrain, Prediction UI) should use.
 * Raw observations are internal implementation details.
 * 
 * FREEZE STATUS: FINAL (v1.0.0)
 * - NO field name changes
 * - NO field removal
 * - NO semantic changes
 * - Only additive changes with version bump
 * 
 * CONSUMERS:
 * - Prediction UI (OnChain Signal Tab)
 * - MetaBrain (future)
 * - External APIs (future)
 */

import {
  ONCHAIN_CONTRACT_VERSION,
  PSI_WARN_THRESHOLD,
  PSI_DEGRADED_THRESHOLD,
  PSI_CRITICAL_THRESHOLD,
  MODIFIER_HEALTHY,
  MODIFIER_WARN,
  MODIFIER_DEGRADED,
  MODIFIER_CRITICAL,
  MIN_SAMPLES_30D,
  WARN_SAMPLES_30D,
  CONFIDENCE_CAP_NO_DATA,
  CONFIDENCE_CAP_LOW_SAMPLES,
  CONFIDENCE_CAP_STALE,
  EMA_ALPHA,
  EMA_WINDOW,
  EMA_WARMUP_MIN,
  MAX_DATA_AGE_MS,
} from './governance.constants.js';

// ═══════════════════════════════════════════════════════════════
// GUARDRAIL STATE & ACTIONS
// ═══════════════════════════════════════════════════════════════

export type GuardrailState = 
  | 'HEALTHY'      // All systems nominal
  | 'WARN'         // Minor issues, reduced confidence
  | 'DEGRADED'     // Significant issues, heavily reduced confidence
  | 'CRITICAL'     // Major issues, force safe state
  | 'FROZEN';      // Module frozen, no updates

export type GuardrailAction =
  | 'NONE'           // No intervention
  | 'DOWNWEIGHT'     // Reduce confidence
  | 'FORCE_SAFE'     // Force safe state
  | 'FREEZE'         // Module frozen
  | 'BLOCK_OUTPUT';  // No output (NO_DATA scenario)

export type FinalState =
  | 'ACCUMULATION'  // Net accumulation detected
  | 'DISTRIBUTION'  // Net distribution detected
  | 'NEUTRAL'       // No clear direction
  | 'SAFE'          // Forced safe state (guardrail triggered)
  | 'NO_DATA';      // Insufficient data

export type FinalStateReason =
  | 'SIGNAL_NEUTRAL'         // Genuine neutral signal
  | 'SIGNAL_ACCUMULATION'    // Genuine accumulation
  | 'SIGNAL_DISTRIBUTION'    // Genuine distribution
  | 'LOW_CONFIDENCE'         // Confidence below threshold
  | 'GUARDRAIL_FORCED_SAFE'  // Guardrail triggered SAFE
  | 'NO_DATA_FORCED_SAFE'    // No data, forced SAFE
  | 'DATA_STALE_FORCED_SAFE' // Stale data, forced SAFE
  | 'NO_DATA';               // Truly no data

export type DataState = 'OK' | 'STALE' | 'NO_DATA';

// ═══════════════════════════════════════════════════════════════
// FLAGS WITH SEVERITY
// ═══════════════════════════════════════════════════════════════

export type FlagSeverity = 'INFO' | 'WARN' | 'CRITICAL';
export type FlagDomain = 'DATA' | 'DRIFT' | 'MODEL' | 'GOV' | 'POST';

export interface FinalFlag {
  code: string;
  severity: FlagSeverity;
  domain: FlagDomain;
}

// Flag definitions
export const FLAG_DEFINITIONS: Record<string, { severity: FlagSeverity; domain: FlagDomain }> = {
  LOW_SAMPLES: { severity: 'CRITICAL', domain: 'DATA' },
  NO_DATA: { severity: 'CRITICAL', domain: 'DATA' },
  DATA_STALE: { severity: 'WARN', domain: 'DATA' },
  DRIFT_WARN: { severity: 'WARN', domain: 'DRIFT' },
  DRIFT_DEGRADED: { severity: 'CRITICAL', domain: 'DRIFT' },
  DRIFT_CRITICAL: { severity: 'CRITICAL', domain: 'DRIFT' },
  PROVIDER_UNHEALTHY: { severity: 'WARN', domain: 'DATA' },
  EMA_SMOOTHED: { severity: 'INFO', domain: 'POST' },
  CONFIDENCE_REDUCED: { severity: 'INFO', domain: 'POST' },
  CONFIDENCE_CAPPED: { severity: 'WARN', domain: 'POST' },
  FORCED_SAFE: { severity: 'CRITICAL', domain: 'GOV' },
};

// ═══════════════════════════════════════════════════════════════
// FINAL OUTPUT
// ═══════════════════════════════════════════════════════════════

export interface OnchainFinalOutput {
  // Identity
  symbol: string;
  t0: number;
  window: string;
  
  // Final values (after all adjustments)
  finalScore: number;        // 0-1, EMA smoothed
  finalConfidence: number;   // 0-1, with guardrail modifier
  finalState: FinalState;    // Governed state
  finalStateReason: FinalStateReason;  // Why this state
  
  // Data health
  dataState: DataState;      // OK | STALE | NO_DATA
  
  // Drivers for explainability
  drivers: string[];
  
  // Flags with severity
  flags: FinalFlag[];
  
  // Governance metadata
  governance: {
    policyVersion: string;
    guardrailState: GuardrailState;
    guardrailAction: GuardrailAction;
    guardrailActionReasons: string[];
    psi: number;
    sampleCount30d: number;
    emaWindow: number;
    emaApplied: boolean;
    confidenceModifier: number;
    confidenceCapped: boolean;
  };
  
  // Raw values (for debugging/comparison)
  raw: {
    score: number;
    confidence: number;
    state: string;
  };
  
  // Processing metadata
  processedAt: number;
}

// ═══════════════════════════════════════════════════════════════
// GUARDRAIL CONFIG
// ═══════════════════════════════════════════════════════════════

export interface GuardrailConfig {
  // Sample thresholds
  minSamples30d: number;
  warnSamples30d: number;
  
  // PSI thresholds
  psiWarn: number;
  psiDegraded: number;
  psiCritical: number;
  
  // Confidence modifiers (institutional ladder)
  modifierHealthy: number;
  modifierWarn: number;
  modifierDegraded: number;
  modifierCritical: number;
  
  // Confidence caps
  noDataConfidenceCap: number;
  lowSamplesConfidenceCap: number;
  staleDataConfidenceCap: number;
  
  // EMA
  emaAlpha: number;
  emaWindow: number;
  emaWarmupMin: number;
  
  // Provider health
  providerHealthRequired: boolean;
  
  // Data freshness
  maxDataAgeMs: number;
}

export const DEFAULT_GUARDRAIL_CONFIG: GuardrailConfig = {
  // Samples (from frozen constants)
  minSamples30d: MIN_SAMPLES_30D,
  warnSamples30d: WARN_SAMPLES_30D,
  
  // PSI (from frozen constants)
  psiWarn: PSI_WARN_THRESHOLD,
  psiDegraded: PSI_DEGRADED_THRESHOLD,
  psiCritical: PSI_CRITICAL_THRESHOLD,
  
  // Modifiers (institutional ladder - from frozen constants)
  modifierHealthy: MODIFIER_HEALTHY,
  modifierWarn: MODIFIER_WARN,
  modifierDegraded: MODIFIER_DEGRADED,
  modifierCritical: MODIFIER_CRITICAL,
  
  // Confidence caps (from frozen constants)
  noDataConfidenceCap: CONFIDENCE_CAP_NO_DATA,
  lowSamplesConfidenceCap: CONFIDENCE_CAP_LOW_SAMPLES,
  staleDataConfidenceCap: CONFIDENCE_CAP_STALE,
  
  // EMA (from frozen constants)
  emaAlpha: EMA_ALPHA,
  emaWindow: EMA_WINDOW,
  emaWarmupMin: EMA_WARMUP_MIN,
  
  // Provider
  providerHealthRequired: true,
  
  // Freshness (from frozen constants)
  maxDataAgeMs: MAX_DATA_AGE_MS,
};

console.log(`[OnChain V2] Final Contracts loaded — ${ONCHAIN_CONTRACT_VERSION}`);
