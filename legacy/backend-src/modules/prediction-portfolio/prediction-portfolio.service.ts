/**
 * Portfolio Brain Service — Stage 7 Orchestrator
 *
 * Main brain: combines Factor Engine, Cluster Engine, Correlation Engine,
 * Risk Budget, and Portfolio Adjustment into a single assessment.
 *
 * Node = main brain. Python = data provider only.
 */
import { getDb } from '../../db/mongodb.js';
import { buildFactorProfile, deduplicateProfile } from './services/factor-engine.service.js';
import { computeClusterOverlaps } from './services/cluster-engine.service.js';
import { computeCorrelation } from './services/correlation-engine.service.js';
import { evaluateRiskBudget } from './services/risk-budget.service.js';
import { computeExposureSummary } from './services/exposure-engine.service.js';
import { buildPortfolioAssessment } from './services/portfolio-adjustment.service.js';
import type {
  CandidateCase,
  ActivePosition,
  PortfolioAssessment,
  ExposureSummary,
  FactorProfile,
} from './types/portfolio.types.js';

// ══════════════════════════════════════
// Active Positions Storage (MongoDB)
// ══════════════════════════════════════

const COLLECTION = 'portfolio_positions';

async function getActivePositions(): Promise<ActivePosition[]> {
  try {
    const db = getDb();
    const docs = await db.collection(COLLECTION)
      .find({ active: true })
      .project({ _id: 0 })
      .toArray();
    return docs as ActivePosition[];
  } catch {
    return [];
  }
}

async function upsertPosition(pos: ActivePosition & { active: boolean }): Promise<void> {
  try {
    const db = getDb();
    await db.collection(COLLECTION).updateOne(
      { marketId: pos.marketId },
      { $set: { ...pos, updatedAt: new Date().toISOString() } },
      { upsert: true },
    );
  } catch {
    // silent fail
  }
}

// ══════════════════════════════════════
// Build CandidateCase from raw Python data
// ══════════════════════════════════════

function buildCandidate(raw: any): CandidateCase {
  const action = raw.recommendationAction || raw.recommendation?.action || 'AVOID';
  const direction: 'long' | 'short' | 'neutral' =
    action.startsWith('YES') ? 'long' :
    action.startsWith('NO') ? 'short' :
    'neutral';

  const factorProfile = raw.factorProfile || buildFactorProfile({
    asset: raw.asset || 'BTC',
    eventType: raw.eventType || raw.event_type || 'generic_crypto',
    entities: raw.entities || [],
    question: raw.question || '',
    endDate: raw.endDate || raw.end_date,
  });

  return {
    marketId: raw.marketId || raw.market_id,
    question: raw.question || '',
    asset: raw.asset || 'BTC',
    eventType: raw.eventType || raw.event_type || 'generic_crypto',
    direction,
    edge: raw.edge ?? raw.analysis?.net_edge ?? 0,
    confidence: raw.confidence ?? raw.analysis?.model_confidence ?? 0.5,
    alignment: raw.alignment ?? raw.analysis?.alignment_score ?? 0.5,
    resolutionRisk: raw.resolutionRisk ?? raw.resolution?.resolution_risk_score ?? 0,
    recommendationAction: action,
    baseSizeFraction: raw.baseSizeFraction ?? raw.sizing?.size_fraction ?? 0,
    factorProfile: deduplicateProfile(factorProfile),
    endDate: raw.endDate || raw.end_date,
    entities: raw.entities || [],
  };
}

// ══════════════════════════════════════
// Main: Assess Portfolio for a Candidate
// ══════════════════════════════════════

export async function assessCandidate(raw: any): Promise<PortfolioAssessment> {
  const candidate = buildCandidate(raw);
  const positions = await getActivePositions();

  // If no active positions, no portfolio constraints
  if (!positions.length) {
    return buildPortfolioAssessment({
      baseSizeFraction: candidate.baseSizeFraction,
      correlationPenalty: 0,
      correlationBlocked: false,
      budgetPenalty: 0,
      budgetBlocked: false,
      budgetReasons: [],
      maxOverlap: 0,
    });
  }

  // 1. Cluster overlaps
  const overlaps = computeClusterOverlaps(candidate, positions);

  // 2. Correlation penalty
  const correlation = computeCorrelation(overlaps);

  // 3. Risk budget
  const budget = evaluateRiskBudget(candidate, positions);

  // 4. Build assessment
  return buildPortfolioAssessment({
    baseSizeFraction: candidate.baseSizeFraction,
    correlationPenalty: correlation.penalty,
    correlationBlocked: correlation.blocked,
    correlationReason: correlation.reason,
    budgetPenalty: budget.penalty,
    budgetBlocked: budget.blocked,
    budgetReasons: budget.reasons,
    maxOverlap: correlation.maxOverlap,
  });
}

// ══════════════════════════════════════
// Batch Assessment (for full pipeline)
// ══════════════════════════════════════

export async function assessBatch(
  rawCases: any[],
): Promise<Record<string, PortfolioAssessment>> {
  const positions = await getActivePositions();
  const results: Record<string, PortfolioAssessment> = {};

  for (const raw of rawCases) {
    const candidate = buildCandidate(raw);
    const marketId = candidate.marketId;

    if (!positions.length) {
      results[marketId] = buildPortfolioAssessment({
        baseSizeFraction: candidate.baseSizeFraction,
        correlationPenalty: 0,
        correlationBlocked: false,
        budgetPenalty: 0,
        budgetBlocked: false,
        budgetReasons: [],
        maxOverlap: 0,
      });
      continue;
    }

    const overlaps = computeClusterOverlaps(candidate, positions);
    const correlation = computeCorrelation(overlaps);
    const budget = evaluateRiskBudget(candidate, positions);

    results[marketId] = buildPortfolioAssessment({
      baseSizeFraction: candidate.baseSizeFraction,
      correlationPenalty: correlation.penalty,
      correlationBlocked: correlation.blocked,
      correlationReason: correlation.reason,
      budgetPenalty: budget.penalty,
      budgetBlocked: budget.blocked,
      budgetReasons: budget.reasons,
      maxOverlap: correlation.maxOverlap,
    });
  }

  return results;
}

// ══════════════════════════════════════
// Exposure Summary
// ══════════════════════════════════════

export async function getExposure(): Promise<ExposureSummary> {
  const positions = await getActivePositions();
  return computeExposureSummary(positions);
}

// ══════════════════════════════════════
// Position Management
// ══════════════════════════════════════

export async function addPosition(raw: any): Promise<void> {
  const candidate = buildCandidate(raw);
  await upsertPosition({
    marketId: candidate.marketId,
    question: candidate.question,
    asset: candidate.asset,
    direction: candidate.direction,
    sizeFraction: candidate.baseSizeFraction,
    factorProfile: candidate.factorProfile,
    active: true,
  });
}

export async function removePosition(marketId: string): Promise<void> {
  try {
    const db = getDb();
    await db.collection(COLLECTION).updateOne(
      { marketId },
      { $set: { active: false, closedAt: new Date().toISOString() } },
    );
  } catch {
    // silent
  }
}

export async function listPositions(): Promise<ActivePosition[]> {
  return getActivePositions();
}
