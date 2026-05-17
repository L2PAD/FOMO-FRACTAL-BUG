/**
 * Sentiment Reliability Service
 * ===============================
 * 
 * BLOCK S1: Unified Reliability Index (URI) - single source of truth.
 * 
 * Formula:
 * URI = 0.30*DataHealth + 0.30*DriftHealth + 0.25*CapitalHealth + 0.15*CalibrationHealth
 * 
 * Levels:
 * - OK (>=0.75): full operations
 * - WARN (0.60-0.75): reduced confidence/size
 * - DEGRADED (0.40-0.60): training blocked
 * - CRITICAL (<0.40): everything blocked
 */

import {
  ReliabilityLevel,
  ReliabilityComponents,
  ReliabilityActions,
  SentimentReliabilityStatus,
  URI_THRESHOLDS,
  URI_WEIGHTS,
} from './sentiment-reliability.types.js';
import { getSentimentParserHealthGuard } from '../guards/sentiment_parser_health_guard.service.js';
import { getSentimentDriftService } from '../drift/sentiment_drift.service.js';
import mongoose from 'mongoose';

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

export class SentimentReliabilityService {
  /**
   * Compute full reliability status
   */
  async computeStatus(): Promise<SentimentReliabilityStatus> {
    const reasons: string[] = [];

    // Compute all health components
    const dataHealth = await this.computeDataHealth(reasons);
    const driftHealth = await this.computeDriftHealth(reasons);
    const capitalHealth = await this.computeCapitalHealth(reasons);
    const calibrationHealth = await this.computeCalibrationHealth(reasons);

    // Calculate URI score
    const uriScore = clamp01(
      URI_WEIGHTS.dataHealth * dataHealth +
      URI_WEIGHTS.driftHealth * driftHealth +
      URI_WEIGHTS.capitalHealth * capitalHealth +
      URI_WEIGHTS.calibrationHealth * calibrationHealth
    );

    // Determine level
    const level = this.scoreToLevel(uriScore);

    // Get actions for this level
    let actions = this.levelToActions(level);

    // S4.3: Override training blocked if CapitalHealth < 50%
    if (capitalHealth < 0.50 && !actions.trainingBlocked) {
      actions = { ...actions, trainingBlocked: true };
      reasons.push('CAPITAL_GATE_TRAINING_BLOCKED');
    }

    // F3: Safe Mode when DataHealth is CRITICAL
    const safeMode = actions.safeMode || dataHealth < 0.20;
    if (safeMode && !actions.safeMode) {
      actions = { ...actions, safeMode: true };
      reasons.push('SAFE_MODE_DATA_CRITICAL');
    }

    return {
      uriScore,
      level,
      components: { dataHealth, driftHealth, capitalHealth, calibrationHealth },
      reasons,
      actions,
      safeMode,
      asOf: new Date().toISOString(),
    };
  }

  /**
   * Convert URI score to level
   */
  private scoreToLevel(score: number): ReliabilityLevel {
    if (score >= URI_THRESHOLDS.OK) return 'OK';
    if (score >= URI_THRESHOLDS.WARN) return 'WARN';
    if (score >= URI_THRESHOLDS.DEGRADED) return 'DEGRADED';
    return 'CRITICAL';
  }

  /**
   * Convert level to actions
   */
  private levelToActions(level: ReliabilityLevel): ReliabilityActions {
    switch (level) {
      case 'OK':
        return {
          workersBlocked: false,
          trainingBlocked: false,
          promotionBlocked: false,
          confidenceMultiplier: 1.0,
          sizeMultiplier: 1.0,
          safeMode: false,
        };
      case 'WARN':
        return {
          workersBlocked: false,
          trainingBlocked: false,
          promotionBlocked: true,
          confidenceMultiplier: 0.85,
          sizeMultiplier: 0.8,
          safeMode: false,
        };
      case 'DEGRADED':
        return {
          workersBlocked: false,
          trainingBlocked: true,
          promotionBlocked: true,
          confidenceMultiplier: 0.70,
          sizeMultiplier: 0.5,
          safeMode: false,
        };
      case 'CRITICAL':
        return {
          workersBlocked: true,
          trainingBlocked: true,
          promotionBlocked: true,
          confidenceMultiplier: 0.50,
          sizeMultiplier: 0.0,
          safeMode: true,  // F3: Safe Mode in CRITICAL
        };
    }
  }

