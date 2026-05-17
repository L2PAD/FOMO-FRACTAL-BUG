/**
 * Data Quality Flags — Unified Enum
 * ===================================
 * 
 * PHASE 2.2: Single source of truth for all data quality flags
 * across ingestion, pricing, pool scoring, and signal layers.
 */

export type FlagSeverity = 'INFO' | 'WARN' | 'CRITICAL';

export interface DataQualityFlag {
  code: string;
  severity: FlagSeverity;
  detail?: string;
}

// ═══════════════════════════════════════════════════════════════
// FLAG CODES (exhaustive enum)
// ═══════════════════════════════════════════════════════════════

export const FLAG_CODES = {
  // Pricing
  NO_PRICE: 'NO_PRICE',                   // No price source available
  PRICE_STALE: 'PRICE_STALE',             // Price older than threshold
  ORACLE_FALLBACK: 'ORACLE_FALLBACK',     // Fell back from primary to secondary source
  LOW_PRICED_SHARE: 'LOW_PRICED_SHARE',   // <70% of flows have USD pricing

  // Pool
  LOW_TVL: 'LOW_TVL',                     // TVL below activation threshold
  POOL_DEGRADED: 'POOL_DEGRADED',         // Pool status = DEGRADED
  POOL_DISABLED: 'POOL_DISABLED',         // Pool status = DISABLED

  // Evidence
  LOW_TRADES: 'LOW_TRADES',               // Too few trades for reliable signal
  LOW_EVENTS: 'LOW_EVENTS',               // Too few on-chain events
  SHORT_WINDOW: 'SHORT_WINDOW',           // Span too short for window
  LOW_CONFIDENCE: 'LOW_CONFIDENCE',       // Confidence below 0.25
  ONE_SIDED_FLOW: 'ONE_SIDED_FLOW',       // >85% dominance from single source

  // Ingestion
  INGESTION_LAG: 'INGESTION_LAG',         // Ingestion is behind by >N blocks
  MISSING_META: 'MISSING_META',           // Token/pool metadata missing
  SYMBOL_UNKNOWN: 'SYMBOL_UNKNOWN',       // Symbol not resolved

  // Data integrity
  STALE: 'STALE',                         // Data older than expected refresh
  HIGH_DEVIATION: 'HIGH_DEVIATION',       // Unusual deviation in values
  CALC_ERROR: 'CALC_ERROR',              // Computation produced NaN/Inf

  // System
  DATA_MISSING: 'DATA_MISSING',           // No data for requested scope
} as const;

export type FlagCode = typeof FLAG_CODES[keyof typeof FLAG_CODES];

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

/**
 * Create a flag with proper typing
 */
export function createFlag(code: FlagCode, severity: FlagSeverity, detail?: string): DataQualityFlag {
  return { code, severity, ...(detail ? { detail } : {}) };
}

/**
 * Check if any flag in array is of given severity
 */
export function hasFlag(flags: DataQualityFlag[], code: FlagCode): boolean {
  return flags.some(f => f.code === code);
}

export function hasCriticalFlags(flags: DataQualityFlag[]): boolean {
  return flags.some(f => f.severity === 'CRITICAL');
}

export function hasWarnFlags(flags: DataQualityFlag[]): boolean {
  return flags.some(f => f.severity === 'WARN');
}

/**
 * Determine if signal should be dimmed based on flags
 */
export function shouldDim(flags: DataQualityFlag[], confidence: number): boolean {
  if (confidence < 0.25) return true;
  if (hasCriticalFlags(flags)) return true;
  const warnCount = flags.filter(f => f.severity === 'WARN').length;
  return warnCount >= 3;
}

/**
 * Determine if signal passes strong-only filter
 */
export function passesStrongOnly(confidence: number, flags: DataQualityFlag[]): boolean {
  return confidence >= 0.55 && !hasCriticalFlags(flags);
}

console.log('[DataQuality] Flags module loaded');
