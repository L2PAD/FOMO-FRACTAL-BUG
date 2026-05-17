/**
 * META BRAIN V2 — META FORECAST SERVICE
 * ========================================
 *
 * Computes consensus forecast from weighted module signals.
 *
 * Formula:
 *   R_meta = Σ(weight_i × dirScore_i × confidence_i × expectedMove_i) / Σ(weight_i × expectedMove_i)
 *   target = currentPrice × (1 + R_meta)
 *
 * Returns forecast for all 3 horizons (1d, 7d, 30d) in a single call.
 * The frontend uses these targets to draw the forecast line on the chart.
 */

import {
  EXPECTED_MOVE,
  MAX_MOVE,
  HorizonKey,
  horizonKeyFromDays,
} from '../config/expectedMoves.config.js';

export interface HorizonForecast {
  horizon: HorizonKey;
  horizonDays: number;
  expReturn: number;
  target: number;
  confidence: number;
  coverage: number;
}

export interface MetaForecastBundle {
  asset: string;
  currentPrice: number;
  asOf: string;
  items: Record<HorizonKey, HorizonForecast>;
}

interface ForecastSignal {
  module: string;
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  confidence: number;
  weight: number;
}

interface ForecastContext {
  asset: string;
  currentPrice: number;
  coverageRatio: number;
  signals: ForecastSignal[];
}

function dirScore(d: string): number {
  if (d === 'LONG') return 1;
  if (d === 'SHORT') return -1;
  return 0;
}

function clamp(x: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, x));
}

function computeHorizonForecast(
  ctx: ForecastContext,
  hKey: HorizonKey,
  hDays: number
): HorizonForecast {
  if (!ctx.signals.length) {
    return {
      horizon: hKey,
      horizonDays: hDays,
      expReturn: 0,
      target: ctx.currentPrice,
      confidence: 0,
      coverage: ctx.coverageRatio,
    };
  }

  let num = 0;
  let den = 0;
  let confNum = 0;
  let confDen = 0;

  for (const s of ctx.signals) {
    const move = EXPECTED_MOVE[s.module]?.[hKey] ?? 0.01;
    const dir = dirScore(s.direction);

    num += s.weight * dir * s.confidence * move;
    den += Math.abs(s.weight) * move;

    confNum += s.weight * s.confidence;
    confDen += s.weight;
  }

  const raw = den > 0 ? num / den : 0;
  const expReturn = clamp(raw, -MAX_MOVE[hKey], MAX_MOVE[hKey]);

  const baseConf = confDen > 0 ? clamp(confNum / confDen, 0, 1) : 0;
  const confidence = clamp(baseConf * ctx.coverageRatio, 0, 1);

  return {
    horizon: hKey,
    horizonDays: hDays,
    expReturn,
    target: Math.round(ctx.currentPrice * (1 + expReturn) * 100) / 100,
    confidence,
    coverage: ctx.coverageRatio,
  };
}

/**
 * Build forecast targets for all 3 horizons.
 */
export function buildMetaForecast(ctx: ForecastContext): MetaForecastBundle {
  const horizons: Array<{ key: HorizonKey; days: number }> = [
    { key: '1d', days: 1 },
    { key: '7d', days: 7 },
    { key: '30d', days: 30 },
  ];

  const items = {} as MetaForecastBundle['items'];
  for (const h of horizons) {
    items[h.key] = computeHorizonForecast(ctx, h.key, h.days);
  }

  return {
    asset: ctx.asset,
    currentPrice: ctx.currentPrice,
    asOf: new Date().toISOString().split('T')[0],
    items,
  };
}

/**
 * Generate a smooth forecast series for chart rendering.
 * Creates intermediate points between NOW and target using ease-out curve.
 *
 * Returns array of {t: "YYYY-MM-DD", v: price} compatible with chart engine.
 */
export function generateForecastSeries(
  currentPrice: number,
  target: number,
  horizonDays: number,
  startDate: Date = new Date()
): Array<{ t: string; v: number }> {
  const series: Array<{ t: string; v: number }> = [];

  // Start point (NOW)
  series.push({
    t: startDate.toISOString().split('T')[0],
    v: Math.round(currentPrice * 100) / 100,
  });

  // Generate daily points with ease-out curve
  const totalReturn = target - currentPrice;

  for (let day = 1; day <= horizonDays; day++) {
    const d = new Date(startDate);
    d.setDate(d.getDate() + day);

    const progress = day / horizonDays;
    // Ease-out: fast start, slow finish (more natural price movement)
    const easing = 1 - Math.pow(1 - progress, 2.5);
    const price = currentPrice + totalReturn * easing;

    series.push({
      t: d.toISOString().split('T')[0],
      v: Math.round(price * 100) / 100,
    });
  }

  return series;
}