  /**
   * Compute Data Health from Parser Guard
   */
  private async computeDataHealth(reasons: string[]): Promise<number> {
    try {
      const guard = getSentimentParserHealthGuard();
      const state = await guard.getState();

      if (!state) {
        reasons.push('NO_GUARD_STATE');
        return 0.7; // Neutral if no state yet
      }

      const metrics = state.details?.metrics || {};
      const cookiesMissing = !metrics.cookiesAvailable && metrics.activeSessions === 0;
      const zeroIngest = metrics.events6h === 0;
      const freshnessMinutes = metrics.lastEventAt
        ? (Date.now() - new Date(metrics.lastEventAt).getTime()) / 60000
        : Infinity;

      // Hard kill cases
      if (cookiesMissing) {
        reasons.push('COOKIES_MISSING');
        return 0.0;
      }

      if (zeroIngest && freshnessMinutes > 60) {
        reasons.push('ZERO_INGEST_STALE');
        return 0.1;
      }

      let score = 1.0;

      // Freshness degradation
      if (freshnessMinutes > 120) {
        score -= 0.4;
        reasons.push('STALE_DATA_120M');
      } else if (freshnessMinutes > 60) {
        score -= 0.2;
        reasons.push('STALE_DATA_60M');
      }

      // Error rate degradation
      const errorRate = metrics.errors6h > 0 && metrics.events6h > 0
        ? metrics.parserErrors6h / metrics.events6h
        : 0;

      if (errorRate > 0.15) {
        score -= 0.3;
        reasons.push('HIGH_ERROR_RATE');
      } else if (errorRate > 0.05) {
        score -= 0.1;
      }

      if (zeroIngest) {
        score -= 0.3;
        reasons.push('ZERO_INGEST');
      }

      return clamp01(score);
    } catch (err) {
      console.error('[Reliability] Error computing data health:', err);
      reasons.push('DATA_HEALTH_ERROR');
      return 0.5;
    }
  }

  /**
   * Compute Drift Health from PSI
   */
  private async computeDriftHealth(reasons: string[]): Promise<number> {
    try {
      const drift = getSentimentDriftService();
      const result = await drift.getLatest('24H');

      if (!result) {
        // No drift data yet - neutral
        return 0.7;
      }

      const psi = result.driftScore || 0;

      if (psi <= 0.15) return 1.0;

      if (psi <= 0.30) {
        reasons.push('DRIFT_WARN');
        return 0.75;
      }

      if (psi <= 0.50) {
        reasons.push('DRIFT_DEGRADED');
        return 0.50;
      }

      reasons.push('DRIFT_CRITICAL');
      return 0.20;
    } catch (err) {
      console.error('[Reliability] Error computing drift health:', err);
      reasons.push('DRIFT_HEALTH_ERROR');
      return 0.6;
    }
  }

