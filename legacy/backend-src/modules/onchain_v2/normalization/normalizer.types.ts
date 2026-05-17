/**
 * OnChain V2 — Normalization Types
 * ==================================
 * 
 * BLOCK 6: Universal signal contract
 * All modules must output this format for composition.
 */

export type SignalDirection = -1 | 0 | 1;

export interface NormalizedSignal {
  key: string;                // e.g. "market", "flow", "bridge", "stables"
  score: number;              // 0..100 (50 = neutral)
  direction: SignalDirection; // -1 = bearish, 0 = neutral, +1 = bullish
  strength: number;           // 0..1 (magnitude of signal)
  confidence: number;         // 0..1 (data quality)
  drivers: string[];          // human-readable explanations
  flags: string[];            // warnings/diagnostics
  raw?: Record<string, any>;  // original data for debugging
}

export interface NormalizeOptions {
  deadzone?: number;          // default 0.05 — threshold for direction
  scale?: number;             // override default scale for tanh
}

export interface NormalizationConfig {
  market: { scale: number };
  flow: { scale: number };
  bridge: { scale: number };
  stables: { scale: number };
}

// Default scales (tuned for production)
export const DEFAULT_SCALES: NormalizationConfig = {
  market: { scale: 15 },        // market score delta from 50
  flow: { scale: 20 },          // flow imbalance percent
  bridge: { scale: 25_000_000 }, // bridge USD 24h
  stables: { scale: 50_000_000 }, // stables USD 24h
};

console.log('[OnChain V2] Normalization types loaded');
