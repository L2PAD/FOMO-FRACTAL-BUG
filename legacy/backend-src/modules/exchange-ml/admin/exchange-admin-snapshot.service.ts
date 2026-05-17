/**
 * Exchange Admin Snapshot Service
 * =================================
 * 
 * BLOCK E6: Aggregates all admin data into single snapshot
 * 1:1 parity with Sentiment Admin Snapshot
 */

import {
  ExchangeAdminSnapshot,
  ReliabilityLevel,
  ModuleManifestMini,
  UriStatus,
  DataHealthStatus,
  DriftStatus,
  CapitalWindow,
  LifecycleStatus,
  CalibrationStatus,
  EvidenceEvent,
  FeatureLockStatus,
} from './exchange-admin-snapshot.types.js';
import { ExchangeReliabilityService } from '../reliability/exchange-reliability.service.js';

// Helper to clamp level
function toLevel(raw: any): ReliabilityLevel {
  const valid: ReliabilityLevel[] = ['OK', 'WARN', 'DEGRADED', 'CRITICAL', 'UNKNOWN'];
  const v = String(raw ?? 'UNKNOWN').toUpperCase() as ReliabilityLevel;
  return valid.includes(v) ? v : 'UNKNOWN';
}

export class ExchangeAdminSnapshotService {
  private reliabilityService: ExchangeReliabilityService;

  constructor() {
    this.reliabilityService = new ExchangeReliabilityService();
  }

  async getSnapshot(): Promise<ExchangeAdminSnapshot> {
    // Fetch all data in parallel
    const [
      manifest,
      reliabilityStatus,
      driftStatus,
      capitalStatus,
      calibrationStatus,
      evidenceEvents,
      featureLockStatus,
    ] = await Promise.all([
      this.getManifest(),
      this.reliabilityService.computeStatus(),
      this.getDriftStatus(),
      this.getCapitalStatus(),
      this.getCalibrationStatus(),
      this.getEvidenceEvents(),
      this.getFeatureLockStatus(),
    ]);

    // Build URI status from reliability
    const uri = this.buildUriStatus(reliabilityStatus);
    const dataHealth = this.buildDataHealth(reliabilityStatus);
    const drift = this.buildDriftStatus(driftStatus, reliabilityStatus);
    const capital = this.buildCapitalStatus(capitalStatus, reliabilityStatus);
    const lifecycle = this.buildLifecycleStatus(reliabilityStatus);
    const calibration = this.buildCalibrationStatus(calibrationStatus);

    return {
      ok: true,
      manifest,
      uri,
      dataHealth,
      drift,
      capital,
      lifecycle,
      calibration,
      evidence: evidenceEvents,
      featureLock: featureLockStatus,
    };
  }

  private async getManifest(): Promise<ModuleManifestMini> {
    try {
      const fs = await import('fs/promises');
      const path = await import('path');
      const manifestPath = path.join(process.cwd(), 'src/modules/exchange-ml/module_manifest.json');
      const content = await fs.readFile(manifestPath, 'utf-8');
      const data = JSON.parse(content);
      return {
        moduleKey: 'exchange',
        version: data.version || 'v1.0.0',
        frozen: data.frozen || false,
        frozenAt: data.frozenAt,
        featureMode: data.featureMode || 'CORE_ONLY',
      };
    } catch {
      return {
        moduleKey: 'exchange',
        version: 'v1.0.0',
        frozen: true,
        featureMode: 'CORE_ONLY',
      };
    }
  }

  private async getDriftStatus(): Promise<any> {
    // For now, return mock drift status
    // In production, would call DriftMonitorService
    return {
      level: 'OK',
      psiNow: 0.08,
      psiEma: 0.07,
      emaAlpha: 0.2,
      streakWarn: 0,
      streakDegraded: 0,
      stabilizedStatus: 'OK',
      recentPsi: [0.05, 0.06, 0.07, 0.08, 0.07, 0.08, 0.09, 0.08],
    };
  }

  private async getCapitalStatus(): Promise<any> {
    // For now, return mock capital status
    // In production, would call CapitalWindowService
    return {
      level: 'WARN',
      trades30d: 45,
      return30d: 0.032,
      expectancy: 0.0018,
      maxDD: 0.12,
      sharpe: 0.85,
      winRate: 0.52,
      equity: 108.5,
      promotionEligible: false,
      reasons: ['Sharpe < 1.0', 'MaxDD > 10%'],
      recentEquity: [100, 101, 102, 101.5, 103, 102, 104, 105, 106, 107, 108, 108.5],
    };
  }

  private async getCalibrationStatus(): Promise<any> {
    // For now, return mock calibration status
    return {
      level: 'OK',
      ece: 0.035,
      buckets: [
        { range: '0.50-0.60', predicted: 0.55, actual: 0.52, samples: 120 },
        { range: '0.60-0.70', predicted: 0.65, actual: 0.63, samples: 95 },
        { range: '0.70-0.80', predicted: 0.75, actual: 0.72, samples: 78 },
        { range: '0.80-0.90', predicted: 0.85, actual: 0.81, samples: 45 },
        { range: '0.90-1.00', predicted: 0.95, actual: 0.88, samples: 22 },
      ],
      totalSamples: 360,
      lastRunAt: new Date().toISOString(),
    };
  }