  /**
   * Compute Capital Health from equity metrics
   */
  private async computeCapitalHealth(reasons: string[]): Promise<number> {
    try {
      const db = mongoose.connection.db;
      if (!db) return 0.7;

      // Get latest risk snapshot
      const snapshot = await db.collection('sent_risk_snapshots')
        .findOne({}, { sort: { ts: -1 } });

      if (!snapshot) {
        // No capital data - neutral
        return 0.7;
      }

      const dd = snapshot.maxDDPct || 0;
      const sharpe = snapshot.sharpeLike || 0;
      const expectancy = snapshot.expectancyPct || 0;

      let score = 1.0;

      // MaxDD mapping
      if (dd > 30) {
        score = 0.2;
        reasons.push('CAPITAL_MAXDD_GT30');
      } else if (dd > 20) {
        score = 0.4;
        reasons.push('CAPITAL_MAXDD_GT20');
      } else if (dd > 10) {
        score = 0.7;
      }

      // Negative expectancy penalty
      if (expectancy < 0) {
        score -= 0.15;
        reasons.push('NEG_EXPECTANCY');
      }

      // Negative sharpe penalty
      if (sharpe < 0) {
        score -= 0.10;
        reasons.push('NEG_SHARPE');
      }

      return clamp01(score);
    } catch (err) {
      console.error('[Reliability] Error computing capital health:', err);
      reasons.push('CAPITAL_HEALTH_ERROR');
      return 0.6;
    }
  }

  /**
   * Compute Calibration Health from Shadow stats
   */
  private async computeCalibrationHealth(reasons: string[]): Promise<number> {
    try {
      const db = mongoose.connection.db;
      if (!db) return 0.7;

      // Get shadow stats for last 14 days
      const since = new Date(Date.now() - 14 * 24 * 3600_000);
      
      const samples = await db.collection('sentiment_dir_samples')
        .find({
          window: '24H',
          finalizedAt: { $gte: since },
          'shadow.rule': { $exists: true },
          'shadow.ml': { $exists: true },
        })
        .toArray();

      const finalized = samples.length;

      // If not enough data - neutral
      if (finalized < 50) {
        return 0.7;
      }

      // Calculate hit rates
      let ruleCorrect = 0;
      let mlCorrect = 0;

      for (const s of samples) {
        const actual = s.label;
        if (!actual || actual === 'NEUTRAL') continue;

        const ruleAction = s.shadow?.rule?.action;
        const mlAction = s.shadow?.ml?.action;

        if (ruleAction === actual) ruleCorrect++;
        if (mlAction === actual) mlCorrect++;
      }

      const nonNeutral = samples.filter(s => s.label && s.label !== 'NEUTRAL').length;
      if (nonNeutral < 30) return 0.7;

      const ruleHitRate = ruleCorrect / nonNeutral;
      const mlHitRate = mlCorrect / nonNeutral;
      const delta = mlHitRate - ruleHitRate;

      if (delta >= 0.02) {
        return 1.0;
      }

      if (delta >= -0.02) {
        return 0.8;
      }

      if (delta >= -0.07) {
        reasons.push('ML_UNDERPERFORMING');
        return 0.5;
      }

      reasons.push('ML_STRONG_UNDERPERFORM');
      return 0.2;
    } catch (err) {
      console.error('[Reliability] Error computing calibration health:', err);
      reasons.push('CALIBRATION_HEALTH_ERROR');
      return 0.6;
    }
  }

  /**
   * Quick check if workers are allowed
   */
  async isWorkersAllowed(): Promise<boolean> {
    const status = await this.computeStatus();
    return !status.actions.workersBlocked;
  }

  /**
   * Quick check if training is allowed
   */
  async isTrainingAllowed(): Promise<boolean> {
    const status = await this.computeStatus();
    return !status.actions.trainingBlocked;
  }

  /**
   * Get confidence multiplier
   */
  async getConfidenceMultiplier(): Promise<number> {
    const status = await this.computeStatus();
    return status.actions.confidenceMultiplier;
  }

  /**
   * Get size multiplier
   */
  async getSizeMultiplier(): Promise<number> {
    const status = await this.computeStatus();
    return status.actions.sizeMultiplier;
  }
}

// Singleton
let reliabilityServiceInstance: SentimentReliabilityService | null = null;

export function getSentimentReliabilityService(): SentimentReliabilityService {
  if (!reliabilityServiceInstance) {
    reliabilityServiceInstance = new SentimentReliabilityService();
  }
  return reliabilityServiceInstance;
}

console.log('[Sentiment-ML] Reliability Service loaded (BLOCK S1)');
