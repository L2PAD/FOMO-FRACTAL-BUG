/**
 * OnChain V2 — Normalization Math
 * =================================
 * 
 * BLOCK 6: Universal math functions for signal normalization.
 * Uses tanh for smooth bounded scaling.
 */

/**
 * Clamp value to [0, 1]
 */
export function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

/**
 * Clamp value to [0, 100]
 */
export function clampScore(x: number): number {
  return Math.max(0, Math.min(100, x));
}

/**
 * Tanh normalization: maps any value to [-1, 1] smoothly
 * @param x - input value
 * @param scale - sensitivity (larger = less sensitive)
 */
export function tanhNorm(x: number, scale: number): number {
  if (!Number.isFinite(x) || scale <= 0) return 0;
  return Math.tanh(x / scale);
}

/**
 * Convert normalized [-1, 1] to score [0, 100]
 * -1 → 0, 0 → 50, +1 → 100
 */
export function toScore(norm: number): number {
  return clampScore(50 + norm * 50);
}

/**
 * Determine direction from normalized value
 * @param norm - normalized value [-1, 1]
 * @param deadzone - threshold for neutral (default 0.05)
 */
export function toDirection(norm: number, deadzone = 0.05): -1 | 0 | 1 {
  if (norm > deadzone) return 1;
  if (norm < -deadzone) return -1;
  return 0;
}

/**
 * Compute strength (magnitude) from normalized value
 */
export function toStrength(norm: number): number {
  return clamp01(Math.abs(norm));
}

/**
 * Weighted average of multiple values
 */
export function weightedAvg(values: number[], weights: number[]): number {
  if (values.length !== weights.length || values.length === 0) return 0;
  
  let sum = 0;
  let weightSum = 0;
  
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    const w = weights[i];
    if (Number.isFinite(v) && Number.isFinite(w) && w > 0) {
      sum += v * w;
      weightSum += w;
    }
  }
  
  return weightSum > 0 ? sum / weightSum : 0;
}

console.log('[OnChain V2] Normalization math loaded');
