/**
 * Exchange Drift Stabilizer Service
 * ===================================
 * 
 * EX-S3: EMA smoothing + persistence for stable drift detection.
 * 
 * Key features:
 * - EMA smoothing of PSI to avoid noise
 * - Streak counters (WARN=3, DEGRADED=2, CRITICAL=1)
 * - Actions binding (confidence/size multipliers, training blocking)
 */

import { ExchangeDriftStateModel, ExchangeDriftStateDoc } from './exchange-drift-state.model.js';
import { getExchangeDriftBaselineService } from './exchange-drift-baseline.service.js';

export type DriftStatus = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL';

export interface DriftStabilizerConfig {
  emaAlpha: number;
  psiOkMax: number;
  psiWarnMax: number;
  psiDegradedMax: number;
  persistWarn: number;
  persistDegraded: number;
  persistCritical: number;
}

const DEFAULT_CONFIG: DriftStabilizerConfig = {
  emaAlpha: 0.2,
  psiOkMax: 0.15,
  psiWarnMax: 0.30,
  psiDegradedMax: 0.50,
  persistWarn: 3,
  persistDegraded: 2,
  persistCritical: 1,
};

export interface DriftActions {
  trainingBlocked: boolean;
  workersBlocked: boolean;
  confidenceMultiplier: number;
  sizeMultiplier: number;
}

export interface DriftRunInput {
  psiByFeature?: Record<string, number>;
  psiRaw?: number;  // Direct PSI value
  baselineVersion?: number | null;
}

export interface DriftRunOutput {
  rawStatus: DriftStatus;
  emaStatus: DriftStatus;
  stabilizedStatus: DriftStatus;
  psiRaw: number;
  psiEma: number;
  psiEmaByFeature: Record<string, number>;
  streaks: { warn: number; degraded: number; critical: number };
  actions: DriftActions;
}

export class ExchangeDriftStabilizerService {
  private config: DriftStabilizerConfig;

