/**
 * OnChain V2 — Analytics Utils
 * =============================
 * 
 * Bias and direction calculations for structural forecast.
 */

import { OnchainPoint } from './types';

function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

/**
 * Confidence-weighted average score
 */
export function weightedAvgScore(points: OnchainPoint[]): number {
  if (!points.length) return 0;
  let wSum = 0;
  let sSum = 0;
  for (const p of points) {
    const w = clamp01(p.confidence);
    wSum += w;
    sSum += clamp01(p.score) * w;
  }
  if (wSum <= 1e-9) return 0;
  return clamp01(sSum / wSum);
}

/**
 * Simple average score
 */
export function simpleAvgScore(points: OnchainPoint[]): number {
  if (!points.length) return 0;
  let sum = 0;
  for (const p of points) sum += clamp01(p.score);
  return clamp01(sum / points.length);
}

/**
 * Direction using slope of last N points
 * Return: -1..+1 (normalized)
 */
export function directionSlope(points: OnchainPoint[], n = 8): number {
  if (points.length < 2) return 0;
  const tail = points.slice(Math.max(0, points.length - n));
  if (tail.length < 2) return 0;
  const first = clamp01(tail[0].score);
  const last = clamp01(tail[tail.length - 1].score);
  const slope = (last - first) / Math.max(1, tail.length - 1);
  return Math.max(-1, Math.min(1, slope * 10));
}

/**
 * Bias label from score
 */
export function biasLabel(score: number): 'Accumulating' | 'Neutral' | 'Distributing' {
  if (score >= 0.62) return 'Accumulating';
  if (score <= 0.38) return 'Distributing';
  return 'Neutral';
}

/**
 * Arrow direction from slope
 */
export function arrowFromSlope(s: number): 'UP' | 'DOWN' | 'FLAT' {
  if (s > 0.12) return 'UP';
  if (s < -0.12) return 'DOWN';
  return 'FLAT';
}

/**
 * Pick points from last N days
 */
export function pickLastDays(points: OnchainPoint[], days: number): OnchainPoint[] {
  if (!points.length) return [];
  const ms = days * 24 * 60 * 60 * 1000;
  const lastT = points[points.length - 1].t;
  const cutoff = lastT - ms;
  return points.filter((p) => p.t >= cutoff);
}

/**
 * Format guardrail state for display
 */
export function formatGuardrailState(state: string): { label: string; color: string } {
  switch (state) {
    case 'HEALTHY':
      return { label: 'Healthy', color: 'text-emerald-600 bg-emerald-50' };
    case 'WARN':
      return { label: 'Warning', color: 'text-amber-600 bg-amber-50' };
    case 'DEGRADED':
      return { label: 'Degraded', color: 'text-orange-600 bg-orange-50' };
    case 'CRITICAL':
      return { label: 'Critical', color: 'text-red-600 bg-red-50' };
    case 'FROZEN':
      return { label: 'Frozen', color: 'text-slate-600 bg-slate-100' };
    default:
      return { label: state, color: 'text-slate-600 bg-slate-50' };
  }
}

/**
 * Format confidence as percentage
 */
export function formatConfidence(conf: number): string {
  return `${Math.round(conf * 100)}%`;
}

/**
 * Format PSI value
 */
export function formatPsi(psi: number): string {
  return psi.toFixed(3);
}
