/**
 * OnChain V2 — LiquidityScore v2 Contracts
 * ==========================================
 * 
 * BLOCK 7: FROZEN v2.0.0 — 2026-02-24
 * 
 * ⚠️  DO NOT MODIFY without version bump to v2.0.1+
 *     Any changes require Cold Restart validation.
 */

export const LARE_V2_VERSION = 'v2.0.0';
export const LARE_V2_FROZEN = true;
export const LARE_V2_FROZEN_DATE = '2026-02-24';

// ═══════════════════════════════════════════════════════════════
// COMPONENT WEIGHTS (sum = 1.0)
// ═══════════════════════════════════════════════════════════════

export const LARE_V2_WEIGHTS = {
  market: 0.30,   // Market liquidity indicators
  flow: 0.25,     // DEX/CEX flow imbalance
  bridge: 0.20,   // L1↔L2 capital migration
  stables: 0.25,  // Stablecoin supply expansion/contraction
} as const;

// ═══════════════════════════════════════════════════════════════
// REGIME THRESHOLDS
// ═══════════════════════════════════════════════════════════════

export const LARE_V2_REGIMES = {
  RISK_ON_ALTS: 65,       // Score >= 65: aggressive alt exposure OK
  MODERATE_RISK_ON: 55,   // Score >= 55: moderate risk
  NEUTRAL_LOW: 45,        // Score >= 45: neutral/cautious
  MODERATE_RISK_OFF: 35,  // Score >= 35: reduce exposure
  // Score < 35: RISK_OFF
} as const;

// ═══════════════════════════════════════════════════════════════
// GATE: RISK CAP BY REGIME
// ═══════════════════════════════════════════════════════════════

export const LARE_V2_RISK_CAP = {
  RISK_ON_ALTS: 0.30,       // Max 30% alt exposure
  MODERATE_RISK_ON: 0.22,   // Max 22%
  NEUTRAL: 0.14,            // Max 14%
  MODERATE_RISK_OFF: 0.08,  // Max 8%
  RISK_OFF: 0.03,           // Max 3%
} as const;

// ═══════════════════════════════════════════════════════════════
// CONFIDENCE THRESHOLDS
// ═══════════════════════════════════════════════════════════════

export const LARE_V2_CONFIDENCE = {
  MIN_FOR_AGGRESSIVE: 0.35,  // Minimum confidence for aggressive risk
  MIN_FOR_POSITIONS: 0.12,   // Below this, block new positions
  PENALTY_ONE_MISSING: 0.85, // Multiply confidence if 1 component missing
  PENALTY_TWO_MISSING: 0.65, // Multiply confidence if 2+ components missing
} as const;

// Type exports
export type LareV2Regime =
  | 'RISK_ON_ALTS'
  | 'MODERATE_RISK_ON'
  | 'NEUTRAL'
  | 'MODERATE_RISK_OFF'
  | 'RISK_OFF';

export type LareV2Window = '24h' | '7d';

console.log('[OnChain V2] LiquidityScore v2 contracts loaded');
