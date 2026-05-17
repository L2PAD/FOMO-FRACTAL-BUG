/**
 * Outcome Lab Types
 *
 * Types for the self-learning loop:
 * trace → correctness → timing → calibration → source attribution → narrative → missed → proposals
 */

export type CorrectnessLevel = 'CORRECT' | 'WRONG' | 'MIXED' | 'PENDING';
export type TimingQuality = 'EARLY' | 'GOOD' | 'OK' | 'LATE' | 'BAD';
export type CalibrationQuality = 'WELL_CALIBRATED' | 'OVERCONFIDENT' | 'UNDERCONFIDENT' | 'POOR';
export type LeadQuality = 'HIGH' | 'MEDIUM' | 'LOW' | 'NOISE';

// ── Decision Trace (snapshot at decision time) ──
export interface DecisionTrace {
  marketId: string;
  question: string;
  asset: string;
  eventType: string;
  entities: string[];

  // Timing
  traceTimestamp: Date;
  endDate?: string;

  // Core prediction
  fairProb: number;
  marketProb: number;
  edge: number;
  confidence: number;
  alignment: number;

  // Decision
  action: string;
  conviction: string;
  size: string;

  // Market state
  repricingState: string;
  entryAction: string;
  marketStage: string;

  // Social snapshot
  social: {
    lifecycle: string | null;
    echoScore: number;
    saturationScore: number;
    originQuality: number;
    topOrigin: string | null;
  };

  // Project snapshot
  project: {
    verdict: string | null;
    valuation: string | null;
    unlockRisk: string | null;
    tokenomics: string | null;
    overallScore: number;
  };

  // Intelligence snapshot
  intelligence: {
    memoAction: string | null;
    mispricingType: string | null;
    pricedInLevel: number;
    evidenceDrivers: number;
    evidenceNoise: number;
  };

  // Execution quality snapshot (TWES)
  executionQuality?: {
    score: number;
    grade: string;
    direction: string;
    entryQuality: string;
    entryPosition: string;
    timingQuality: string;
    missedWindow: boolean;
    slippageLeakage: number;
    missedMove: number;
    opportunityReason: string;
    regime: string;
    narrativePhase: string;
    lessons: string[];
  };
}

// ── Resolved Market ──
export interface ResolvedMarket {
  marketId: string;
  question: string;
  asset: string;
  outcome: 'YES' | 'NO';
  resolvedAt: Date;
  finalPrice: number;
}

// ── Correctness Review ──
export interface CorrectnessReview {
  correctness: CorrectnessLevel;
  directionCorrect: boolean;
  edgeRealized: boolean;
  strongestCall: string;     // e.g. "YES_NOW at 43% was correct"
  confidenceJustified: boolean;
  notes: string[];
}

// ── Timing Review ──
export interface TimingReview {
  timingQuality: TimingQuality;
  bestWindow: string | null;       // "2h after first signal" etc.
  firstActionable: string | null;  // when edge first appeared
  missed: boolean;
  entryDelay: number;              // hours from first signal to action
  optimalEntryProb: number;        // what prob was at best entry
  actualEntryProb: number;         // what prob was at our entry
  notes: string[];
}

// ── Calibration Review ──
export interface CalibrationReview {
  calibrationQuality: CalibrationQuality;
  avgFairProb: number;
  actualOutcomeProb: number;       // 1 or 0
  errorScore: number;              // |fairProb - outcome|
  overconfidenceScore: number;     // how much we overestimated
  notes: string[];
}

// ── Source Attribution ──
export interface SourceAttribution {
  source: string;
  sourceType: string;
  helpful: boolean;
  leadQuality: LeadQuality;
  impactScore: number;             // 0–1
  timeliness: string;              // 'early' | 'on_time' | 'late' | 'after_the_fact'
  lesson: string;
}

// ── Narrative Review ──
export interface NarrativeReview {
  lifecycleAtBest: string | null;
  saturationTooHigh: boolean;
  echoMisleading: boolean;
  narrativeHelped: boolean;
  narrativeTrap: boolean;          // narrative was strong but outcome was opposite
  notes: string[];
}

// ── Missed Opportunity ──
export interface MissedOpportunity {
  missed: boolean;
  reason: string;
  edgeAtBest: number;
  actionAtBest: string;
  whyMissed: string[];             // "system stayed WATCH", "confidence too low", etc.
}

// ── Weight Proposals ──
export interface WeightProposal {
  sourceAdjustments: { source: string; currentWeight: number; proposedWeight: number; reason: string }[];
  timingAdjustments: { parameter: string; currentValue: number; proposedValue: number; reason: string }[];
  calibrationAdjustments: { parameter: string; adjustment: number; reason: string }[];
}

// ── Execution Quality Summary (for reviews) ──
export interface ExecutionQualitySummary {
  score: number;
  grade: string;
  direction: string;
  entryQuality: string;
  timingQuality: string;
  slippageLeakage: number;
  missedMove: number;
  lessons: string[];
}

// ── Full Outcome Review ──
export interface OutcomeReview {
  marketId: string;
  question: string;
  asset: string;
  outcome: 'YES' | 'NO';
  resolvedAt: Date;

  trace: DecisionTrace;
  correctness: CorrectnessReview;
  timing: TimingReview;
  calibration: CalibrationReview;
  sourceAttributions: SourceAttribution[];
  narrative: NarrativeReview;
  missedOpportunity: MissedOpportunity;
  executionQuality?: ExecutionQualitySummary;
  proposals: WeightProposal;

  overallGrade: 'A' | 'B' | 'C' | 'D' | 'F';
  lessonsLearned: string[];
  reviewedAt: Date;
}

// ── Heatmap Entry ──
export interface SignalHeatmapEntry {
  source: string;
  sourceType: string;
  totalOccurrences: number;
  earlySignalRate: number;         // 0–1
  confirmationRate: number;        // 0–1
  noiseRate: number;               // 0–1
  avgImpactScore: number;
  avgLeadTime: number;             // hours
  reliability: number;             // 0–1
}
