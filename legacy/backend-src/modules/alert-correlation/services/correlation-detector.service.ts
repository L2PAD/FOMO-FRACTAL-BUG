/**
 * Correlation Detector Service
 *
 * Determines the type of meta-alert from a cluster.
 * Includes contradictionScore to detect mixed signals.
 *
 * Types: SECTOR_ROTATION, MULTI_MARKET_CONFIRMATION, UNLOCK_RISK_CLUSTER,
 *        RISK_ON_SHIFT, RISK_OFF_SHIFT, NARRATIVE_EXHAUSTION, BROAD_OVERHEAT,
 *        CLUSTER_WAKEUP, MIXED_CLUSTER
 */

import type { AlertCluster, MetaAlertType, RawAlertRef, FactorOverlapResult } from '../types/correlation.types.js';

export interface DetectionResult {
  type: MetaAlertType;
  confidence: number;
  contradictionScore: number;
  keyDrivers: string[];
  risks: string[];
}

class CorrelationDetectorService {
  detect(cluster: AlertCluster, overlap: FactorOverlapResult): DetectionResult {
    const alerts = cluster.alerts;
    const contradictionScore = this.computeContradiction(alerts);

    // If contradiction is very high, it's a MIXED_CLUSTER
    if (contradictionScore > 0.6) {
      return {
        type: 'MIXED_CLUSTER',
        confidence: 0.5,
        contradictionScore,
        keyDrivers: ['Mixed signals detected within cluster'],
        risks: ['Contradictory alerts — exercise caution'],
      };
    }

    // Try each detection rule in order of specificity
    const result =
      this.detectUnlockRisk(alerts, overlap) ||
      this.detectNarrativeExhaustion(alerts, overlap) ||
      this.detectBroadOverheat(alerts, overlap) ||
      this.detectSectorRotation(alerts, overlap) ||
      this.detectClusterWakeup(alerts, overlap) ||
      this.detectMultiMarketConfirmation(alerts, overlap) ||
      this.detectRiskShift(alerts, overlap);

    if (!result) {
      return {
        type: 'MIXED_CLUSTER',
        confidence: 0.3,
        contradictionScore,
        keyDrivers: overlap.dominantSharedFactors.slice(0, 3),
        risks: ['Low correlation — cluster may be noise'],
      };
    }

    // Adjust confidence based on contradiction
    result.contradictionScore = contradictionScore;
    if (contradictionScore > 0.3) {
      result.confidence *= (1 - contradictionScore * 0.5);
    }

    return result;
  }

  private computeContradiction(alerts: RawAlertRef[]): number {
    let bullish = 0;
    let bearish = 0;
    let risk = 0;
    let saturated = 0;

    for (const a of alerts) {
      if (a.type === 'ENTRY_SIGNAL') bullish++;
      if (a.type === 'EXIT_SIGNAL' || a.type === 'TRIM_SIGNAL') bearish++;
      if (a.type === 'RISK_ALERT') risk++;
      if (a.social?.lifecycle === 'SATURATED' || (a.social?.saturation ?? 0) > 0.7) saturated++;
    }

    const total = alerts.length;
    if (total < 2) return 0;

    // Contradiction: mix of bullish and bearish/risk signals
    const bullishRatio = bullish / total;
    const bearishRatio = (bearish + risk) / total;

    // High contradiction = both sides present significantly
    const minSide = Math.min(bullishRatio, bearishRatio);
    const contradictionFromDirection = minSide * 2; // 0-1 scale

    // Also factor in saturated narratives mixed with entry signals
    const saturationContradiction = (saturated > 0 && bullish > 0) ? 0.2 : 0;

    return Math.min(1, contradictionFromDirection + saturationContradiction);
  }

  private detectUnlockRisk(alerts: RawAlertRef[], overlap: FactorOverlapResult): DetectionResult | null {
    const riskAlerts = alerts.filter(a => a.type === 'RISK_ALERT' || a.project?.unlockRisk === 'HIGH');
    if (riskAlerts.length < 2) return null;

    return {
      type: 'UNLOCK_RISK_CLUSTER',
      confidence: 0.6 + riskAlerts.length * 0.1,
      contradictionScore: 0,
      keyDrivers: [
        `${riskAlerts.length} projects show elevated unlock pressure`,
        ...overlap.dominantSharedFactors.slice(0, 2),
      ],
      risks: ['Elevated sell pressure risk', 'Avoid late longs in affected names'],
    };
  }

  private detectNarrativeExhaustion(alerts: RawAlertRef[], overlap: FactorOverlapResult): DetectionResult | null {
    const saturated = alerts.filter(a =>
      a.social?.lifecycle === 'SATURATED' || (a.social?.saturation ?? 0) > 0.7
    );
    if (saturated.length < 2) return null;

    return {
      type: 'NARRATIVE_EXHAUSTION',
      confidence: 0.55 + saturated.length * 0.1,
      contradictionScore: 0,
      keyDrivers: [
        `${saturated.length} markets in saturated/late narrative`,
        'Edge compression across cluster',
        ...overlap.dominantSharedFactors.slice(0, 1),
      ],
      risks: ['High echo chamber risk', 'Elevated late-entry risk'],
    };
  }

