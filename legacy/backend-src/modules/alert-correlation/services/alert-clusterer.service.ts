/**
 * Alert Clusterer Service
 *
 * Groups raw alerts that occurred within a time window (30 min)
 * and have meaningful factor overlap. Min 2 alerts per cluster.
 */

import { factorOverlapService } from './factor-overlap.service.js';
import type { RawAlertRef, AlertCluster } from '../types/correlation.types.js';

const WINDOW_MS = 30 * 60 * 1000; // 30 minutes
const MIN_CLUSTER_SIZE = 2;
const MIN_OVERLAP_FOR_CLUSTER = 0.05; // Low bar — quality gate filters later

class AlertClustererService {
  private alertBuffer: RawAlertRef[] = [];
  private clusterCounter = 0;

  /**
   * Add an alert and return any new clusters formed.
   */
  ingest(alert: RawAlertRef): AlertCluster[] {
    this.alertBuffer.push(alert);
    this.pruneOldAlerts();
    return this.findClusters();
  }

  /**
   * Cluster a batch of alerts at once.
   */
  clusterBatch(alerts: RawAlertRef[]): AlertCluster[] {
    if (alerts.length < MIN_CLUSTER_SIZE) return [];

    const clusters: AlertCluster[] = [];
    const used = new Set<string>();

    // Sort by timestamp
    const sorted = [...alerts].sort((a, b) => a.timestamp - b.timestamp);

    for (let i = 0; i < sorted.length; i++) {
      if (used.has(sorted[i].alertId)) continue;

      const seed = sorted[i];
      const members = [seed];
      used.add(seed.alertId);

      for (let j = i + 1; j < sorted.length; j++) {
        if (used.has(sorted[j].alertId)) continue;

        // Time window check
        if (sorted[j].timestamp - seed.timestamp > WINDOW_MS) break;

        // Factor overlap check
        const overlap = factorOverlapService.compute([seed, sorted[j]]);
        if (overlap.overlapScore >= MIN_OVERLAP_FOR_CLUSTER || this.sameThemeOrAsset(seed, sorted[j])) {
          members.push(sorted[j]);
          used.add(sorted[j].alertId);
        }
      }

      if (members.length >= MIN_CLUSTER_SIZE) {
        clusters.push({
          clusterId: `cluster_${++this.clusterCounter}_${Date.now()}`,
          alerts: members,
          windowStart: members[0].timestamp,
          windowEnd: members[members.length - 1].timestamp,
        });
      }
    }

    return clusters;
  }

  private findClusters(): AlertCluster[] {
    return this.clusterBatch(this.alertBuffer);
  }

  private sameThemeOrAsset(a: RawAlertRef, b: RawAlertRef): boolean {
    // Quick check: same asset
    if (a.asset && b.asset && a.asset === b.asset) return true;

    // Quick check: shared theme
    const aThemes = new Set(a.factors?.themeFactors || []);
    const bThemes = b.factors?.themeFactors || [];
    for (const t of bThemes) {
      if (aThemes.has(t)) return true;
    }

    return false;
  }

  private pruneOldAlerts(): void {
    const cutoff = Date.now() - WINDOW_MS * 2;
    this.alertBuffer = this.alertBuffer.filter(a => a.timestamp > cutoff);
  }

  clearBuffer(): void {
    this.alertBuffer = [];
  }
}

export const alertClustererService = new AlertClustererService();
