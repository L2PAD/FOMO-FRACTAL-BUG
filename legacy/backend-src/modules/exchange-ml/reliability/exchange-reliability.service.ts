/**
 * Exchange Reliability Service
 * ==============================
 * 
 * EX-S1: Unified Reliability Index (URI) for Exchange.
 * 
 * Formula:
 * URI = 0.30*DataHealth + 0.30*DriftHealth + 0.25*CapitalHealth + 0.15*CalibrationHealth
 * 
 * Levels:
 * - OK (>=0.75): full operations
 * - WARN (0.60-0.75): reduced confidence/size, promotion blocked
 * - DEGRADED (0.40-0.60): training blocked
 * - CRITICAL (<0.40): everything blocked
 */

import {
  ReliabilityLevel,
  ExchangeReliabilityActions,
  ExchangeReliabilityStatus,
  EX_URI_THRESHOLDS,
  EX_URI_WEIGHTS,
} from './exchange-reliability.types.js';
import { getExchangePriceProviderHealthService } from './exchange-price-provider-health.service.js';
import mongoose from 'mongoose';

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

export class ExchangeReliabilityService {
  /**
   * Compute full reliability status
   */
  async computeStatus(): Promise<ExchangeReliabilityStatus> {
    const reasons: string[] = [];

    // Compute all health components
    const [dataResult, driftResult, capitalResult, calibrationResult] = await Promise.all([
      this.computeDataHealth(reasons),
      this.computeDriftHealth(reasons),
      this.computeCapitalHealth(reasons),
      this.computeCalibrationHealth(reasons),
    ]);

    const components = {
      dataHealth: clamp01(dataResult.score),
      driftHealth: clamp01(driftResult.score),
      capitalHealth: clamp01(capitalResult.score),
      calibrationHealth: clamp01(calibrationResult.score),
    };

    // Calculate URI score
    const uriScore = clamp01(
      EX_URI_WEIGHTS.dataHealth * components.dataHealth +
      EX_URI_WEIGHTS.driftHealth * components.driftHealth +
      EX_URI_WEIGHTS.capitalHealth * components.capitalHealth +
      EX_URI_WEIGHTS.calibrationHealth * components.calibrationHealth
    );

    // Determine level
    const level = this.scoreToLevel(uriScore);

    // Get actions for this level
    let actions = this.levelToActions(level);

    // EX-S4: Override training blocked if CapitalHealth < 50%
    if (components.capitalHealth < 0.50 && !actions.trainingBlocked) {
      actions = { ...actions, trainingBlocked: true };
      reasons.push('CAPITAL_GATE_TRAINING_BLOCKED');
    }

    return {
      uriScore,
      level,
      components,
      reasons,
      actions,
      asOf: new Date().toISOString(),
      raw: {
        data: dataResult.raw,
        drift: driftResult.raw,
        capital: capitalResult.raw,
        calibration: calibrationResult.raw,
      },
    };
  }

  /**
   * Convert URI score to level
   */
  private scoreToLevel(score: number): ReliabilityLevel {
    if (score >= EX_URI_THRESHOLDS.OK) return 'OK';
    if (score >= EX_URI_THRESHOLDS.WARN) return 'WARN';
    if (score >= EX_URI_THRESHOLDS.DEGRADED) return 'DEGRADED';
    return 'CRITICAL';
  }

  /**
   * Convert level to actions
   */
  private levelToActions(level: ReliabilityLevel): ExchangeReliabilityActions {
    switch (level) {
      case 'OK':
        return {
          workersBlocked: false,
          trainingBlocked: false,
          promotionBlocked: false,
          confidenceMultiplier: 1.0,
          sizeMultiplier: 1.0,
        };
      case 'WARN':
        return {
          workersBlocked: false,
          trainingBlocked: false,
          promotionBlocked: true,
          confidenceMultiplier: 0.85,
          sizeMultiplier: 0.80,
        };
      case 'DEGRADED':
        return {
          workersBlocked: false,
          trainingBlocked: true,
          promotionBlocked: true,
          confidenceMultiplier: 0.70,
          sizeMultiplier: 0.50,
        };
      case 'CRITICAL':
        return {
          workersBlocked: true,
          trainingBlocked: true,
          promotionBlocked: true,
          confidenceMultiplier: 0.50,
          sizeMultiplier: 0.25,
        };
    }
  }

  /**
   * Compute Data Health from Price Provider
   */
  private async computeDataHealth(reasons: string[]): Promise<{ score: number; raw?: any }> {
    try {
      const providerHealth = getExchangePriceProviderHealthService();
      const result = await providerHealth.check();

      reasons.push(...result.reasons.map(r => `DATA:${r}`));

      return { score: result.score, raw: result.metrics };
    } catch (err) {
      console.error('[Exchange Reliability] Error computing data health:', err);
      reasons.push('DATA:ERROR');
      return { score: 0.5 };
    }
  }

  /**
   * Compute Drift Health
   * For now returns neutral - will be connected to EX-S3 drift stabilizer
   */
  private async computeDriftHealth(reasons: string[]): Promise<{ score: number; raw?: any }> {
    try {
      const db = mongoose.connection.db;
      if (!db) return { score: 0.7 };

      // Check if drift state exists from EX-S3
      const driftState = await db.collection('exchange_drift_state')
        .findOne({}, { sort: { asOf: -1 } });

      if (!driftState) {
        // No drift data yet - neutral
        return { score: 0.7, raw: { status: 'NO_DATA' } };
      }

      // Map stabilized status to score
      const status = driftState.stabilizedStatus || 'OK';
      let score = 0.7;

      switch (status) {
        case 'OK': score = 1.0; break;
        case 'WARN': score = 0.65; reasons.push('DRIFT:WARN'); break;
        case 'DEGRADED': score = 0.45; reasons.push('DRIFT:DEGRADED'); break;
        case 'CRITICAL': score = 0.20; reasons.push('DRIFT:CRITICAL'); break;
      }

      return { score, raw: { status, psiEma: driftState.psiEma } };
    } catch (err) {
      console.error('[Exchange Reliability] Error computing drift health:', err);
      reasons.push('DRIFT:ERROR');
      return { score: 0.6 };
    }
  }

