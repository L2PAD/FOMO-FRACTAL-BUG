export type ReliabilityLevel = "OK" | "WARN" | "DEGRADED" | "CRITICAL" | "UNKNOWN";

export type ModuleMode = "RULE" | "ML";

export interface UriComponent {
  score: number; // 0..1
  level: ReliabilityLevel;
  reasons?: string[];
}

export interface UriStatus {
  uriScore: number; // 0..1
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
    workersBlocked: boolean;
    confidenceMultiplier: number; // 0..1
    sizeMultiplier: number; // 0..1
    safeMode: boolean;
    safeModeReason?: string;
  };
}

export interface ParserHealthStatus {
  level: ReliabilityLevel;
  reasons: string[];
  cookiesSessions: number;
  lastIngestAt?: string; // ISO
  lastTweetAt?: string; // ISO
  ingestionRatePerHour?: number;
  errorRate?: number;
}

export interface ModuleManifestMini {
  moduleKey: "sentiment" | string;
  version: string; // "v1.0.0"
  frozen: boolean;
  frozenAt?: string;
  featureMode?: string; // "CORE_ONLY"
}

export interface DriftStatus {
  psiRaw: number;
  psiEma: number;
  status: ReliabilityLevel;
  streakCount: number;
  baselineVersion: string;
  baselineCreatedAt?: string;
  baselineAge?: number; // days
  psiHistory?: number[]; // last 30 values for sparkline
}

export interface CapitalMetrics {
  trades: number;
  winRate: number;
  expectancy: number;
  maxDD: number;
  sharpe: number;
  equity: number;
  equityHistory?: number[]; // last 30 values for sparkline
}

export interface CapitalGates {
  promotionEligible: boolean;
  rollbackTriggered: boolean;
  promotionLockActive: boolean;
  promotionLockUntil?: string;
}

export interface LifecycleStatus {
  mode: ModuleMode;
  shadowDecisions: number;
  edgeDelta: number;
  cooldownRemainingDays: number;
  lastPromotion?: string;
  lastRollback?: string;
}

export interface CalibrationBucket {
  bucketMin: number;
  bucketMax: number;
  total: number;
  wins: number;
  posteriorMean: number;
}

export interface CalibrationStatus {
  ece: number;
  status: ReliabilityLevel;
  buckets?: CalibrationBucket[];
}

export interface EvidenceEvent {
  timestamp: string;
  module: string;
  type: string;
  severity: string;
  message: string;
  details: Record<string, any>;
}

export interface SentimentAdminSnapshot {
  manifest: ModuleManifestMini;
  uri: UriStatus;
  parserHealth: ParserHealthStatus;
  drift?: DriftStatus;
  capital?: CapitalMetrics;
  capitalGates?: CapitalGates;
  lifecycle?: LifecycleStatus;
  calibration?: CalibrationStatus;
  evidence?: EvidenceEvent[];
}

// Intelligence data types (from /api/market/sentiment/intelligence-v1)
export interface ConfidenceBucket {
  bucket: string;
  count: number;
}

export interface BiasDistribution {
  longPct: number;
  shortPct: number;
  neutralPct: number;
}

export interface SentimentIntelligenceData {
  regime: {
    marketRegime: string;
    trendStrength: number;
  };
  distribution: {
    confidenceHistogram: ConfidenceBucket[];
    biasDistribution: BiasDistribution;
  };
  performance: {
    mlEquity: number[];
    ruleEquity: number[];
    rollingHitRate: number;
    rollingSharpe: number;
  };
  stability: {
    uriAdjustmentsPct: number;
    safeModePct: number;
    calibrationAdjustmentsPct: number;
    lowDataPct: number;
  };
}
