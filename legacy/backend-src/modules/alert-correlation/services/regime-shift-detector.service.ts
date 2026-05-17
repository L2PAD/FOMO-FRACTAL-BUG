/**
 * Regime Shift Detector Service
 *
 * Determines if a cluster represents a regime shift vs a local event.
 * Uses: factor overlap, timing density, signal consistency, breadth.
 */

import type { AlertCluster, FactorOverlapResult, RawAlertRef } from '../types/correlation.types.js';

export interface RegimeShiftResult {
  detected: boolean;
  direction: 'RISK_ON' | 'RISK_OFF' | 'NEUTRAL';
  confidence: number;
  breadth: number;
  consistency: number;
  timingDensity: number;
}

class RegimeShiftDetectorService {
  detect(cluster: AlertCluster, overlap: FactorOverlapResult): RegimeShiftResult {
    const alerts = cluster.alerts;
    if (alerts.length < 3) {
      return { detected: false, direction: 'NEUTRAL', confidence: 0, breadth: 0, consistency: 0, timingDensity: 0 };
    }

    // 1. Breadth: how many unique assets/markets
    const uniqueAssets = new Set(alerts.map(a => a.asset).filter(Boolean));
    const uniqueMarkets = new Set(alerts.map(a => a.marketId));
    const breadth = Math.min(1, uniqueAssets.size / 5); // 5+ assets = max breadth

    // 2. Consistency: do signals agree on direction?
    let bullish = 0;
    let bearish = 0;
    for (const a of alerts) {
      if (a.type === 'ENTRY_SIGNAL') bullish++;
      else if (a.type === 'EXIT_SIGNAL' || a.type === 'TRIM_SIGNAL' || a.type === 'RISK_ALERT') bearish++;
    }
    const total = bullish + bearish;
    const consistency = total > 0 ? Math.max(bullish, bearish) / total : 0;

    // 3. Timing density: alerts per minute
    const windowMs = Math.max(1, cluster.windowEnd - cluster.windowStart);
    const windowMin = windowMs / 60000;
    const timingDensity = Math.min(1, alerts.length / Math.max(1, windowMin * 2));

    // 4. Factor overlap contribution
    const overlapContrib = Math.min(1, overlap.overlapScore * 3);

    // 5. No strong contradictions
    const hasContradictions = (bullish > 0 && bearish > 0);

    // Combined confidence
    const rawConfidence =
      breadth * 0.30 +
      consistency * 0.30 +
      overlapContrib * 0.20 +
      timingDensity * 0.20;

    const confidence = hasContradictions ? rawConfidence * 0.6 : rawConfidence;
    const detected = confidence > 0.45 && breadth > 0.3 && consistency > 0.65;

    const direction = bullish > bearish ? 'RISK_ON' : bearish > bullish ? 'RISK_OFF' : 'NEUTRAL';

    return {
      detected,
      direction: detected ? direction : 'NEUTRAL',
      confidence: Math.round(confidence * 100) / 100,
      breadth: Math.round(breadth * 100) / 100,
      consistency: Math.round(consistency * 100) / 100,
      timingDensity: Math.round(timingDensity * 100) / 100,
    };
  }
}

export const regimeShiftDetectorService = new RegimeShiftDetectorService();
