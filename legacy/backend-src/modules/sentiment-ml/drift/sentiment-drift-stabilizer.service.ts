/**
 * Sentiment Drift Stabilizer Service
 * =====================================
 * 
 * BLOCK S3: EMA smoothing + persistence for stable drift detection.
 * 
 * Key features:
 * - EMA smoothing of PSI to avoid noise
 * - Streak counters for persistence (don't react to single spikes)
 * - Actions binding (confidence/size multipliers, training blocking)
 * - Baseline age tracking
 */

import { DriftStabilizerConfig, DEFAULT_DRIFT_STABILIZER_CONFIG } from './drift.config.js';
import { SentimentDriftStateModel, SentimentDriftStateDoc } from './sentiment-drift-state.model.js';
import { getSentimentDriftBaselineService } from './sentiment-drift-baseline.service.js';

export type DriftStatus = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';

export interface DriftActions {
  confidenceMultiplier: number;
  sizeMultiplier: number;
  trainingBlocked: boolean;
  promotionBlocked: boolean;
}

export interface DriftRunInput {
  window: '24H' | '7D' | '30D';
  psiByFeature: Record<string, number>;
  baselineVersion?: number | null;
  now?: Date;
}

export interface DriftRunOutput {
  rawStatus: DriftStatus;
  emaStatus: DriftStatus;
  stabilizedStatus: DriftStatus;
  psiEmaByFeature: Record<string, number>;
  streaks: { warn: number; degraded: number; critical: number };
  actions: DriftActions;
  baselineAge: { days: number; isStale: boolean; needsRefresh: boolean } | null;
}

export class SentimentDriftStabilizerService {
  private config: DriftStabilizerConfig;

  constructor(config?: Partial<DriftStabilizerConfig>) {
    this.config = { ...DEFAULT_DRIFT_STABILIZER_CONFIG, ...config };
  }

  /**
   * Convert max PSI to status
   */
  private statusFromPsi(maxPsi: number): DriftStatus {
    if (maxPsi < this.config.psiOkMax) return 'OK';
    if (maxPsi < this.config.psiWarnMax) return 'WARN';
    if (maxPsi < this.config.psiDegradedMax) return 'DEGRADED';
    return 'CRITICAL';
  }

  /**
   * Get max PSI from feature map
   */
  private maxPsi(map: Record<string, number>): number {
    let max = 0;
    for (const v of Object.values(map)) {
      if (v > max) max = v;
    }
    return max;
  }

  /**
   * EMA calculation
   */
  private ema(prev: number | undefined, next: number): number {
    if (prev === undefined || Number.isNaN(prev)) return next;
    return this.config.emaAlpha * next + (1 - this.config.emaAlpha) * prev;
  }

  /**
   * Map status to actions
   */
  private statusToActions(status: DriftStatus): DriftActions {
    switch (status) {
      case 'OK':
        return {
          confidenceMultiplier: 1.0,
          sizeMultiplier: 1.0,
          trainingBlocked: false,
          promotionBlocked: false,
        };
      case 'WARN':
        return {
          confidenceMultiplier: 0.9,
          sizeMultiplier: 0.85,
          trainingBlocked: false,
          promotionBlocked: false,
        };
      case 'DEGRADED':
        return {
          confidenceMultiplier: 0.7,
          sizeMultiplier: 0.5,
          trainingBlocked: true,
          promotionBlocked: true,
        };
      case 'CRITICAL':
        return {
          confidenceMultiplier: 0.5,
          sizeMultiplier: 0.25,
          trainingBlocked: true,
          promotionBlocked: true,
        };
    }
  }

  /**
   * Check baseline age
   */
  private async getBaselineAge(window: '24H' | '7D' | '30D'): Promise<{ days: number; isStale: boolean; needsRefresh: boolean } | null> {
    try {
      const baselineSvc = getSentimentDriftBaselineService();
      const baseline = await baselineSvc.getLatestBaseline(window);
      
      if (!baseline) return null;

      const ageDays = (Date.now() - new Date(baseline.createdAt).getTime()) / (24 * 3600_000);
      
      return {
        days: Math.round(ageDays * 10) / 10,
        isStale: ageDays >= this.config.maxBaselineAgeDays,
        needsRefresh: ageDays >= this.config.baselineAgeWarnDays,
      };
    } catch {
      return null;
    }
  }

