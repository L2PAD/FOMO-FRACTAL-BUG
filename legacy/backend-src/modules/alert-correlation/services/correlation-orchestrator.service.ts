/**
 * Correlation Orchestrator Service
 *
 * Main pipeline: alerts → cluster → overlap → detect → regime → priority
 *              → quality gate → build → dedup → deliver
 */

import { MongoClient } from 'mongodb';
import { alertClustererService } from './alert-clusterer.service.js';
import { factorOverlapService } from './factor-overlap.service.js';
import { correlationDetectorService } from './correlation-detector.service.js';
import { regimeShiftDetectorService } from './regime-shift-detector.service.js';
import { clusterPriorityService } from './cluster-priority.service.js';
import { correlationQualityGateService } from './correlation-quality-gate.service.js';
import { metaAlertBuilderService } from './meta-alert-builder.service.js';
import { correlationDedupService } from './correlation-dedup.service.js';
import type { RawAlertRef, MetaAlert } from '../types/correlation.types.js';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'intelligence_engine';

class CorrelationOrchestratorService {
  private recentMetaAlerts: MetaAlert[] = [];

  /**
   * Process a batch of raw alerts and return any meta-alerts.
   */
  async analyze(rawAlerts: RawAlertRef[]): Promise<MetaAlert[]> {
    if (rawAlerts.length < 2) return [];

    // 1. Cluster
    const clusters = alertClustererService.clusterBatch(rawAlerts);
    if (clusters.length === 0) return [];

    const metaAlerts: MetaAlert[] = [];

    for (const cluster of clusters) {
      // 2. Factor overlap
      const overlap = factorOverlapService.compute(cluster.alerts);

      // 3. Detect correlation type
      const detection = correlationDetectorService.detect(cluster, overlap);

      // 4. Regime shift
      const regime = regimeShiftDetectorService.detect(cluster, overlap);

      // 5. Priority
      const priority = clusterPriorityService.compute(cluster, overlap, regime);

      // 6. Quality gate
      const gate = correlationQualityGateService.evaluate(cluster, overlap, detection, regime, priority);
      if (!gate.pass) {
        console.log(`[Correlation] Gate rejected: ${gate.reason} (overlap=${overlap.overlapScore}, gain=${gate.metaInsightGain})`);
        continue;
      }

      // 7. Build meta-alert
      const metaAlert = metaAlertBuilderService.build(
        cluster, overlap, detection, regime, priority, gate.metaInsightGain,
      );

      // 8. Dedup
      if (!correlationDedupService.canReEmit(metaAlert.dedupKey, metaAlert.type, metaAlert.confidence)) {
        console.log(`[Correlation] Dedup suppressed: ${metaAlert.type} (${metaAlert.dedupKey})`);
        continue;
      }

      correlationDedupService.markEmitted(metaAlert.dedupKey);
      metaAlerts.push(metaAlert);
    }

    // Store and return
    if (metaAlerts.length > 0) {
      this.recentMetaAlerts = [...metaAlerts, ...this.recentMetaAlerts].slice(0, 50);
      await this.saveMetaAlerts(metaAlerts);
      console.log(`[Correlation] Generated ${metaAlerts.length} meta-alert(s): ${metaAlerts.map(m => m.type).join(', ')}`);
    }

    return metaAlerts;
  }

  /**
   * Ingest a single raw alert (real-time mode).
   */
  async ingestAlert(alert: RawAlertRef): Promise<MetaAlert[]> {
    const clusters = alertClustererService.ingest(alert);
    if (clusters.length === 0) return [];

    // Process each cluster through the pipeline
    const allMeta: MetaAlert[] = [];
    for (const cluster of clusters) {
      const results = await this.analyze(cluster.alerts);
      allMeta.push(...results);
    }
    return allMeta;
  }

  /**
   * Get recent meta-alerts.
   */
  getRecent(limit = 20): MetaAlert[] {
    return this.recentMetaAlerts.slice(0, limit);
  }

  /**
   * Get meta-alerts from DB.
   */
  async getHistory(limit = 50): Promise<MetaAlert[]> {
    const client = new MongoClient(MONGO_URL);
    try {
      await client.connect();
      const docs = await client.db(DB_NAME)
        .collection('meta_alerts')
        .find({}, { projection: { _id: 0 } })
        .sort({ timestamp: -1 })
        .limit(limit)
        .toArray();
      return docs as MetaAlert[];
    } finally {
      await client.close();
    }
  }

  /**
   * Get current regime state.
   */
  getRegimeState(): { direction: string; confidence: number; lastUpdate: number } | null {
    const latest = this.recentMetaAlerts.find(m => m.regimeShift?.detected);
    if (!latest?.regimeShift) return null;
    return {
      direction: latest.regimeShift.direction,
      confidence: latest.regimeShift.confidence,
      lastUpdate: latest.timestamp,
    };
  }

  /**
   * Get suppressed member alert IDs from recent meta-alerts.
   */
  getSuppressedAlertIds(): Set<string> {
    const ids = new Set<string>();
    for (const meta of this.recentMetaAlerts) {
      if (meta.suppressMemberAlerts) {
        for (const id of meta.members) ids.add(id);
      }
    }
    return ids;
  }

  private async saveMetaAlerts(alerts: MetaAlert[]): Promise<void> {
    try {
      const client = new MongoClient(MONGO_URL);
      await client.connect();
      const col = client.db(DB_NAME).collection('meta_alerts');
      for (const a of alerts) {
        await col.insertOne({ ...a });
      }
      await client.close();
    } catch {
      // Non-critical
    }
  }

  clear(): void {
    this.recentMetaAlerts = [];
    alertClustererService.clearBuffer();
    correlationDedupService.clear();
  }
}

export const correlationOrchestratorService = new CorrelationOrchestratorService();
