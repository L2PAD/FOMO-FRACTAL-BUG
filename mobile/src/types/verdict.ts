/**
 * Verdict Inspector card types — observability layer for the
 * Expo Trading Runtime v1.
 *
 * Mirrors the FastAPI shape returned by /api/mbrain/verdicts/* (see
 * backend/routes/mbrain_verdicts.py:_build_inspector_card). Read-only.
 */

export type StageDirection = 'LONG' | 'SHORT' | 'HOLD';
export type FinalAction = 'LONG' | 'SHORT' | 'HOLD';
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME';
export type StageName =
  | 'raw'
  | 'after_rules'
  | 'after_meta_brain'
  | 'after_calibration'
  | 'final';

export type StageBlock = {
  direction: StageDirection;
  confidence: number | null;
  expectedReturn: number | null;
  collapsed_to_hold: boolean;
};

export type Badge = {
  type:
    | 'SUPPRESSED'
    | 'META_DOWNGRADE'
    | 'BLOCKED'
    | 'DIRECTION_FLIP';
  label: string;
  tone: 'warn' | 'block' | 'alert';
};

export type AdjustmentRow = {
  stage: 'RULES' | 'META_BRAIN' | 'CALIBRATION';
  key?: string;
  notes?: string;
  deltaConfidence?: number;
  deltaReturn?: number;
};

export type AppliedRule = {
  id: string;
  severity: 'INFO' | 'WARN' | 'BLOCK';
  message?: string;
  overrideAction?: string;
};

export type VerdictCard = {
  verdictId: string | null;
  symbol: string;
  horizon: string;
  ts: string;
  regime: string | null;
  modelId: string | null;
  final_action: FinalAction;
  blocked: boolean;
  block_reason: string[];
  confidence_final: number | null;
  risk: RiskLevel | null;
  stages: Record<StageName, StageBlock>;
  reason_chain: string[];
  badges: Badge[];
  raw_appliedRules: AppliedRule[];
  raw_adjustments: AdjustmentRow[];
};

export type VerdictListResponse = {
  ok: boolean;
  n: number;
  cards: VerdictCard[];
  note?: string;
  error?: string;
};

export type VerdictSweepResponse = {
  ok: boolean;
  n: number;
  elapsed_ms: number;
  cards: VerdictCard[];
  failures: Array<{ asset: string; horizon: string; reason: string }>;
};
