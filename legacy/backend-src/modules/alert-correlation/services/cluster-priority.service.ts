/**
 * Cluster Priority Service
 *
 * Computes meta-alert priority from weighted factors.
 * Also computes memberDiversityScore.
 *
 * Weights: avgEdge=0.25, avgConfidence=0.20, overlap=0.20,
 *          alertDensity=0.15, execQuality=0.10, regimeShift=0.10
 */

import type { AlertCluster, FactorOverlapResult, RawAlertRef } from '../types/correlation.types.js';
import type { RegimeShiftResult } from './regime-shift-detector.service.js';

export interface PriorityResult {
  priorityScore: number;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  memberDiversityScore: number;
}

class ClusterPriorityService {
  compute(
    cluster: AlertCluster,
    overlap: FactorOverlapResult,
    regime: RegimeShiftResult,
  ): PriorityResult {
    const alerts = cluster.alerts;

    // Avg edge
    const edges = alerts.map(a => a.edge ?? 0).filter(e => e > 0);
    const avgEdge = edges.length > 0 ? edges.reduce((s, e) => s + e, 0) / edges.length : 0;

    // Avg confidence
    const confs = alerts.map(a => a.confidence ?? 0).filter(c => c > 0);
    const avgConf = confs.length > 0 ? confs.reduce((s, c) => s + c, 0) / confs.length : 0;

    // Alert density (alerts per 10 min)
    const windowMin = Math.max(1, (cluster.windowEnd - cluster.windowStart) / 60000);
    const density = Math.min(1, alerts.length / (windowMin * 0.5));

    // Overlap score (already 0-1ish)
    const overlapNorm = Math.min(1, overlap.overlapScore * 3);

    // Regime shift confidence
    const regimeScore = regime.detected ? regime.confidence : 0;

    // Execution quality (avg from alerts if available — simplified to 0.5 default)
    const execQuality = 0.5;

    const priorityScore =
      avgEdge * 10 * 0.25 +
      avgConf * 0.20 +
      overlapNorm * 0.20 +
      density * 0.15 +
      execQuality * 0.10 +
      regimeScore * 0.10;

    const priority: 'HIGH' | 'MEDIUM' | 'LOW' =
      priorityScore > 0.6 ? 'HIGH' :
      priorityScore > 0.35 ? 'MEDIUM' : 'LOW';

    // Member diversity: unique assets / total alerts
    const uniqueAssets = new Set(alerts.map(a => a.asset).filter(Boolean));
    const uniqueMarkets = new Set(alerts.map(a => a.marketId));
    const memberDiversityScore = Math.min(1,
      (uniqueAssets.size / Math.max(1, alerts.length)) * 0.6 +
      (uniqueMarkets.size / Math.max(1, alerts.length)) * 0.4
    );

    return {
      priorityScore: Math.round(priorityScore * 100) / 100,
      priority,
      memberDiversityScore: Math.round(memberDiversityScore * 100) / 100,
    };
  }
}

export const clusterPriorityService = new ClusterPriorityService();
