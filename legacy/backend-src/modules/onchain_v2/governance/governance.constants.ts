/**
 * OnChain V2 — Governance Constants
 * ===================================
 * 
 * 🔒 FROZEN v1.0.0 — DO NOT MODIFY
 * 
 * These constants define the immutable governance parameters.
 * Changes require version bump and migration plan.
 * 
 * FREEZE DATE: 2026-02-22
 * FREEZE AUTHOR: SYSTEM
 * 
 * RULES:
 * - NO threshold changes without version bump
 * - NO PSI level changes
 * - NO confidence modifier changes
 * - NO EMA parameter changes
 */

// ═══════════════════════════════════════════════════════════════
// VERSION
// ═══════════════════════════════════════════════════════════════

export const ONCHAIN_ENGINE_VERSION = 'v1.0.0';
export const ONCHAIN_CONTRACT_VERSION = 'v1.0.0';
export const ONCHAIN_FREEZE_DATE = '2026-02-22';

// ═══════════════════════════════════════════════════════════════
// PSI DRIFT THRESHOLDS (IMMUTABLE)
// ═══════════════════════════════════════════════════════════════

/** PSI < 0.15 = OK (no drift detected) */
export const PSI_OK_THRESHOLD = 0.15;

/** 0.15 <= PSI < 0.30 = WARN (minor drift) */
export const PSI_WARN_THRESHOLD = 0.15;

/** 0.30 <= PSI < 0.50 = DEGRADED (significant drift) */
export const PSI_DEGRADED_THRESHOLD = 0.30;

/** PSI >= 0.50 = CRITICAL (major drift, force safe) */
export const PSI_CRITICAL_THRESHOLD = 0.50;

// ═══════════════════════════════════════════════════════════════
// SAMPLE THRESHOLDS (IMMUTABLE)
// ═══════════════════════════════════════════════════════════════

/** Minimum samples for any output */
export const MIN_SAMPLES_30D = 50;

/** Samples below this trigger WARN */
export const WARN_SAMPLES_30D = 150;

/** Auto-baseline requires this many samples */
export const AUTO_BASELINE_MIN_SAMPLES = 200;

/** Auto-baseline requires stable PSI for N cycles */
export const AUTO_BASELINE_STABLE_CYCLES = 3;

// ═══════════════════════════════════════════════════════════════
// CONFIDENCE MODIFIERS (INSTITUTIONAL LADDER)
// ═══════════════════════════════════════════════════════════════

/** HEALTHY state: full confidence */
export const MODIFIER_HEALTHY = 1.0;

/** WARN state: reduced confidence */
export const MODIFIER_WARN = 0.7;

/** DEGRADED state: heavily reduced confidence */
export const MODIFIER_DEGRADED = 0.4;

/** CRITICAL state: minimal confidence (near-zero trust) */
export const MODIFIER_CRITICAL = 0.15;

// ═══════════════════════════════════════════════════════════════
// CONFIDENCE CAPS
// ═══════════════════════════════════════════════════════════════

/** NO_DATA: zero confidence */
export const CONFIDENCE_CAP_NO_DATA = 0;

/** LOW_SAMPLES: hard cap */
export const CONFIDENCE_CAP_LOW_SAMPLES = 0.15;

/** STALE_DATA: reduced cap */
export const CONFIDENCE_CAP_STALE = 0.20;

// ═══════════════════════════════════════════════════════════════
// EMA PARAMETERS
// ═══════════════════════════════════════════════════════════════

/** EMA smoothing factor (0.2 = ~5 sample effective window) */
export const EMA_ALPHA = 0.2;

/** EMA window for display purposes */
export const EMA_WINDOW = 5;

/** Minimum samples before EMA is applied */
export const EMA_WARMUP_MIN = 3;

// ═══════════════════════════════════════════════════════════════
// DATA FRESHNESS
// ═══════════════════════════════════════════════════════════════

/** Maximum data age before considered STALE (24 hours) */
export const MAX_DATA_AGE_MS = 24 * 60 * 60 * 1000;

// ═══════════════════════════════════════════════════════════════
// GUARDRAIL STATE → ACTION MAPPING
// ═══════════════════════════════════════════════════════════════