  /**
   * Compute Capital Health from trade performance
   */
  private async computeCapitalHealth(reasons: string[]): Promise<{ score: number; raw?: any }> {
    try {
      const db = mongoose.connection.db;
      if (!db) return { score: 0.7 };

      // Get recent trades for capital metrics
      const since = new Date(Date.now() - 30 * 24 * 3600_000);
      const trades = await db.collection('exchange_trades')
        .find({ closedAt: { $gte: since } })
        .sort({ closedAt: 1 })
        .toArray();

      if (!trades.length) {
        // No trades - try alternative collection
        const altTrades = await db.collection('trade_records')
          .find({ closedAt: { $gte: since } })
          .sort({ closedAt: 1 })
          .toArray();

        if (!altTrades.length) {
          return { score: 0.7, raw: { status: 'NO_TRADES' } };
        }
      }

      // Calculate metrics from trades
      const pnls = trades.map(t => t.pnlPct || t.returnPct || 0);
      if (!pnls.length) return { score: 0.7, raw: { status: 'NO_PNL_DATA' } };

      const mean = pnls.reduce((a, b) => a + b, 0) / pnls.length;
      const variance = pnls.reduce((a, x) => a + (x - mean) * (x - mean), 0) / Math.max(1, pnls.length - 1);
      const std = Math.sqrt(variance);
      const sharpeLike = std > 1e-9 ? mean / std : 0;

      // Calculate MaxDD
      let eq = 1;
      let peak = 1;
      let maxDD = 0;
      for (const p of pnls) {
        eq *= (1 + p);
        peak = Math.max(peak, eq);
        const dd = (peak - eq) / peak;
        maxDD = Math.max(maxDD, dd);
      }

      // Score calculation
      let score = 1.0;

      if (maxDD > 0.30) {
        score = 0.2;
        reasons.push('CAPITAL:MAXDD_GT30');
      } else if (maxDD > 0.20) {
        score = 0.4;
        reasons.push('CAPITAL:MAXDD_GT20');
      } else if (maxDD > 0.10) {
        score = 0.7;
      }

      if (mean < 0) {
        score -= 0.15;
        reasons.push('CAPITAL:NEG_EXPECTANCY');
      }

      if (sharpeLike < 0) {
        score -= 0.10;
        reasons.push('CAPITAL:NEG_SHARPE');
      }

      return {
        score: clamp01(score),
        raw: {
          trades: pnls.length,
          expectancy: mean,
          sharpeLike,
          maxDD,
        },
      };
    } catch (err) {
      console.error('[Exchange Reliability] Error computing capital health:', err);
      reasons.push('CAPITAL:ERROR');
      return { score: 0.6 };
    }
  }

  /**
   * Compute Calibration Health
   * For now returns neutral - can be enhanced with shadow vs active comparison
   */
  private async computeCalibrationHealth(reasons: string[]): Promise<{ score: number; raw?: any }> {
    try {
      const db = mongoose.connection.db;
      if (!db) return { score: 0.7 };

      // Check shadow performance if available
      const since = new Date(Date.now() - 14 * 24 * 3600_000);
      const shadows = await db.collection('exchange_shadow_predictions')
        .find({ resolvedAt: { $gte: since } })
        .toArray();

      if (!shadows.length) {
        return { score: 0.7, raw: { status: 'NO_SHADOW_DATA' } };
      }

      // Calculate shadow vs active accuracy
      let shadowCorrect = 0;
      let activeCorrect = 0;

      for (const s of shadows) {
        if (s.shadowCorrect) shadowCorrect++;
        if (s.activeCorrect) activeCorrect++;
      }

      const shadowAccuracy = shadows.length ? shadowCorrect / shadows.length : 0.5;
      const activeAccuracy = shadows.length ? activeCorrect / shadows.length : 0.5;
      const delta = shadowAccuracy - activeAccuracy;

      let score = 0.7;
      if (delta >= 0.02) {
        score = 1.0;
      } else if (delta >= -0.02) {
        score = 0.8;
      } else if (delta >= -0.07) {
        score = 0.5;
        reasons.push('CALIB:ML_UNDERPERFORMING');
      } else {
        score = 0.2;
        reasons.push('CALIB:ML_STRONG_UNDERPERFORM');
      }

      return {
        score,
        raw: {
          samples: shadows.length,
          shadowAccuracy,
          activeAccuracy,
          delta,
        },
      };
    } catch (err) {
      console.error('[Exchange Reliability] Error computing calibration health:', err);
      reasons.push('CALIB:ERROR');
      return { score: 0.6 };
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
   * Quick check if promotion is allowed
   */
  async isPromotionAllowed(): Promise<boolean> {
    const status = await this.computeStatus();
    return !status.actions.promotionBlocked;
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
let reliabilityServiceInstance: ExchangeReliabilityService | null = null;

export function getExchangeReliabilityService(): ExchangeReliabilityService {
  if (!reliabilityServiceInstance) {
    reliabilityServiceInstance = new ExchangeReliabilityService();
  }
  return reliabilityServiceInstance;
}

console.log('[Exchange-ML] Reliability Service loaded (EX-S1)');
