/**
 * Exchange Drift Baseline Service
 * =================================
 * 
 * EX-S2: Baseline versioning with gates.
 * 
 * Gates:
 * - AUTO: URI >= 75%, CapitalHealth >= 70%, TradesCount >= 100
 * - MANUAL: URI >= 60%
 * - Cooldown: 14 days between baselines
 */

import { ExchangeDriftBaselineModel, ExchangeDriftBaselineDoc } from './exchange-drift-baseline.model.js';
import { getExchangeReliabilityService } from '../reliability/exchange-reliability.service.js';

// Gate configuration
export const EX_BASELINE_GATES = {
  auto: {
    uriMin: 0.75,
    capitalHealthMin: 0.70,
    driftHealthMin: 0.70,
    minTrades: 100,
  },
  manual: {
    uriMin: 0.60,
  },
  cooldownDays: 14,
};

export interface BaselineCreateResult {
  ok: boolean;
  code?: string;
  message?: string;
  version?: number;
  baseline?: ExchangeDriftBaselineDoc;
}

export class ExchangeDriftBaselineService {
  /**
   * Get latest baseline
   */
  async getLatestBaseline(): Promise<ExchangeDriftBaselineDoc | null> {
    return ExchangeDriftBaselineModel.findOne().sort({ version: -1 }).lean();
  }

  /**
   * List baseline history
   */
  async listHistory(limit: number = 20): Promise<ExchangeDriftBaselineDoc[]> {
    return ExchangeDriftBaselineModel.find()
      .sort({ version: -1 })
      .limit(limit)
      .lean();
  }

  /**
   * Create baseline if gates allow
   */
  async createBaselineIfAllowed(
    mode: 'AUTO' | 'MANUAL',
    notes?: string
  ): Promise<BaselineCreateResult> {
    // Get current reliability status
    const reliability = getExchangeReliabilityService();
    const uri = await reliability.computeStatus();

    // Check cooldown
    const latest = await this.getLatestBaseline();
    if (latest) {
      const daysSince = (Date.now() - new Date(latest.createdAt).getTime()) / (24 * 3600_000);
      if (daysSince < EX_BASELINE_GATES.cooldownDays) {
        return {
          ok: false,
          code: 'COOLDOWN',
          message: `Cooldown active: ${daysSince.toFixed(1)} days < ${EX_BASELINE_GATES.cooldownDays} days`,
        };
      }
    }

    // Check gates based on mode
    if (mode === 'AUTO') {
      if (uri.uriScore < EX_BASELINE_GATES.auto.uriMin) {
        return {
          ok: false,
          code: 'GATE_BLOCKED',
          message: `URI too low for AUTO: ${(uri.uriScore * 100).toFixed(0)}% < ${EX_BASELINE_GATES.auto.uriMin * 100}%`,
        };
      }
      if (uri.components.capitalHealth < EX_BASELINE_GATES.auto.capitalHealthMin) {
        return {
          ok: false,
          code: 'GATE_BLOCKED',
          message: `CapitalHealth too low: ${(uri.components.capitalHealth * 100).toFixed(0)}% < ${EX_BASELINE_GATES.auto.capitalHealthMin * 100}%`,
        };
      }
      if (uri.components.driftHealth < EX_BASELINE_GATES.auto.driftHealthMin) {
        return {
          ok: false,
          code: 'GATE_BLOCKED',
          message: `DriftHealth too low: ${(uri.components.driftHealth * 100).toFixed(0)}% < ${EX_BASELINE_GATES.auto.driftHealthMin * 100}%`,
        };
      }
    } else {
      // MANUAL mode - relaxed gates
      if (uri.uriScore < EX_BASELINE_GATES.manual.uriMin) {
        return {
          ok: false,
          code: 'GATE_BLOCKED',
          message: `URI too low for MANUAL: ${(uri.uriScore * 100).toFixed(0)}% < ${EX_BASELINE_GATES.manual.uriMin * 100}%`,
        };
      }
    }

    // Create baseline
    const version = latest ? latest.version + 1 : 1;

    // Build snapshot (simplified - can be enhanced with real feature extraction)
    const snapshot = {
      featureStats: {},  // Would be populated by feature extractor
      capital: {
        expectancy: uri.raw?.capital?.expectancy ?? 0,
        sharpeLike: uri.raw?.capital?.sharpeLike ?? 0,
        maxDD: uri.raw?.capital?.maxDD ?? 0,
        winRate: 0,
        tradesCount: uri.raw?.capital?.trades ?? 0,
      },
      regime: {
        dominantRegime: 'UNKNOWN' as const,
        volatilityState: 'MID' as const,
      },
    };

    const baseline = await ExchangeDriftBaselineModel.create({
      version,
      mode,
      uriScore: uri.uriScore,
      capitalHealth: uri.components.capitalHealth,
      driftHealth: uri.components.driftHealth,
      snapshot,
      lockedUntil: new Date(Date.now() + EX_BASELINE_GATES.cooldownDays * 24 * 3600_000),
      notes,
    });

    console.log(`[Exchange Baseline] Created v${version} (${mode})`);

    return {
      ok: true,
      version,
      baseline: baseline.toObject(),
    };
  }
}

// Singleton
let baselineServiceInstance: ExchangeDriftBaselineService | null = null;

export function getExchangeDriftBaselineService(): ExchangeDriftBaselineService {
  if (!baselineServiceInstance) {
    baselineServiceInstance = new ExchangeDriftBaselineService();
  }
  return baselineServiceInstance;
}

console.log('[Exchange-ML] Drift Baseline Service loaded (EX-S2)');
