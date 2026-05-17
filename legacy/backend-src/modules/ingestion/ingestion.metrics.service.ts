/**
 * Ingestion Metrics Service
 * =========================
 * Records ingestion run metrics to MongoDB for monitoring and alerting.
 * Collection: ingestion_runs
 */

import mongoose from 'mongoose';
import type { IngestionRunResult } from './ingestion.types.js';

const METRICS_COLLECTION = 'ingestion_runs';

export interface IngestionHealthSnapshot {
  lastRunAt: Date | null;
  lastSuccessAt: Date | null;
  runsLast1h: number;
  eventsLast1h: number;
  dedupeRate: number;
  errorRate: number;
  consecutiveZeroInserts: number;
}

class IngestionMetricsService {
  /**
   * Record a completed ingestion run.
   */
  async record(result: IngestionRunResult): Promise<void> {
    const db = mongoose.connection.db;
    if (!db) return;

    await db.collection(METRICS_COLLECTION).insertOne({
      ...result,
      durationMs: result.finishedAt.getTime() - result.startedAt.getTime(),
      recordedAt: new Date(),
    });

    console.log(
      `[IngestionMetrics] ${result.source}: fetched=${result.fetched} inserted=${result.inserted} dup=${result.duplicated} err=${result.errors} (${result.durationMs}ms)`
    );
  }

  /**
   * Get health snapshot for monitoring dashboard.
   */
  async getHealth(): Promise<IngestionHealthSnapshot> {
    const db = mongoose.connection.db;
    if (!db) {
      return {
        lastRunAt: null,
        lastSuccessAt: null,
        runsLast1h: 0,
        eventsLast1h: 0,
        dedupeRate: 0,
        errorRate: 0,
        consecutiveZeroInserts: 0,
      };
    }

    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    const col = db.collection(METRICS_COLLECTION);

    // Last run
    const lastRun = await col.findOne({}, { sort: { finishedAt: -1 } });

    // Last success (inserted > 0)
    const lastSuccess = await col.findOne(
      { inserted: { $gt: 0 } },
      { sort: { finishedAt: -1 } }
    );

    // Runs in last hour
    const recentRuns = await col.find({ startedAt: { $gte: oneHourAgo } }).toArray();
    const runsLast1h = recentRuns.length;

    // Aggregate metrics from recent runs
    let totalFetched = 0;
    let totalInserted = 0;
    let totalDuplicated = 0;
    let totalErrors = 0;

    for (const run of recentRuns) {
      totalFetched += run.fetched || 0;
      totalInserted += run.inserted || 0;
      totalDuplicated += run.duplicated || 0;
      totalErrors += run.errors || 0;
    }

    const dedupeRate = totalFetched > 0 ? totalDuplicated / totalFetched : 0;
    const errorRate = totalFetched > 0 ? totalErrors / totalFetched : 0;

    // Consecutive zero inserts (from most recent)
    const recentByTime = await col
      .find({})
      .sort({ finishedAt: -1 })
      .limit(20)
      .toArray();

    let consecutiveZeroInserts = 0;
    for (const run of recentByTime) {
      if ((run.inserted || 0) === 0) {
        consecutiveZeroInserts++;
      } else {
        break;
      }
    }

    return {
      lastRunAt: lastRun?.finishedAt ?? null,
      lastSuccessAt: lastSuccess?.finishedAt ?? null,
      runsLast1h,
      eventsLast1h: totalInserted,
      dedupeRate: Math.round(dedupeRate * 100) / 100,
      errorRate: Math.round(errorRate * 100) / 100,
      consecutiveZeroInserts,
    };
  }

  /**
   * Get recent runs for admin view.
   */
  async getRecentRuns(limit = 20): Promise<any[]> {
    const db = mongoose.connection.db;
    if (!db) return [];

    return db
      .collection(METRICS_COLLECTION)
      .find({}, { projection: { _id: 0 } })
      .sort({ finishedAt: -1 })
      .limit(limit)
      .toArray();
  }
}

export const ingestionMetricsService = new IngestionMetricsService();
