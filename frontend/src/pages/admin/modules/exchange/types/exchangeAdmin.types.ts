/**
 * Exchange Admin Types (Frontend)
 * =================================
 * 
 * BLOCK E6: TypeScript types for Exchange Admin dashboard
 * 1:1 parity with Sentiment Admin types
 */

export type ReliabilityLevel = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL' | 'UNKNOWN';

export interface ModuleManifestMini {
  moduleKey: 'exchange';
  version: string;
  frozen: boolean;
  frozenAt?: string;
  featureMode?: string;
}

export interface UriComponent {
  score: number;
  level: ReliabilityLevel;
  reasons?: string[];
}

export interface UriStatus {
  uriScore: number;
  uriLevel: ReliabilityLevel;
  components: {
    dataHealth: UriComponent;
    driftHealth: UriComponent;
    capitalHealth: UriComponent;
    calibrationHealth: UriComponent;
  };
  actions: {
    trainingBlocked: boolean;
    promotionBlocked: boolean;
    workersEnabled: boolean;
    confidenceMultiplier: number;
    sizeMultiplier: number;
    safeMode: boolean;
    safeModeReason?: string;
  };
}

export interface DataHealthStatus {
  level: ReliabilityLevel;
  reasons: string[];
  lastCandleAt?: string;
  candlesLagSec?: number;
  provider?: string;
  fetchErrors24h?: number;
  coveragePct?: number;
}

export interface DriftStatus {
  level: ReliabilityLevel;
  psiNow?: number;
  psiEma?: number;
  emaAlpha?: number;
  streakWarn?: number;
  streakDegraded?: number;
  streakCritical?: number;
  lastBaselineVersion?: string;
  lastBaselineAt?: string;
  recentPsi?: number[];
  stabilizedStatus?: string;
}

export interface CapitalWindow {
  level: ReliabilityLevel;
  trades30d: number;
  return30d: number;
  expectancy: number;
  maxDD: number;
  sharpe: number;
  winRate?: number;
  equity?: number;
  gates: {
    promotionEligible: boolean;
    reasons: string[];
  };
  recentEquity?: number[];
}

export interface LifecycleStatus {
  mode: 'RULE' | 'ML';
  activeModelVersion?: string;
  shadowStatus?: ReliabilityLevel;
  edgeDelta?: number;
  divergence?: number;
  shadowDecisions?: number;
  lastPromotionAt?: string;
  rollbackCooldown?: {
    active: boolean;
    remainingDays?: number;
  };
}

export interface CalibrationBucket {
  range: string;
  predicted: number;
  actual: number;
  samples: number;
}

export interface CalibrationStatus {
  level: ReliabilityLevel;
  ece?: number;
  buckets?: CalibrationBucket[];
  lastRunAt?: string;
  totalSamples?: number;
}

export interface EvidenceEvent {
  _id?: string;
  timestamp: string;
  eventType: string;
  moduleKey: string;
  payload?: any;
  fieldsCount?: number;
}

export interface FeatureLockStatus {
  locked: boolean;
  lockedUntil?: string;
  lockedBy?: string;
  remainingMinutes?: number;
}

export interface ExchangeAdminSnapshot {
  ok: true;
  manifest: ModuleManifestMini;
  uri: UriStatus;
  dataHealth: DataHealthStatus;
  drift: DriftStatus;
  capital: CapitalWindow;
  lifecycle: LifecycleStatus;
  calibration: CalibrationStatus;
  evidence: EvidenceEvent[];
  featureLock: FeatureLockStatus;
}
