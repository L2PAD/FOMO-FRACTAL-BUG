/**
 * Execution Quality Alert Service
 * 
 * Detects anomalies: if execution score < 0.4 three times in a row
 * in the same context, raises an anomaly alert with suggested adjustment.
 */

import { MongoClient } from 'mongodb';

const COLLECTION = 'execution_quality_alerts';
const STREAKS_COLLECTION = 'execution_score_streaks';
const SCORE_THRESHOLD = 0.4;
const STREAK_THRESHOLD = 3;
const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'intelligence_engine';

async function getCollection(name: string) {
  const client = new MongoClient(MONGO_URL);
  await client.connect();
  return client.db(DB_NAME).collection(name);
}

interface ScoreEntry {
  asset: string;
  context: string;
  score: number;
  grade: string;
  timestamp: string;
  marketId?: string;
}

interface Streak {
  asset: string;
  context: string;
  consecutiveLow: number;
  scores: number[];
  lastUpdated: string;
}

interface QualityAlert {
  alertId: string;
  type: 'EXECUTION_ANOMALY';
  asset: string;
  context: string;
  consecutiveLow: number;
  avgScore: number;
  scores: number[];
  suggestedAdjustment: string;
  contextSummary: string;
  severity: 'WARNING' | 'CRITICAL';
  acknowledged: boolean;
  timestamp: string;
}

class ExecutionQualityAlertService {
  /**
   * Ingest a new execution score and check for anomalies.
   */
  async ingestScore(entry: ScoreEntry): Promise<QualityAlert | null> {
    const streaksCol = await getCollection(STREAKS_COLLECTION);
    const alertsCol = await getCollection(COLLECTION);

    // Get or create streak
    const existing = await streaksCol.findOne(
      { asset: entry.asset, context: entry.context },
      { projection: { _id: 0 } }
    );

    const streak: Streak = existing || {
      asset: entry.asset,
      context: entry.context,
      consecutiveLow: 0,
      scores: [],
      lastUpdated: new Date().toISOString(),
    };

    if (entry.score < SCORE_THRESHOLD) {
      streak.consecutiveLow += 1;
      streak.scores.push(entry.score);
      // Keep only last 10 scores in the streak
      if (streak.scores.length > 10) streak.scores = streak.scores.slice(-10);
    } else {
      // Reset streak on good score
      streak.consecutiveLow = 0;
      streak.scores = [];
    }
    streak.lastUpdated = new Date().toISOString();

    await streaksCol.updateOne(
      { asset: entry.asset, context: entry.context },
      { $set: streak },
      { upsert: true }
    );

    // Check if anomaly threshold is reached
    if (streak.consecutiveLow >= STREAK_THRESHOLD) {
      const avgScore = streak.scores.slice(-STREAK_THRESHOLD).reduce((a, b) => a + b, 0) / STREAK_THRESHOLD;
      const alert = this.buildAlert(entry, streak, avgScore);

      await alertsCol.insertOne({ ...alert });
      console.log(`[ExecQualityAlert] ANOMALY: ${entry.asset} (${entry.context}) — ${streak.consecutiveLow} consecutive low scores, avg=${avgScore.toFixed(3)}`);

      // Reset streak after alert
      await streaksCol.updateOne(
        { asset: entry.asset, context: entry.context },
        { $set: { consecutiveLow: 0, scores: [] } }
      );

      return alert;
    }

    return null;
  }

  private buildAlert(entry: ScoreEntry, streak: Streak, avgScore: number): QualityAlert {
    const severity = streak.consecutiveLow >= 5 ? 'CRITICAL' : 'WARNING';
    const adjustment = this.suggestAdjustment(entry.context, avgScore, streak.consecutiveLow);
    const summary = this.buildContextSummary(entry, streak, avgScore);

    return {
      alertId: `exec_qual_${Date.now()}_${entry.asset}`,
      type: 'EXECUTION_ANOMALY',
      asset: entry.asset,
      context: entry.context,
      consecutiveLow: streak.consecutiveLow,
      avgScore: Math.round(avgScore * 1000) / 1000,
      scores: streak.scores.slice(-STREAK_THRESHOLD),
      suggestedAdjustment: adjustment,
      contextSummary: summary,
      severity,
      acknowledged: false,
      timestamp: new Date().toISOString(),
    };
  }

  private suggestAdjustment(context: string, avgScore: number, count: number): string {
    const suggestions: string[] = [];

    if (context.includes('TREND')) {
      suggestions.push('Consider switching to LIMIT entries in trending markets to reduce slippage');
    }
    if (context.includes('RANGE')) {
      suggestions.push('Range-bound markets: tighten entry zones and use FADE_SPIKE style');
    }
    if (context.includes('TRANSITION')) {
      suggestions.push('Market in transition: reduce position size and wait for regime confirmation');
    }

    if (avgScore < 0.2) {
      suggestions.push('Execution quality critically low — pause entries and review strategy');
    } else if (avgScore < 0.3) {
      suggestions.push('Consider reducing aggressiveness: use WAIT_FOR_DIP instead of ENTER_MARKET');
    } else {
      suggestions.push('Fine-tune entry timing: recent entries show consistent edge leakage');
    }

    if (count >= 5) {
      suggestions.push('PATTERN DETECTED: Systematic execution weakness in this context. Flag for auto-tune review');
    }

    return suggestions.join('. ');
  }

  private buildContextSummary(entry: ScoreEntry, streak: Streak, avgScore: number): string {
    return `${entry.asset} in ${entry.context} context: ${streak.consecutiveLow} consecutive executions scored below ${SCORE_THRESHOLD} (avg: ${(avgScore * 100).toFixed(1)}%). Last scores: [${streak.scores.slice(-STREAK_THRESHOLD).map(s => (s * 100).toFixed(0) + '%').join(', ')}].`;
  }

  /**
   * Get all execution quality alerts.
   */
  async getAlerts(limit = 50): Promise<QualityAlert[]> {
    const col = await getCollection(COLLECTION);
    return col
      .find({}, { projection: { _id: 0 } })
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray() as Promise<QualityAlert[]>;
  }

  /**
   * Get current active streaks.
   */
  async getStreaks(): Promise<Streak[]> {
    const col = await getCollection(STREAKS_COLLECTION);
    return col
      .find({ consecutiveLow: { $gt: 0 } }, { projection: { _id: 0 } })
      .sort({ consecutiveLow: -1 })
      .toArray() as Promise<Streak[]>;
  }

  /**
   * Acknowledge an alert.
   */
  async acknowledge(alertId: string): Promise<boolean> {
    const col = await getCollection(COLLECTION);
    const result = await col.updateOne(
      { alertId },
      { $set: { acknowledged: true } }
    );
    return result.modifiedCount > 0;
  }
}

export const executionQualityAlertService = new ExecutionQualityAlertService();
