/**
 * LiquidityScore Engine — Contracts
 * ==================================
 * 
 * 🔒 FROZEN v1.0.0 — 2026-02-23
 * 
 * LARE (Liquidity & Alt Rotation Engine)
 * Alt-first Liquidity & Regime Classification
 * 
 * ⚠️ DO NOT MODIFY formulas, weights, thresholds without version bump
 * 
 * Output types for LiquidityScore (0-100), not price forecasts.
 */

// ═══════════════════════════════════════════════════════════════
// VERSION & FREEZE STATUS
// ═══════════════════════════════════════════════════════════════

export const LARE_VERSION = 'v1.0.0';
export const LARE_FROZEN = true;
export const LARE_FROZEN_DATE = '2026-02-23';

// ═══════════════════════════════════════════════════════════════
// ENUMS
// ═══════════════════════════════════════════════════════════════

export enum LiquidityRegime {
  RISK_ON_ALTS = 'RISK_ON_ALTS',
  RISK_OFF = 'RISK_OFF',
  STABLE_INFLOW = 'STABLE_INFLOW',
  BTC_FLIGHT = 'BTC_FLIGHT',
  NEUTRAL = 'NEUTRAL',
}

export enum FlagSeverity {
  INFO = 'INFO',
  WARN = 'WARN',
  DEGRADED = 'DEGRADED',
  CRITICAL = 'CRITICAL',
}

export enum GuardrailAction {
  NONE = 'NONE',
  DOWNWEIGHT = 'DOWNWEIGHT',
  FORCE_SAFE = 'FORCE_SAFE',
  BLOCK_OUTPUT = 'BLOCK_OUTPUT',
}

// ═══════════════════════════════════════════════════════════════
// FLAG TYPES
// ═══════════════════════════════════════════════════════════════

export interface LiquidityFlag {
  code: string;
  severity: FlagSeverity;
  message: string;
}

export const FLAG_CODES = {
  NO_DATA: 'NO_DATA',
  STALE_MARKET_SERIES: 'STALE_MARKET_SERIES',
  LOW_SAMPLES_30D: 'LOW_SAMPLES_30D',
  API_PARTIAL: 'API_PARTIAL',
  OUTLIER_SPIKE: 'OUTLIER_SPIKE',
  // Phase 2.2 Flow flags
  DEX_DATA_STALE: 'DEX_DATA_STALE',
  NO_DEX_DATA: 'NO_DEX_DATA',
  EXCHANGE_LABELS_MISSING: 'EXCHANGE_LABELS_MISSING',
  LOW_FLOW_SAMPLES: 'LOW_FLOW_SAMPLES',
} as const;

// ═══════════════════════════════════════════════════════════════
// 🔒 FROZEN THRESHOLDS — DO NOT MODIFY
// ═══════════════════════════════════════════════════════════════

export const LIQUIDITY_THRESHOLDS = {
  // Regime detection thresholds (raw % change)
  ALT_UP_PCT: 2,           // +2% alt cap = "rising"
  ALT_DOWN_PCT: -2,        // -2% alt cap = "falling"
  STABLE_DOM_UP: 0.3,      // +0.3pp stable dominance = "rising"
  STABLE_SUPPLY_UP: 1,     // +1% stable supply = "rising"
  BTC_DOM_UP: 0.3,         // +0.3pp BTC dom = "rising"
  ETHBTC_UP: 1,            // +1% ETH/BTC = "rising"
  ETHBTC_DOWN: -1,         // -1% ETH/BTC = "falling"
  
  // 🔒 Score weights (sum = 1.0) — FROZEN v1.0.0
  WEIGHT_ALT_MOM: 0.30,      // Alt cap momentum
  WEIGHT_ETHBTC: 0.20,       // ETH/BTC impulse
  WEIGHT_STABLE: 0.20,       // Stable dominance (inverted)
  WEIGHT_BTC: 0.15,          // BTC dominance (inverted)
  WEIGHT_DEX_PRESSURE: 0.10, // DEX buy/sell pressure
  WEIGHT_EXCHANGE: 0.05,     // CEX inflow/outflow
  
  // Confidence factors
  SAMPLE_COUNT_TARGET: 200,
  STALE_THRESHOLD_MS: 25 * 60 * 1000,  // 25 minutes
  VERY_STALE_MS: 60 * 60 * 1000,        // 1 hour
  
  // Flow data thresholds
  DEX_MIN_SWAPS: 10,        // Minimum swaps for valid signal
  EXCHANGE_MIN_TRANSFERS: 5, // Minimum transfers for valid signal
  
  // Robust normalization
  SIGMOID_K: 2,
  OUTLIER_Z_THRESHOLD: 6,
} as const;

