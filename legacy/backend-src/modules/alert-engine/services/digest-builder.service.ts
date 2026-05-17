/**
 * Digest Builder
 *
 * Two modes:
 *   1. Real-time: immediate alerts for Tier 1 signals
 *   2. Batch: aggregated digest every 30 minutes (adaptive)
 *
 * Adaptive: Tier 1 → immediate, quiet market → less frequent.
 */

import type { AlertPayload, DigestPayload } from '../types/alert.types.js';

class DigestBuilderService {
  private batchBuffer: AlertPayload[] = [];
  private lastBatchTime = Date.now();
  private batchIntervalMs = 30 * 60 * 1000; // 30 min default
  private minBatchIntervalMs = 15 * 60 * 1000; // 15 min minimum
  private maxBatchIntervalMs = 60 * 60 * 1000; // 60 min maximum

  /**
   * Add alert to appropriate channel.
   * Returns: { immediate: AlertPayload | null, batchReady: DigestPayload | null }
   */
  process(alert: AlertPayload): { immediate: AlertPayload | null; batchReady: DigestPayload | null } {
    let immediate: AlertPayload | null = null;
    let batchReady: DigestPayload | null = null;

    // Tier HIGH / IMMEDIATE → deliver immediately
    if (alert.urgency === 'IMMEDIATE' || alert.tier === 'HIGH') {
      immediate = alert;
    }

    // All alerts go into batch buffer
    this.batchBuffer.push(alert);

    // Adapt batch interval based on activity
    this.adaptInterval();

    // Check if batch is ready
    const elapsed = Date.now() - this.lastBatchTime;
    if (elapsed >= this.batchIntervalMs && this.batchBuffer.length > 0) {
      batchReady = this.buildBatchDigest();
    }

    return { immediate, batchReady };
  }

  /**
   * Force flush current batch (for API trigger).
   */
  flushBatch(): DigestPayload | null {
    if (this.batchBuffer.length === 0) return null;
    return this.buildBatchDigest();
  }

  /**
   * Get pending batch count.
   */
  getPendingCount(): number {
    return this.batchBuffer.length;
  }

  private buildBatchDigest(): DigestPayload {
    const alerts = [...this.batchBuffer];
    this.batchBuffer = [];
    this.lastBatchTime = Date.now();

    // Sort by priority (highest first)
    alerts.sort((a, b) => b.priority - a.priority);

    const high = alerts.filter(a => a.tier === 'HIGH').length;
    const medium = alerts.filter(a => a.tier === 'MEDIUM').length;
    const low = alerts.filter(a => a.tier === 'LOW').length;

    return {
      type: 'batch',
      timestamp: new Date().toISOString(),
      alerts,
      summary: {
        total: alerts.length,
        high,
        medium,
        low,
        topAction: alerts.length > 0 ? alerts[0].action : null,
      },
    };
  }

  private adaptInterval(): void {
    const recentHighCount = this.batchBuffer.filter(a => a.tier === 'HIGH').length;

    if (recentHighCount >= 3) {
      // Many high signals → shorten interval
      this.batchIntervalMs = this.minBatchIntervalMs;
    } else if (this.batchBuffer.length === 0) {
      // Quiet market → extend interval
      this.batchIntervalMs = this.maxBatchIntervalMs;
    } else {
      // Normal
      this.batchIntervalMs = 30 * 60 * 1000;
    }
  }
}

export const digestBuilderService = new DigestBuilderService();
