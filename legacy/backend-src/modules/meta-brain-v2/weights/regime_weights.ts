/**
 * META BRAIN V2 — REGIME WEIGHTS CONFIG
 * =======================================
 *
 * Single config for base weights + regime multipliers.
 * Easy to extend for a 5th module (e.g. TechAnalysis).
 *
 * Effective weight:
 *   w_i = base_i × regimeMult_i × health_i × drift_i
 *   w'_i = w_i / Σ(w_j) for all aligned j
 */

export type MetaRegime = 'TREND' | 'RANGE' | 'RISK_OFF' | 'TRANSITION';

/** Base weights per module (sums to 1.0) */
export const BASE_WEIGHTS: Record<string, number> = {
  fractal:   0.25,
  exchange:  0.35,
  onchain:   0.25,
  sentiment: 0.15,
};

/** Regime multipliers — how each regime reshapes the weights */
export const REGIME_MULT: Record<MetaRegime, Record<string, number>> = {
  TREND:      { fractal: 1.20, exchange: 1.15, onchain: 0.90, sentiment: 0.85 },
  RANGE:      { fractal: 0.85, exchange: 0.80, onchain: 1.10, sentiment: 1.05 },
  RISK_OFF:   { fractal: 0.80, exchange: 0.85, onchain: 1.20, sentiment: 1.25 },
  TRANSITION: { fractal: 0.95, exchange: 0.95, onchain: 1.05, sentiment: 1.05 },
};

/** Health → weight multiplier */
export const HEALTH_MULT: Record<string, number> = {
  OK:   1.0,
  WARN: 0.7,
  FAIL: 0.0,
};

/** Default regime when detection fails */
export const DEFAULT_REGIME: MetaRegime = 'TRANSITION';