  constructor(config?: Partial<DriftStabilizerConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Convert PSI to status
   */
  private statusFromPsi(psi: number): DriftStatus {
    if (psi < this.config.psiOkMax) return 'OK';
    if (psi < this.config.psiWarnMax) return 'WARN';
    if (psi < this.config.psiDegradedMax) return 'DEGRADED';
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
          trainingBlocked: false,
          workersBlocked: false,
          confidenceMultiplier: 1.0,
          sizeMultiplier: 1.0,
        };
      case 'WARN':
        return {
          trainingBlocked: false,
          workersBlocked: false,
          confidenceMultiplier: 0.9,
          sizeMultiplier: 0.85,
        };
      case 'DEGRADED':
        return {
          trainingBlocked: true,
          workersBlocked: false,
          confidenceMultiplier: 0.7,
          sizeMultiplier: 0.5,
        };
      case 'CRITICAL':
        return {
          trainingBlocked: true,
          workersBlocked: true,
          confidenceMultiplier: 0.5,
          sizeMultiplier: 0.25,
        };
    }
  }

  /**
   * Run drift stabilization
   */
  async run(input: DriftRunInput): Promise<DriftRunOutput> {
    const key = 'default';
    const { psiByFeature = {}, psiRaw: inputPsiRaw, baselineVersion } = input;

    // Get or create state
    let state = await ExchangeDriftStateModel.findOne({ key }).lean();
    if (!state) {
      await ExchangeDriftStateModel.create({ key });
      state = await ExchangeDriftStateModel.findOne({ key }).lean();
    }

    // Determine raw PSI (either from input or from feature map)
    const psiRaw = inputPsiRaw ?? this.maxPsi(psiByFeature);

    // 1) Raw status
    const rawStatus = this.statusFromPsi(psiRaw);

    // 2) EMA update
    const prevPsiEma = (state as any)?.psiEma ?? 0;
    const psiEma = this.ema(prevPsiEma, psiRaw);

    // EMA per feature
    const prevEmaByFeature = (state as any)?.psiEmaByFeature || {};
    const nextEmaByFeature: Record<string, number> = {};
    for (const [feat, psi] of Object.entries(psiByFeature)) {
      nextEmaByFeature[feat] = this.ema(prevEmaByFeature[feat], psi);
    }

    // 3) EMA status
    const emaStatus = this.statusFromPsi(psiEma);

    // 4) Update persistence counters
    let warnStreak = (state as any)?.warnStreak || 0;
    let degradedStreak = (state as any)?.degradedStreak || 0;
    let criticalStreak = (state as any)?.criticalStreak || 0;

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

    // 5) Stabilized status by persistence
    let stabilizedStatus: DriftStatus = 'OK';
    if (criticalStreak >= this.config.persistCritical) {
      stabilizedStatus = 'CRITICAL';
    } else if (degradedStreak >= this.config.persistDegraded) {
      stabilizedStatus = 'DEGRADED';
    } else if (warnStreak >= this.config.persistWarn) {
      stabilizedStatus = 'WARN';
    }

    // 6) Get actions
    const actions = this.statusToActions(stabilizedStatus);

    // 7) Persist state
    await ExchangeDriftStateModel.updateOne(
      { key },
      {
        $set: {
          baselineVersion: baselineVersion ?? (state as any)?.baselineVersion ?? null,
          psiLastByFeature: psiByFeature,
          psiEmaByFeature: nextEmaByFeature,
          psiRaw,
          psiEma,
          lastRawStatus: rawStatus,
          lastEmaStatus: emaStatus,
          lastStabilizedStatus: stabilizedStatus,
          warnStreak,
          degradedStreak,
          criticalStreak,
          actions,
          lastRunAt: new Date(),
        },
      },
      { upsert: true }
    );

    console.log(`[ExDriftStabilizer] raw=${rawStatus}, ema=${emaStatus}, stabilized=${stabilizedStatus}, streaks={W:${warnStreak},D:${degradedStreak},C:${criticalStreak}}`);

    return {
      rawStatus,
      emaStatus,
      stabilizedStatus,
      psiRaw,
      psiEma,
      psiEmaByFeature: nextEmaByFeature,
      streaks: { warn: warnStreak, degraded: degradedStreak, critical: criticalStreak },
      actions,
    };
  }

  /**
   * Get current state (without running)
   */
  async getState(): Promise<DriftRunOutput | null> {
    const state = await ExchangeDriftStateModel.findOne({ key: 'default' }).lean();
    if (!state) return null;

    const s = state as any;
    const status = (s.lastStabilizedStatus || 'OK') as DriftStatus;

    return {
      rawStatus: (s.lastRawStatus || 'OK') as DriftStatus,
      emaStatus: (s.lastEmaStatus || 'OK') as DriftStatus,
      stabilizedStatus: status,
      psiRaw: s.psiRaw || 0,
      psiEma: s.psiEma || 0,
      psiEmaByFeature: s.psiEmaByFeature || {},
      streaks: {
        warn: s.warnStreak || 0,
        degraded: s.degradedStreak || 0,
        critical: s.criticalStreak || 0,
      },
      actions: s.actions || this.statusToActions(status),
    };
  }

  /**
   * Reset streaks
   */
  async resetStreaks(): Promise<void> {
    await ExchangeDriftStateModel.updateOne(
      { key: 'default' },
      {
        $set: {
          warnStreak: 0,
          degradedStreak: 0,
          criticalStreak: 0,
          lastStabilizedStatus: 'OK',
          actions: this.statusToActions('OK'),
        },
      }
    );
  }
}

// Singleton
let stabilizerInstance: ExchangeDriftStabilizerService | null = null;

export function getExchangeDriftStabilizerService(): ExchangeDriftStabilizerService {
  if (!stabilizerInstance) {
    stabilizerInstance = new ExchangeDriftStabilizerService();
  }
  return stabilizerInstance;
}

console.log('[Exchange-ML] Drift Stabilizer Service loaded (EX-S3)');