  private detectBroadOverheat(alerts: RawAlertRef[], overlap: FactorOverlapResult): DetectionResult | null {
    const overheated = alerts.filter(a => {
      const edge = a.edge ?? 0;
      return edge < 0.03 || a.social?.lifecycle === 'SATURATED';
    });
    if (overheated.length < 3) return null;

    return {
      type: 'BROAD_OVERHEAT',
      confidence: 0.5 + overheated.length * 0.08,
      contradictionScore: 0,
      keyDrivers: [
        `${overheated.length} markets showing edge compression`,
        'Broad market overheating detected',
      ],
      risks: ['Position trimming may be warranted', 'Late entries especially risky'],
    };
  }

  private detectSectorRotation(alerts: RawAlertRef[], overlap: FactorOverlapResult): DetectionResult | null {
    const uniqueAssets = new Set(alerts.map(a => a.asset).filter(Boolean));
    const entryOrChange = alerts.filter(a => a.type === 'ENTRY_SIGNAL' || a.type === 'STATE_CHANGE');

    if (uniqueAssets.size < 3 || entryOrChange.length < 3) return null;
    if (overlap.themeOverlap < 0.1) return null;

    const windowMins = Math.round((alerts[alerts.length - 1].timestamp - alerts[0].timestamp) / 60000);

    return {
      type: 'SECTOR_ROTATION',
      confidence: 0.6 + Math.min(0.3, uniqueAssets.size * 0.05),
      contradictionScore: 0,
      keyDrivers: [
        `${uniqueAssets.size} related markets became actionable in ${windowMins}m`,
        'Shared theme alignment detected',
        ...overlap.dominantSharedFactors.slice(0, 2),
      ],
      risks: ['Sector volatility may be elevated', 'Late joiners face higher risk'],
    };
  }

  private detectClusterWakeup(alerts: RawAlertRef[], overlap: FactorOverlapResult): DetectionResult | null {
    const earlyNarrative = alerts.filter(a =>
      a.social?.lifecycle === 'EARLY' || a.social?.lifecycle === 'EXPANDING'
    );
    if (earlyNarrative.length < 2) return null;
    if (overlap.themeOverlap < 0.15) return null;

    return {
      type: 'CLUSTER_WAKEUP',
      confidence: 0.55 + earlyNarrative.length * 0.08,
      contradictionScore: 0,
      keyDrivers: [
        `${earlyNarrative.length} markets in early/expanding narrative phase`,
        'Theme waking up after quiet period',
        ...overlap.dominantSharedFactors.slice(0, 1),
      ],
      risks: ['Early-stage volatility', 'Narrative may not sustain'],
    };
  }

  private detectMultiMarketConfirmation(alerts: RawAlertRef[], overlap: FactorOverlapResult): DetectionResult | null {
    const uniqueMarkets = new Set(alerts.map(a => a.marketId));
    if (uniqueMarkets.size < 2) return null;
    if (overlap.overlapScore < 0.08) return null;

    const entryAlerts = alerts.filter(a => a.type === 'ENTRY_SIGNAL');
    if (entryAlerts.length < 2) return null;

    return {
      type: 'MULTI_MARKET_CONFIRMATION',
      confidence: 0.6 + overlap.overlapScore * 0.5,
      contradictionScore: 0,
      keyDrivers: [
        `${uniqueMarkets.size} markets confirm same thesis`,
        ...overlap.dominantSharedFactors.slice(0, 3),
      ],
      risks: ['Correlated exposure risk'],
    };
  }

  private detectRiskShift(alerts: RawAlertRef[], overlap: FactorOverlapResult): DetectionResult | null {
    let bullishScore = 0;
    let bearishScore = 0;

    for (const a of alerts) {
      const weight = a.priority === 'HIGH' ? 2 : a.priority === 'MEDIUM' ? 1.5 : 1;
      if (a.type === 'ENTRY_SIGNAL') bullishScore += weight;
      if (a.type === 'EXIT_SIGNAL' || a.type === 'TRIM_SIGNAL') bearishScore += weight;
      if (a.type === 'RISK_ALERT') bearishScore += weight * 0.8;
    }

    const total = bullishScore + bearishScore;
    if (total < 3) return null;

    // Need strong directional consistency AND timing density AND overlap
    const timingDensity = alerts.length / Math.max(1, (alerts[alerts.length - 1].timestamp - alerts[0].timestamp) / 60000);
    if (timingDensity < 0.05 && overlap.overlapScore < 0.1) return null;

    const ratio = Math.max(bullishScore, bearishScore) / total;
    if (ratio < 0.7) return null; // Not consistent enough

    const direction = bullishScore > bearishScore ? 'RISK_ON' : 'RISK_OFF';
    const type: MetaAlertType = direction === 'RISK_ON' ? 'RISK_ON_SHIFT' : 'RISK_OFF_SHIFT';

    return {
      type,
      confidence: 0.5 + ratio * 0.3 + overlap.overlapScore * 0.2,
      contradictionScore: 0,
      keyDrivers: [
        `${direction} regime detected`,
        `${alerts.length} consistent directional signals`,
        ...overlap.dominantSharedFactors.slice(0, 1),
      ],
      risks: direction === 'RISK_ON'
        ? ['Euphoria may already be priced in']
        : ['Broad sell pressure may cascade'],
    };
  }
}

export const correlationDetectorService = new CorrelationDetectorService();
