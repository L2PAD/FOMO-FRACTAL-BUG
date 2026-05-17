/**
 * Execution Anomaly Repository
 *
 * Stores detected anomalies with suppression tracking.
 */

import { MongoClient } from 'mongodb';
import type { ExecutionAnomaly } from '../types/execution-anomaly.types.js';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'intelligence_engine';
const COLLECTION = 'execution_anomalies';
const SUPPRESSION_HOURS = 24;

class ExecutionAnomalyRepository {
  private async col() {
    const client = new MongoClient(MONGO_URL);
    await client.connect();
    return client.db(DB_NAME).collection(COLLECTION);
  }

  /**
   * Save an anomaly alert.
   */
  async save(anomaly: ExecutionAnomaly): Promise<void> {
    const col = await this.col();
    await col.insertOne({ ...anomaly });
  }

  /**
   * Check if context is currently suppressed (alert already fired recently).
   */
  async isSuppressed(contextKey: string): Promise<boolean> {
    const col = await this.col();
    const now = new Date().toISOString();
    const existing = await col.findOne({
      contextKey,
      suppressedUntil: { $gt: now },
    });
    return !!existing;
  }

  /**
   * Calculate suppression expiry time.
   */
  static calculateSuppressedUntil(): string {
    return new Date(Date.now() + SUPPRESSION_HOURS * 60 * 60 * 1000).toISOString();
  }

  /**
   * Get all anomalies, newest first.
   */
  async getAll(limit = 50): Promise<ExecutionAnomaly[]> {
    const col = await this.col();
    return col
      .find({}, { projection: { _id: 0 } })
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray() as unknown as ExecutionAnomaly[];
  }

  /**
   * Get unacknowledged anomalies.
   */
  async getUnacknowledged(limit = 20): Promise<ExecutionAnomaly[]> {
    const col = await this.col();
    return col
      .find({ acknowledged: false }, { projection: { _id: 0 } })
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray() as unknown as ExecutionAnomaly[];
  }

  /**
   * Acknowledge an anomaly.
   */
  async acknowledge(anomalyId: string): Promise<boolean> {
    const col = await this.col();
    const result = await col.updateOne(
      { anomalyId },
      { $set: { acknowledged: true } },
    );
    return result.modifiedCount > 0;
  }

  /**
   * Get anomaly history for a specific context key.
   */
  async getByContext(contextKey: string, limit = 10): Promise<ExecutionAnomaly[]> {
    const col = await this.col();
    return col
      .find({ contextKey }, { projection: { _id: 0 } })
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray() as unknown as ExecutionAnomaly[];
  }
}

export const anomalyRepo = new ExecutionAnomalyRepository();
