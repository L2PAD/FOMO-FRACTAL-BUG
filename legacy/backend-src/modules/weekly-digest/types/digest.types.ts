/**
 * Weekly Digest Types
 */

export interface WeeklyPerformance {
  period: { from: string; to: string };
  totalMarkets: number;
  correct: number;
  wrong: number;
  mixed: number;
  accuracy: number;
  edgeWeightedAccuracy: number;
  convictionWeightedAccuracy: number;
  avgEdge: number;
  avgConfidence: number;
  avgGrade: string;
  gradeDistribution: Record<string, number>;
  bySegment: {
    earlyWeek: SegmentPerf;
    midWeek: SegmentPerf;
    lateWeek: SegmentPerf;
  };
  byRegime: {
    bull: SegmentPerf;
    bear: SegmentPerf;
    transition: SegmentPerf;
  };
}

export interface SegmentPerf {
  count: number;
  accuracy: number;
  avgEdge: number;
}

export interface SourcePerformance {
  topSources: SourceStat[];
  decliningSources: SourceStat[];
  noisySources: SourceStat[];
}

export interface SourceStat {
  source: string;
  winRate: number;
  avgImpact: number;
  signalCount: number;
  earlySignalScore: number;
  noiseScore: number;
}

export interface MarketPattern {
  pattern: string;
  accuracy: number;
  count: number;
  avgEdge: number;
}

export interface TimingAnalysis {
  early: number;
  good: number;
  ok: number;
  late: number;
  bad: number;
  avgTimingQuality: number;
  missedWindowPct: number;
  lateEntryPct: number;
}

export interface MissedOpportunity {
  market: string;
  asset: string;
  missedEdge: number;
  reason: string;
}

export interface CalibrationAnalysis {
  overconfident: number;
  underconfident: number;
  wellCalibrated: number;
  avgCalibrationError: number;
  confidenceDrift: number;
  driftDirection: 'UP' | 'DOWN' | 'STABLE';
}

export interface EdgeAttribution {
  exchange: number;
  onchain: number;
  sentiment: number;
  social: number;
  project: number;
  intelligence: number;
}

export interface DecisionQuality {
  highQualityDecisions: number;
  luckyWins: number;
  badButCorrect: number;
  skillfulLosses: number;
  totalDecisions: number;
  decisionQualityScore: number;
}

export interface AlertPerformance {
  alertsTriggered: number;
  actionableAlerts: number;
  correctAlerts: number;
  falsePositives: number;
  alertAccuracy: number;
}

export interface ExecutionQuality {
  avgScore: number;
  avgGrade: string;
  totalEvaluated: number;
  byDirection: {
    LONG: { count: number; avgScore: number };
    SHORT: { count: number; avgScore: number };
  };
  entryQuality: {
    excellent: number;
    good: number;
    ok: number;
    bad: number;
  };
  timingQuality: {
    excellent: number;
    good: number;
    ok: number;
    late: number;
    bad: number;
  };
  avgSlippageLeakage: number;
  avgMissedMove: number;
  topIssues: string[];
  bestStyle: { style: string; avgScore: number } | null;
  worstStyle: { style: string; avgScore: number } | null;
  executionLessons: string[];
}

export interface WeeklyChange {
  metric: string;
  prev: number;
  current: number;
  delta: number;
  deltaPercent: number;
  direction: 'UP' | 'DOWN' | 'STABLE';
  impact: 'HIGH' | 'MEDIUM' | 'LOW';
}

export type SystemState = 'IMPROVING' | 'STABLE' | 'DEGRADING' | 'UNSTABLE';

export interface RegimeComparison {
  regime: string;
  prevAccuracy: number;
  currentAccuracy: number;
  delta: number;
  direction: 'UP' | 'DOWN' | 'STABLE';
  prevExecScore: number;
  currentExecScore: number;
  execDelta: number;
}

export interface ExecutionStyleDelta {
  style: string;
  prevScore: number;
  currentScore: number;
  delta: number;
  direction: 'UP' | 'DOWN' | 'STABLE';
  note: string;
}

export interface DigestComparison {
  systemState: SystemState;
  overallChangeScore: number;
  metricDeltas: WeeklyChange[];
  regimeComparison: RegimeComparison[];
  executionDeltas: ExecutionStyleDelta[];
  biggestImprovement: string;
  biggestDegradation: string;
  drivers: string[];
  confidenceDrift: {
    direction: 'UP' | 'DOWN' | 'STABLE';
    delta: number;
    interpretation: string;
  };
}

export interface WeeklyDigest {
  period: { from: string; to: string };
  generatedAt: string;
  performance: WeeklyPerformance;
  timing: TimingAnalysis;
  sources: SourcePerformance;
  patterns: { best: MarketPattern[]; worst: MarketPattern[] };
  edgeAttribution: EdgeAttribution;
  decisionQuality: DecisionQuality;
  calibration: CalibrationAnalysis;
  alertPerformance: AlertPerformance;
  executionQuality?: ExecutionQuality;
  comparison?: DigestComparison;
  missedOpportunities: MissedOpportunity[];
  changes: WeeklyChange[];
  lessons: string[];
  mistakes: string[];
  improvements: string[];
}
