/**
 * Meta Alert Builder Service
 *
 * Builds human-readable meta-alerts with title, summary, drivers, risks.
 */

import type { AlertCluster, FactorOverlapResult, MetaAlert, MetaAlertType } from '../types/correlation.types.js';
import type { DetectionResult } from './correlation-detector.service.js';
import type { RegimeShiftResult } from './regime-shift-detector.service.js';
import type { PriorityResult } from './cluster-priority.service.js';

let metaIdCounter = 0;

const TITLES: Record<MetaAlertType, string> = {
  SECTOR_ROTATION: 'SECTOR ROTATION DETECTED',
  MULTI_MARKET_CONFIRMATION: 'MULTI-MARKET CONFIRMATION',
  UNLOCK_RISK_CLUSTER: 'UNLOCK RISK CLUSTER',
  RISK_ON_SHIFT: 'RISK-ON SHIFT',
  RISK_OFF_SHIFT: 'RISK-OFF SHIFT',
  NARRATIVE_EXHAUSTION: 'NARRATIVE EXHAUSTION',
  BROAD_OVERHEAT: 'BROAD OVERHEAT',
  CLUSTER_WAKEUP: 'CLUSTER WAKEUP',
  MIXED_CLUSTER: 'MIXED SIGNAL CLUSTER',
};

class MetaAlertBuilderService {
  build(
    cluster: AlertCluster,
    overlap: FactorOverlapResult,
    detection: DetectionResult,
    regime: RegimeShiftResult,
    priority: PriorityResult,
    metaInsightGain: number,
  ): MetaAlert {
    const alerts = cluster.alerts;
    const uniqueAssets = [...new Set(alerts.map(a => a.asset).filter(Boolean))];
    const uniqueMarkets = [...new Set(alerts.map(a => a.marketId))];

    const windowMins = Math.round((cluster.windowEnd - cluster.windowStart) / 60000);
    const theme = overlap.dominantSharedFactors
      .filter(f => f.startsWith('theme:'))
      .map(f => f.replace('theme:', ''))
      .join(', ') || 'Related';

    const summary = this.buildSummary(detection.type, uniqueAssets, windowMins, theme, detection);

    // Suppress member alerts if meta-alert is high quality
    const suppressMemberAlerts = priority.priority === 'HIGH' && metaInsightGain > 0.5;

    const dedupKey = `${detection.type}:${overlap.dominantSharedFactors.slice(0, 2).join(',')}:${regime.direction}`;

    return {
      metaAlertId: `meta_${++metaIdCounter}_${Date.now()}`,
      type: detection.type,
      title: TITLES[detection.type] || detection.type,
      summary,
      members: alerts.map(a => a.alertId),
      marketIds: uniqueMarkets,
      assets: uniqueAssets,
      priority: priority.priority,
      confidence: Math.round(detection.confidence * 100) / 100,
      sharedFactors: overlap.dominantSharedFactors,
      keyDrivers: detection.keyDrivers,
      risks: detection.risks,
      contradictionScore: Math.round(detection.contradictionScore * 100) / 100,
      memberDiversityScore: priority.memberDiversityScore,
      metaInsightGain: Math.round(metaInsightGain * 100) / 100,
      suppressMemberAlerts,
      regimeShift: regime.detected ? {
        detected: true,
        direction: regime.direction,
        confidence: regime.confidence,
      } : undefined,
      dedupKey,
      timestamp: Date.now(),
    };
  }

  private buildSummary(
    type: MetaAlertType, assets: string[], windowMins: number, theme: string, detection: DetectionResult,
  ): string {
    switch (type) {
      case 'SECTOR_ROTATION':
        return `${assets.length} ${theme} markets became actionable in ${windowMins}m. Shared bullish alignment and early cluster repricing detected.`;

      case 'MULTI_MARKET_CONFIRMATION':
        return `${assets.length} markets confirm same thesis (${theme}). Signals reinforce each other.`;

      case 'UNLOCK_RISK_CLUSTER':
        return `${assets.length} projects show elevated unlock pressure. Sell-side risk building across cluster.`;

      case 'RISK_ON_SHIFT':
        return `Broad risk-on signal across ${assets.length} markets. Positive alignment spreading.`;

      case 'RISK_OFF_SHIFT':
        return `Risk-off regime detected across ${assets.length} markets. Defensive positioning warranted.`;

      case 'NARRATIVE_EXHAUSTION':
        return `${assets.length} related markets moved into saturated narrative state. Edge compression across cluster.`;

      case 'BROAD_OVERHEAT':
        return `${assets.length} markets showing signs of overheating. Broad edge compression detected.`;

      case 'CLUSTER_WAKEUP':
        return `${theme} theme waking up — ${assets.length} markets in early/expanding phase. New opportunity cluster forming.`;

      case 'MIXED_CLUSTER':
        return `Mixed signals in ${theme} cluster: both bullish and risk signals present. Exercise caution.`;

      default:
        return `${assets.length} correlated alerts detected in ${windowMins}m window.`;
    }
  }
}

export const metaAlertBuilderService = new MetaAlertBuilderService();
