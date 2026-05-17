/**
 * PSI (Population Stability Index) Utilities
 * ============================================
 * 
 * BLOCK 10.1: Feature Drift Monitor utilities.
 * 
 * PSI measures distribution shift between baseline (training) and live data.
 * 
 * Interpretation:
 *   PSI < 0.1  → Stable
 *   0.1-0.25  → Moderate drift
 *   > 0.25    → Severe drift
 */

export type HistBin = { lo: number; hi: number; p: number };

const EPS = 1e-6;

export function clamp01(x: number): number {
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

/**
 * Build histogram from values using fixed bin edges
 */
export function buildHistogram(values: number[], bins: { lo: number; hi: number }[]): HistBin[] {
  const counts = new Array(bins.length).fill(0);
  
  for (const v of values) {
    let idx = -1;
    for (let i = 0; i < bins.length; i++) {
      const { lo, hi } = bins[i];
      if (v >= lo && v < hi) { 
        idx = i; 
        break; 
      }
    }
    // Right-closed edge for last bin
    if (idx === -1 && bins.length > 0) {
      const last = bins[bins.length - 1];
      if (v >= last.lo && v <= last.hi) {
        idx = bins.length - 1;
      }
    }
    if (idx !== -1) {
      counts[idx] += 1;
    }
  }
  
  const n = values.length || 1;
  return bins.map((b, i) => ({ lo: b.lo, hi: b.hi, p: counts[i] / n }));
}

/**
 * Compute PSI between expected (baseline) and actual (live) distributions
 */
export function computePSI(expected: HistBin[], actual: HistBin[]): number {
  if (expected.length !== actual.length) {
    throw new Error('PSI bins length mismatch');
  }
  
  let psi = 0;
  for (let i = 0; i < expected.length; i++) {
    const e = Math.max(expected[i].p, EPS);
    const a = Math.max(actual[i].p, EPS);
    psi += (a - e) * Math.log(a / e);
  }
  
  return Math.abs(psi); // PSI is always positive
}

/**
 * Convert PSI to drift status
 */
export function driftStatusFromScore(score: number): 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL' {
  if (score < 0.15) return 'OK';
  if (score < 0.30) return 'WARN';
  if (score < 0.50) return 'DEGRADED';
  return 'CRITICAL';
}

/**
 * Normalize PSI to 0-1 scale (soft cap at 0.5)
 */
export function psiToUnit(psi: number): number {
  return clamp01(psi / 0.5);
}

/**
 * Create bins from percentiles (for training snapshot)
 */
export function createBinsFromValues(values: number[], numBins: number = 10): HistBin[] {
  if (values.length === 0) return [];
  
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  
  // Use percentiles for bin edges
  const edges: number[] = [];
  for (let i = 0; i <= numBins; i++) {
    const pct = i / numBins;
    const idx = Math.min(Math.floor(pct * n), n - 1);
    edges.push(sorted[idx]);
  }
  
  // Create bins
  const bins: HistBin[] = [];
  for (let i = 0; i < numBins; i++) {
    const lo = edges[i];
    const hi = edges[i + 1];
    // Count values in this bin
    const count = values.filter(v => v >= lo && (i === numBins - 1 ? v <= hi : v < hi)).length;
    bins.push({ lo, hi, p: count / n });
  }
  
  return bins;
}

/**
 * Compute basic statistics for feature
 */
export function computeFeatureStats(values: number[]): { mean: number; std: number; min: number; max: number; n: number } {
  if (values.length === 0) {
    return { mean: 0, std: 0, min: 0, max: 0, n: 0 };
  }
  
  const n = values.length;
  const mean = values.reduce((a, b) => a + b, 0) / n;
  const variance = values.reduce((a, x) => a + (x - mean) ** 2, 0) / n;
  const std = Math.sqrt(variance);
  const min = Math.min(...values);
  const max = Math.max(...values);
  
  return { mean, std, min, max, n };
}

console.log('[Sentiment-ML] PSI Utils loaded (BLOCK 10.1)');
