/**
 * Alert Performance
 *
 * Measures effectiveness of the alert system.
 * Closes the loop: alert → action → outcome.
 */

import type { AlertPerformance } from '../types/digest.types.js';

interface AlertData {
  type: string;
  tier: string;
  asset: string;
  action: string;
  edge: number;
  timestamp: string;
}

interface ReviewData {
  asset: string;
  correctness: { correctness: string };
}

class AlertPerformanceService {
  analyze(alerts: AlertData[], reviews: ReviewData[]): AlertPerformance {
    const triggered = alerts.length;
    const actionable = alerts.filter(a => a.tier === 'HIGH' || a.tier === 'MEDIUM').length;

    // Match alerts to review outcomes
    const reviewByAsset = new Map<string, boolean>();
    for (const r of reviews) {
      reviewByAsset.set(r.asset, r.correctness?.correctness === 'CORRECT');
    }

    let correctAlerts = 0;
    let falsePositives = 0;
    for (const a of alerts) {
      if (a.type === 'ENTRY_SIGNAL') {
        const outcome = reviewByAsset.get(a.asset);
        if (outcome === true) correctAlerts++;
        else if (outcome === false) falsePositives++;
      }
    }

    const entryAlerts = alerts.filter(a => a.type === 'ENTRY_SIGNAL').length;

    return {
      alertsTriggered: triggered,
      actionableAlerts: actionable,
      correctAlerts,
      falsePositives,
      alertAccuracy: entryAlerts > 0 ? Math.round((correctAlerts / entryAlerts) * 100) : 0,
    };
  }
}

export const alertPerformanceService = new AlertPerformanceService();
