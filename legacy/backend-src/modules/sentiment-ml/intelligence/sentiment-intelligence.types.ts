/**
 * Sentiment Intelligence Types
 * =============================
 * 
 * BLOCK P3: Types for Sentiment Intelligence Page
 * User-facing analytics, not admin
 */

export type ReliabilityLevel = 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL' | 'UNKNOWN';
export type MarketRegime = 'TREND' | 'RANGE' | 'UNKNOWN';

export interface ConfidenceBucket {
  bucket: string;
  count: number;
}

export interface BiasDistribution {
  longPct: number;
  shortPct: number;
  neutralPct: number;
}

export interface DriftTimelinePoint {
  date: string;
  level: ReliabilityLevel;
}

export interface SentimentIntelligenceDTO {
  regime: {
    marketRegime: MarketRegime;
    trendStrength: number;
  };

  reliability: {
    uriScore: number;
    uriLevel: ReliabilityLevel;
    safeMode: boolean;
    confidenceMultiplier: number;
    sizeMultiplier: number;
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

  capital: {
    return30d: number;
    maxDD: number;
    expectancy: number;
    trades: number;
    winRate: number;
  };

  stability: {
    uriAdjustmentsPct: number;
    safeModePct: number;
    calibrationAdjustmentsPct: number;
    lowDataPct: number;
  };

  driftTimeline: DriftTimelinePoint[];
}

export interface SentimentIntelligenceResponse {
  ok: true;
  data: SentimentIntelligenceDTO;
  generatedAt: string;
}
