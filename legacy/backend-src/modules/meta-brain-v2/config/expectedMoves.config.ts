/**
 * META BRAIN V2 — EXPECTED MOVES CONFIG
 * ========================================
 *
 * Base amplitude of typical price move per module per horizon.
 * These are conservative estimates that can be calibrated later
 * by the ML dataset builder based on actual returns.
 *
 * Units: decimal (0.03 = 3%)
 */

export type HorizonKey = '1d' | '7d' | '30d';

// Base expected move per module per horizon
export const EXPECTED_MOVE: Record<string, Record<HorizonKey, number>> = {
  fractal:    { '1d': 0.005, '7d': 0.025, '30d': 0.08  },
  exchange:   { '1d': 0.006, '7d': 0.03,  '30d': 0.06  },
  onchain:    { '1d': 0.003, '7d': 0.02,  '30d': 0.05  },
  sentiment:  { '1d': 0.008, '7d': 0.02,  '30d': 0.04  },
  prediction: { '1d': 0.006, '7d': 0.025, '30d': 0.055 },
  tech:       { '1d': 0.0,   '7d': 0.0,   '30d': 0.0   },
};

// Safety clamp to prevent wild targets
export const MAX_MOVE: Record<HorizonKey, number> = {
  '1d': 0.05,
  '7d': 0.12,
  '30d': 0.25,
};

export function horizonKeyFromDays(days: number): HorizonKey {
  if (days <= 1) return '1d';
  if (days <= 7) return '7d';
  return '30d';
}
