/**
 * Alt Liquidity Types
 * ====================
 * 
 * PHASE 3: Type definitions for Alt Liquidity Signal UI
 */

export type LiquidityRegime =
  | 'RISK_ON_ALTS'
  | 'RISK_OFF'
  | 'STABLE_INFLOW'
  | 'BTC_FLIGHT'
  | 'NEUTRAL';

export type GuardrailState = 'HEALTHY' | 'WARN' | 'DEGRADED' | 'CRITICAL' | 'FROZEN';
export type GuardrailAction = 'NONE' | 'DOWNWEIGHT' | 'FORCE_SAFE' | 'BLOCK_OUTPUT' | 'FREEZE';
export type FlagSeverity = 'INFO' | 'WARN' | 'DEGRADED' | 'CRITICAL';

export interface LiquidityFlag {
  code: string;
  severity: FlagSeverity;
  message?: string;
}

export interface LiquidityInputs {
  pureAltCap: { now: number; delta24h: number | null; delta7d: number | null };
  stableSupply: { now: number; delta24h: number | null; delta7d: number | null };
  stableDom: { now: number; delta24h: number | null; delta7d: number | null };
  btcDom: { now: number; delta24h: number | null; delta7d: number | null };
  ethbtc: { now: number; delta24h: number | null; delta7d: number | null };
}

export interface LiquidityGovernance {
  guardrailState: GuardrailState;
  guardrailAction: GuardrailAction;
  confidenceModifier: number;
  reasons: string[];
}

export interface LiquidityGate {
  allowAggressiveRisk: boolean;
  riskCap: number;
  blockNewPositions: boolean;
  reason: string;
}

export interface LiquidityLatest {
  ok: boolean;
  t: number;
  score: number;
  regime: LiquidityRegime;
  confidence: number;
  drivers: string[];
  flags: LiquidityFlag[];
  inputs?: LiquidityInputs;
  governance: LiquidityGovernance;
  gate: LiquidityGate;
  version?: string;
}

export interface LiquiditySeriesPoint {
  t: number;
  score: number;
  confidence: number;
  regime?: LiquidityRegime;
  flags?: string[];
  drivers?: string[];
}

export interface LiquiditySeries {
  ok: boolean;
  key: string;
  window: string;
  count: number;
  series: LiquiditySeriesPoint[];
}

// UI helper types
export type ScoreTone = 'good' | 'mid' | 'bad';
export type RegimeTone = 'good' | 'mid' | 'bad' | 'neutral';
