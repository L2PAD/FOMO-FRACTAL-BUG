/**
 * META BRAIN V2 — SIGNAL CONTRACT
 * ================================
 * 
 * Unified signal format for all modules.
 * Every provider MUST return this shape.
 * 
 * Key fields for Time Alignment:
 *   asOfTs   — when the signal was computed (provider sets this)
 *   ttlMs    — how long the signal is considered fresh
 *   sourceId — runId / snapshotId for traceability
 *   anchorTs — set ONLY by alignment layer, never by provider
 * 
 * @sealed v1.0
 */

export type Direction = 'LONG' | 'SHORT' | 'NEUTRAL';
export type Horizon = '1D' | '7D' | '30D';
export type SignalHealth = 'OK' | 'WARN' | 'FAIL';
export type PriceBasis = 'close' | 'open' | 'vwap' | 'mid';

/**
 * Raw signal from a provider (before alignment).
 * Provider sets asOfTs, ttlMs, sourceId.
 * Provider NEVER sets anchorTs.
 */
export interface RawMetaSignal {
  module: string;
  asset: string;
  horizon: Horizon;

  // Directional
  direction: Direction;
  score: number;           // [-1..+1]
  confidence: number;      // [0..1]

  // Optional enrichment
  targetPrice?: number;
  expectedMovePct?: number;
  band?: { p25: number; p50: number; p75: number };

  // Time anchors (provider fills these)
  asOfTs: number;          // when signal was computed
  ttlMs: number;           // freshness window in ms
  sourceId: string;        // runId / snapshotId / batchId

  // Basis
  basis: PriceBasis;

  // Health
  health: SignalHealth;
  drift?: number;          // 0..1

  // Debug
  featuresHash?: string;
  reasons: string[];
}

/**
 * Aligned signal (after alignment layer adds anchorTs).
 */
export interface AlignedMetaSignal extends RawMetaSignal {
  anchorTs: number;        // set ONLY by alignment layer
}

/**
 * Dropped signal with reason.
 */
export interface DroppedSignal {
  module: string;
  reason: 'STALE' | 'SKEW' | 'TIMEOUT' | 'ERROR' | 'NO_DATA';
  asOfTs?: number;
  ttlMs?: number;
  detail?: string;
}

/**
 * Alignment result.
 */
export interface AlignmentResult {
  anchorTs: number;
  coverage: {
    total: number;
    aligned: number;
    dropped: number;
  };
  aligned: AlignedMetaSignal[];
  dropped: DroppedSignal[];
}