export const GUARDRAIL_STATE_ACTIONS: Record<string, { action: string; modifier: number }> = {
  HEALTHY: { action: 'NONE', modifier: MODIFIER_HEALTHY },
  WARN: { action: 'DOWNWEIGHT', modifier: MODIFIER_WARN },
  DEGRADED: { action: 'DOWNWEIGHT', modifier: MODIFIER_DEGRADED },
  CRITICAL: { action: 'FORCE_SAFE', modifier: MODIFIER_CRITICAL },
  FROZEN: { action: 'FREEZE', modifier: 0 },
};

// ═══════════════════════════════════════════════════════════════
// SCORE → STATE MAPPING
// ═══════════════════════════════════════════════════════════════

/** Score >= 0.62 = ACCUMULATION */
export const SCORE_ACCUMULATION_THRESHOLD = 0.62;

/** Score <= 0.38 = DISTRIBUTION */
export const SCORE_DISTRIBUTION_THRESHOLD = 0.38;

// ═══════════════════════════════════════════════════════════════
// FREEZE VALIDATION
// ═══════════════════════════════════════════════════════════════

/**
 * Validates that all constants are within expected ranges.
 * Call this at startup to catch any accidental modifications.
 */
export function validateFreezeIntegrity(): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  // PSI thresholds must be ordered
  if (PSI_WARN_THRESHOLD >= PSI_DEGRADED_THRESHOLD) {
    errors.push('PSI_WARN_THRESHOLD must be < PSI_DEGRADED_THRESHOLD');
  }
  if (PSI_DEGRADED_THRESHOLD >= PSI_CRITICAL_THRESHOLD) {
    errors.push('PSI_DEGRADED_THRESHOLD must be < PSI_CRITICAL_THRESHOLD');
  }
  
  // Modifiers must be in range and ordered
  if (MODIFIER_HEALTHY !== 1.0) {
    errors.push('MODIFIER_HEALTHY must be 1.0');
  }
  if (MODIFIER_WARN >= MODIFIER_HEALTHY || MODIFIER_WARN <= 0) {
    errors.push('MODIFIER_WARN must be in (0, 1.0)');
  }
  if (MODIFIER_DEGRADED >= MODIFIER_WARN || MODIFIER_DEGRADED <= 0) {
    errors.push('MODIFIER_DEGRADED must be in (0, MODIFIER_WARN)');
  }
  if (MODIFIER_CRITICAL >= MODIFIER_DEGRADED || MODIFIER_CRITICAL <= 0) {
    errors.push('MODIFIER_CRITICAL must be in (0, MODIFIER_DEGRADED)');
  }
  
  // Score thresholds
  if (SCORE_ACCUMULATION_THRESHOLD <= 0.5 || SCORE_ACCUMULATION_THRESHOLD > 1) {
    errors.push('SCORE_ACCUMULATION_THRESHOLD must be in (0.5, 1]');
  }
  if (SCORE_DISTRIBUTION_THRESHOLD >= 0.5 || SCORE_DISTRIBUTION_THRESHOLD < 0) {
    errors.push('SCORE_DISTRIBUTION_THRESHOLD must be in [0, 0.5)');
  }
  
  // Sample thresholds
  if (MIN_SAMPLES_30D <= 0) {
    errors.push('MIN_SAMPLES_30D must be > 0');
  }
  if (WARN_SAMPLES_30D <= MIN_SAMPLES_30D) {
    errors.push('WARN_SAMPLES_30D must be > MIN_SAMPLES_30D');
  }
  if (AUTO_BASELINE_MIN_SAMPLES <= WARN_SAMPLES_30D) {
    errors.push('AUTO_BASELINE_MIN_SAMPLES must be > WARN_SAMPLES_30D');
  }
  
  // EMA
  if (EMA_ALPHA <= 0 || EMA_ALPHA >= 1) {
    errors.push('EMA_ALPHA must be in (0, 1)');
  }
  
  return {
    valid: errors.length === 0,
    errors,
  };
}

// Run validation at module load
const freezeValidation = validateFreezeIntegrity();
if (!freezeValidation.valid) {
  console.error('[OnChain V2] FREEZE INTEGRITY FAILED:', freezeValidation.errors);
  throw new Error(`OnChain freeze integrity check failed: ${freezeValidation.errors.join(', ')}`);
}

console.log(`[OnChain V2] Governance Constants loaded — ${ONCHAIN_ENGINE_VERSION} (frozen ${ONCHAIN_FREEZE_DATE})`);