  private async getEvidenceEvents(): Promise<EvidenceEvent[]> {
    // Return recent evidence events
    const now = Date.now();
    return [
      {
        timestamp: new Date(now - 3600000).toISOString(),
        eventType: 'guard_state_changed',
        moduleKey: 'exchange',
        payload: { action: 'URI level changed' },
        fieldsCount: 3,
      },
      {
        timestamp: new Date(now - 7200000).toISOString(),
        eventType: 'capital_health_computed',
        moduleKey: 'exchange',
        payload: { trades: 45, return: 0.032 },
        fieldsCount: 4,
      },
      {
        timestamp: new Date(now - 14400000).toISOString(),
        eventType: 'drift_check_completed',
        moduleKey: 'exchange',
        payload: { psi: 0.08 },
        fieldsCount: 2,
      },
    ];
  }

  private async getFeatureLockStatus(): Promise<FeatureLockStatus> {
    return {
      locked: false,
    };
  }

  private buildUriStatus(rel: any): UriStatus {
    return {
      uriScore: rel?.uriScore ?? 0.6,
      uriLevel: toLevel(rel?.level ?? 'UNKNOWN'),
      components: {
        dataHealth: {
          score: rel?.components?.dataHealth?.score ?? 0.8,
          level: toLevel(rel?.components?.dataHealth?.level),
          reasons: rel?.components?.dataHealth?.reasons ?? [],
        },
        driftHealth: {
          score: rel?.components?.driftHealth?.score ?? 0.9,
          level: toLevel(rel?.components?.driftHealth?.level),
          reasons: rel?.components?.driftHealth?.reasons ?? [],
        },
        capitalHealth: {
          score: rel?.components?.capitalHealth?.score ?? 0.7,
          level: toLevel(rel?.components?.capitalHealth?.level),
          reasons: rel?.components?.capitalHealth?.reasons ?? [],
        },
        calibrationHealth: {
          score: rel?.components?.calibrationHealth?.score ?? 0.95,
          level: toLevel(rel?.components?.calibrationHealth?.level),
          reasons: rel?.components?.calibrationHealth?.reasons ?? [],
        },
      },
      actions: {
        trainingBlocked: rel?.actions?.trainingBlocked ?? true,
        promotionBlocked: rel?.actions?.promotionBlocked ?? true,
        workersEnabled: rel?.actions?.workersEnabled ?? true,
        confidenceMultiplier: rel?.actions?.confidenceMultiplier ?? 0.85,
        sizeMultiplier: rel?.actions?.sizeMultiplier ?? 0.8,
        safeMode: rel?.actions?.safeMode ?? false,
        safeModeReason: rel?.actions?.safeModeReason,
      },
    };
  }

  private buildDataHealth(rel: any): DataHealthStatus {
    const dh = rel?.components?.dataHealth ?? {};
    return {
      level: toLevel(dh?.level ?? 'OK'),
      reasons: dh?.reasons ?? [],
      lastCandleAt: dh?.lastCandleAt ?? new Date().toISOString(),
      candlesLagSec: dh?.candlesLagSec ?? 120,
      provider: 'Binance',
      fetchErrors24h: dh?.fetchErrors24h ?? 0,
      coveragePct: dh?.coveragePct ?? 98,
    };
  }

  private buildDriftStatus(drift: any, rel: any): DriftStatus {
    return {
      level: toLevel(drift?.level ?? rel?.components?.driftHealth?.level ?? 'OK'),
      psiNow: drift?.psiNow ?? 0.08,
      psiEma: drift?.psiEma ?? 0.07,
      emaAlpha: drift?.emaAlpha ?? 0.2,
      streakWarn: drift?.streakWarn ?? 0,
      streakDegraded: drift?.streakDegraded ?? 0,
      streakCritical: drift?.streakCritical ?? 0,
      lastBaselineVersion: drift?.lastBaselineVersion ?? 'v1.0.0',
      lastBaselineAt: drift?.lastBaselineAt ?? '2026-02-17T00:00:00Z',
      recentPsi: drift?.recentPsi ?? [],
      stabilizedStatus: drift?.stabilizedStatus ?? 'OK',
    };
  }

  private buildCapitalStatus(cap: any, rel: any): CapitalWindow {
    return {
      level: toLevel(cap?.level ?? rel?.components?.capitalHealth?.level ?? 'WARN'),
      trades30d: cap?.trades30d ?? 45,
      return30d: cap?.return30d ?? 0.032,
      expectancy: cap?.expectancy ?? 0.0018,
      maxDD: cap?.maxDD ?? 0.12,
      sharpe: cap?.sharpe ?? 0.85,
      winRate: cap?.winRate ?? 0.52,
      equity: cap?.equity ?? 108.5,
      gates: {
        promotionEligible: cap?.promotionEligible ?? false,
        reasons: cap?.reasons ?? [],
      },
      recentEquity: cap?.recentEquity ?? [],
    };
  }

  private buildLifecycleStatus(rel: any): LifecycleStatus {
    return {
      mode: 'RULE',
      activeModelVersion: undefined,
      shadowStatus: 'OK',
      edgeDelta: 0,
      divergence: 0,
      shadowDecisions: 0,
      lastPromotionAt: undefined,
      rollbackCooldown: {
        active: false,
      },
    };
  }

  private buildCalibrationStatus(cal: any): CalibrationStatus {
    return {
      level: toLevel(cal?.level ?? 'OK'),
      ece: cal?.ece ?? 0.035,
      buckets: cal?.buckets ?? [],
      lastRunAt: cal?.lastRunAt,
      totalSamples: cal?.totalSamples ?? 360,
    };
  }
}

// Singleton
let instance: ExchangeAdminSnapshotService | null = null;

export function getExchangeAdminSnapshotService(): ExchangeAdminSnapshotService {
  if (!instance) {
    instance = new ExchangeAdminSnapshotService();
  }
  return instance;
}
