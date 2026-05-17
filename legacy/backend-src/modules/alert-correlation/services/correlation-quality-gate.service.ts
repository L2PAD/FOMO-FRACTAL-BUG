/**
 * Correlation Quality Gate Service
 *
 * Filters meta-alerts that don't add meaningful knowledge
 * beyond what the raw alerts already provide.
 *
 * metaInsightGain = sharedFactorStrength×0.4 + regimeShiftConfidence×0.3
 *                 + clusterDensity×0.2 + redundancyReduction×0.1
 */

import type { AlertCluster, FactorOverlapResult, MetaAlertType } from '../types/correlation.types.js';
import type { DetectionResult } from './correlation-detector.service.js';
import type { RegimeShiftResult } from './regime-shift-detector.service.js';
import type { PriorityResult } from './cluster-priority.service.js';

const MIN_CLUSTER_SIZE = 2;
const MIN_OVERLAP_SCORE = 0.03;
const MIN_PRIORITY_SCORE = 0.2;
const MIN_INSIGHT_GAIN = 0.15;

export interface QualityGateResult {
  pass: boolean;
  metaInsightGain: number;
  reason?: string;
}

class CorrelationQualityGateService {
  evaluate(
    cluster: AlertCluster,
    overlap: FactorOverlapResult,
    detection: DetectionResult,
    regime: RegimeShiftResult,
    priority: PriorityResult,
  ): QualityGateResult {
    // 1. Min cluster size
    if (cluster.alerts.length < MIN_CLUSTER_SIZE) {
      return { pass: false, metaInsightGain: 0, reason: 'CLUSTER_TOO_SMALL' };
    }

    // 2. Min overlap
    if (overlap.overlapScore < MIN_OVERLAP_SCORE && !regime.detected) {
      return { pass: false, metaInsightGain: 0, reason: 'OVERLAP_TOO_LOW' };
    }

    // 3. Min priority
    if (priority.priorityScore < MIN_PRIORITY_SCORE) {
      return { pass: false, metaInsightGain: 0, reason: 'PRIORITY_TOO_LOW' };
    }

    // 4. Compute metaInsightGain
    const sharedFactorStrength = Math.min(1, overlap.overlapScore * 5);
    const regimeShiftConfidence = regime.detected ? regime.confidence : 0;
    const clusterDensity = this.computeDensity(cluster);
    const redundancyReduction = this.computeRedundancyReduction(cluster, priority.memberDiversityScore);

    const metaInsightGain =
      sharedFactorStrength * 0.4 +
      regimeShiftConfidence * 0.3 +
      clusterDensity * 0.2 +
      redundancyReduction * 0.1;

    if (metaInsightGain < MIN_INSIGHT_GAIN) {
      return { pass: false, metaInsightGain, reason: 'LOW_INSIGHT_GAIN' };
    }

    // 5. Mixed cluster with high contradiction — lower bar but still allow
    if (detection.contradictionScore > 0.5 && metaInsightGain < 0.25) {
      return { pass: false, metaInsightGain, reason: 'HIGH_CONTRADICTION_LOW_GAIN' };
    }

    return { pass: true, metaInsightGain: Math.round(metaInsightGain * 100) / 100 };
  }

  private computeDensity(cluster: AlertCluster): number {
    const windowMin = Math.max(1, (cluster.windowEnd - cluster.windowStart) / 60000);
    return Math.min(1, cluster.alerts.length / (windowMin * 0.3));
  }

  private computeRedundancyReduction(cluster: AlertCluster, diversityScore: number): number {
    // High diversity = meta-alert reduces many individual alerts to one
    // Low diversity = just repeating the same asset's alerts
    return diversityScore;
  }
}

export const correlationQualityGateService = new CorrelationQualityGateService();