// ═══════════════════════════════════════════════════════════════
// INPUT TYPES
// ═══════════════════════════════════════════════════════════════

export interface MarketSeriesInput {
  now: number;
  delta24h: number | null;
  delta7d: number | null;
}

export interface LiquidityInputs {
  pureAltCap: MarketSeriesInput;
  stableSupply: MarketSeriesInput;
  stableDom: MarketSeriesInput;
  btcDom: MarketSeriesInput;
  ethbtc: MarketSeriesInput;
}

// ═══════════════════════════════════════════════════════════════
// GOVERNANCE
// ═══════════════════════════════════════════════════════════════

export interface LiquidityGovernance {
  guardrailState: 'HEALTHY' | 'WARN' | 'DEGRADED' | 'CRITICAL';
  guardrailAction: GuardrailAction;
  confidenceModifier: number;
  reasons: string[];
}

// ═══════════════════════════════════════════════════════════════
// GATE CONTRACT (Context Layer Output)
// ═══════════════════════════════════════════════════════════════

/**
 * Risk Gate - Context Layer Output
 * 
 * OnChain does NOT provide direction (BUY/SELL).
 * It provides risk context and permission gates.
 */
export interface LiquidityGate {
  allowAggressiveRisk: boolean;  // true only in RISK_ON_ALTS with high confidence
  riskCap: number;               // 0-1, multiplier for position sizing/confidence
  blockNewPositions: boolean;    // true in CRITICAL state
  reason: string;                // Human-readable explanation
}

// ═══════════════════════════════════════════════════════════════
// OUTPUT CONTRACTS
// ═══════════════════════════════════════════════════════════════

export interface LiquidityLatest {
  ok: boolean;
  t: number;
  score: number;           // 0-100
  confidence: number;      // 0-1
  regime: LiquidityRegime;
  drivers: string[];
  flags: LiquidityFlag[];
  inputs?: LiquidityInputs;
  governance: LiquidityGovernance;
  gate: LiquidityGate;     // Context Layer Risk Gate
  version: string;         // API version for freeze tracking
}

export interface LiquiditySeriesPoint {
  t: number;
  score: number;
  confidence: number;
  regime: LiquidityRegime;
  flags: string[];         // Just codes for storage efficiency
  drivers: string[];
}

export interface LiquiditySeries {
  ok: boolean;
  key: string;
  window: string;
  count: number;
  series: LiquiditySeriesPoint[];
}

// ═══════════════════════════════════════════════════════════════
// ENGINE INTERNAL
// ═══════════════════════════════════════════════════════════════

export interface LiquidityFeatures {
  altMom: number;          // 0-1, positive factor
  stableInflow: number;    // 0-1, negative factor (inverted in score)
  btcFlight: number;       // 0-1, negative factor
  ethbtcImpulse: number;   // 0-1, positive factor
  // Phase 2.2 Flow features
  dexPressure: number;     // 0-1, buy pressure positive
  exchangePressure: number; // 0-1, inflow pressure negative (inverted in score)
}

export interface LiquidityEngineResult {
  score: number;
  confidenceBase: number;
  regime: LiquidityRegime;
  drivers: string[];
  flags: LiquidityFlag[];
  features: LiquidityFeatures;
  debug?: {
    rawDeltas: Record<string, number | null>;
    normalizedFeatures: Record<string, number>;
  };
}

console.log('[Liquidity] Contracts loaded');