  /**
   * Run drift stabilization
   */
  async run(input: DriftRunInput): Promise<DriftRunOutput> {
    const { window, psiByFeature, now = new Date() } = input;
    const key = window;

    // Get or create state
    let state = await SentimentDriftStateModel.findOne({ key }).lean();
    if (!state) {
      await SentimentDriftStateModel.create({ key });
      state = await SentimentDriftStateModel.findOne({ key }).lean();
    }

    // 1) Raw status from current PSI
    const rawMax = this.maxPsi(psiByFeature);
    const rawStatus = this.statusFromPsi(rawMax);

    // 2) EMA update per feature
    const prevEma = (state as any)?.psiEmaByFeature || {};
    const nextEma: Record<string, number> = {};
    for (const [feat, psi] of Object.entries(psiByFeature)) {
      nextEma[feat] = this.ema(prevEma[feat], psi);
    }

    // 3) EMA status
    const emaMax = this.maxPsi(nextEma);
    const emaStatus = this.statusFromPsi(emaMax);

    // 4) Update persistence counters
    let warnStreak = (state as any)?.warnStreak || 0;
    let degradedStreak = (state as any)?.degradedStreak || 0;
    let criticalStreak = (state as any)?.criticalStreak || 0;

    // Reset rules: streak counts only for current severity
    if (emaStatus === 'WARN') {
      warnStreak += 1;
      degradedStreak = 0;
      criticalStreak = 0;
    } else if (emaStatus === 'DEGRADED') {
      degradedStreak += 1;
      warnStreak = 0;
      criticalStreak = 0;
    } else if (emaStatus === 'CRITICAL') {
      criticalStreak += 1;
      warnStreak = 0;
      degradedStreak = 0;
    } else {
      // OK - reset all
      warnStreak = 0;
      degradedStreak = 0;
      criticalStreak = 0;
    }

    // 5) Stabilized status by persistence thresholds
    let stabilizedStatus: DriftStatus = 'OK';
    if (criticalStreak >= this.config.persistCritical) {
      stabilizedStatus = 'CRITICAL';
    } else if (degradedStreak >= this.config.persistDegraded) {
      stabilizedStatus = 'DEGRADED';
    } else if (warnStreak >= this.config.persistWarn) {
      stabilizedStatus = 'WARN';
    }

    // 6) Get actions for stabilized status
    const actions = this.statusToActions(stabilizedStatus);

    // 7) Check baseline age
    const baselineAge = await this.getBaselineAge(window);

    // 8) Persist state
    await SentimentDriftStateModel.updateOne(
      { key },
      {
        $set: {
          baselineVersion: input.baselineVersion ?? (state as any)?.baselineVersion ?? null,
          psiLastByFeature: psiByFeature,
          psiEmaByFeature: nextEma,
          lastRawStatus: rawStatus,
          lastEmaStatus: emaStatus,
          lastStabilizedStatus: stabilizedStatus,
          warnStreak,
          degradedStreak,
          criticalStreak,
          lastRunAt: now,
        },
      },
      { upsert: true }
    );

    console.log(`[DriftStabilizer] ${window}: raw=${rawStatus}, ema=${emaStatus}, stabilized=${stabilizedStatus}, streaks={W:${warnStreak},D:${degradedStreak},C:${criticalStreak}}`);

    return {
      rawStatus,
      emaStatus,
      stabilizedStatus,
      psiEmaByFeature: nextEma,
      streaks: { warn: warnStreak, degraded: degradedStreak, critical: criticalStreak },
      actions,
      baselineAge,
    };
  }

  /**
   * Get current state (without running)
   */
  async getState(window: '24H' | '7D' | '30D'): Promise<DriftRunOutput | null> {
    const state = await SentimentDriftStateModel.findOne({ key: window }).lean();
    if (!state) return null;

    const s = state as any;
    const status = (s.lastStabilizedStatus || 'OK') as DriftStatus;
    const baselineAge = await this.getBaselineAge(window);

    return {
      rawStatus: (s.lastRawStatus || 'OK') as DriftStatus,
      emaStatus: (s.lastEmaStatus || 'OK') as DriftStatus,
      stabilizedStatus: status,
      psiEmaByFeature: s.psiEmaByFeature || {},
      streaks: {
        warn: s.warnStreak || 0,
        degraded: s.degradedStreak || 0,
        critical: s.criticalStreak || 0,
      },
      actions: this.statusToActions(status),
      baselineAge,
    };
  }

  /**
   * Reset streaks (for testing or manual intervention)
   */
  async resetStreaks(window: '24H' | '7D' | '30D'): Promise<void> {
    await SentimentDriftStateModel.updateOne(
      { key: window },
      {
        $set: {
          warnStreak: 0,
          degradedStreak: 0,
          criticalStreak: 0,
          lastStabilizedStatus: 'OK',
        },
      }
    );
  }
}

// Singleton
let stabilizerInstance: SentimentDriftStabilizerService | null = null;

export function getSentimentDriftStabilizer(): SentimentDriftStabilizerService {
  if (!stabilizerInstance) {
    stabilizerInstance = new SentimentDriftStabilizerService();
  }
  return stabilizerInstance;
}

console.log('[Sentiment-ML] Drift Stabilizer Service loaded (BLOCK S3)');
