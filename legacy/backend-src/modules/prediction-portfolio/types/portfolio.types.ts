/**
 * Portfolio Brain Types — Stage 7
 *
 * Type definitions for Portfolio Brain: factor profiles, cluster overlap,
 * correlation penalties, risk budget, and portfolio assessment.
 */

// ══════════════════════════════════════
// Factor Profile
// ══════════════════════════════════════

export type FactorProfile = {
  assetFactors: string[];
  themeFactors: string[];
  catalystFactors: string[];
  deadlineFactors: string[];
  resolutionFactors: string[];
  entityFactors: string[];
};

// ══════════════════════════════════════
// Candidate Case (input to Portfolio Brain)
// ══════════════════════════════════════

export type CandidateCase = {
  marketId: string;
  question: string;
  asset: string;
  eventType: string;
  direction: 'long' | 'short' | 'neutral';

  edge: number;
  confidence: number;
  alignment: number;
  resolutionRisk: number;

  recommendationAction: string;
  baseSizeFraction: number;

  factorProfile: FactorProfile;

  // Optional metadata
  endDate?: string;
  entities?: string[];
  threshold?: number;
  comparator?: string;
};

// ══════════════════════════════════════
// Active Position
// ══════════════════════════════════════

export type ActivePosition = {
  marketId: string;
  question: string;
  asset: string;
  direction: 'long' | 'short' | 'neutral';
  sizeFraction: number;

  factorProfile: FactorProfile;
};

// ══════════════════════════════════════
// Cluster Overlap Result
// ══════════════════════════════════════

export type ClusterOverlap = {
  positionMarketId: string;
  rawOverlap: number;
  directionAdjustedOverlap: number;
  breakdown: {
    asset: number;
    theme: number;
    catalyst: number;
    deadline: number;
    resolution: number;
    entity: number;
  };
};

// ══════════════════════════════════════
// Correlation Result
// ══════════════════════════════════════

export type CorrelationResult = {
  penalty: number;
  blocked: boolean;
  reason?: string;
  maxOverlap: number;
  overlaps: ClusterOverlap[];
};

// ══════════════════════════════════════
// Risk Budget Result
// ══════════════════════════════════════

export type RiskBudgetResult = {
  penalty: number;
  blocked: boolean;
  reasons: string[];

  totalExposure: number;
  entityExposures: Record<string, number>;
  themeExposures: Record<string, number>;
};

// ══════════════════════════════════════
// Exposure Summary
// ══════════════════════════════════════

export type ExposureSummary = {
  totalExposure: number;
  byAsset: Record<string, number>;
  byTheme: Record<string, number>;
  byEntity: Record<string, number>;
  byResolution: Record<string, number>;
  byCatalyst: Record<string, number>;
  positionCount: number;
};

// ══════════════════════════════════════
// Portfolio Assessment (final output)
// ══════════════════════════════════════

export type PortfolioAssessment = {
  allowed: boolean;
  capped: boolean;
  blocked: boolean;

  overlapScore: number;
  correlationPenalty: number;
  budgetPenalty: number;

  adjustedSizeFraction: number;
  adjustedSize: 'FULL' | 'MEDIUM' | 'SMALL' | 'TINY' | 'NONE';

  reasons: string[];
};
