/**
 * OnChain V2 — Frontend Types
 * ============================
 * 
 * Canonical types for OnChain data in UI.
 */

export type GuardrailState = 'HEALTHY' | 'WARN' | 'DEGRADED' | 'CRITICAL' | 'FROZEN';
export type GuardrailAction = 'NONE' | 'DOWNWEIGHT' | 'FORCE_SAFE' | 'BLOCK_OUTPUT' | 'FREEZE';
export type OnchainWindow = '24h' | '7d' | '30d' | '90d' | '365d';
export type FinalState = 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL' | 'SAFE' | 'NO_DATA';
export type DataState = 'OK' | 'STALE' | 'NO_DATA';

export interface OnchainPoint {
  t: number; // unix ms
  score: number; // 0-1 (finalScore)
  confidence: number; // 0-1 (finalConfidence)
  state?: FinalState;
  guardrailState?: GuardrailState;
}

export interface OnchainGovernance {
  policyVersion: string;
  guardrailState: GuardrailState;
  guardrailAction: GuardrailAction;
  guardrailActionReasons: string[];
  psi: number;
  sampleCount30d: number;
  emaWindow: number;
  emaApplied: boolean;
  confidenceModifier: number;
  confidenceCapped: boolean;
}

export interface OnchainFlag {
  code: string;
  severity: 'CRITICAL' | 'WARN' | 'INFO';
  domain: 'DATA' | 'DRIFT' | 'MODEL' | 'GOV' | 'POST';
}

export interface OnchainFinalOutput {
  symbol: string;
  t0: number;
  window: string;
  finalScore: number;
  finalConfidence: number;
  finalState: FinalState;
  finalStateReason: string;
  dataState: DataState;
  drivers: string[];
  flags: OnchainFlag[];
  governance: OnchainGovernance;
  raw: {
    score: number;
    confidence: number;
    state: string;
  };
  processedAt: number;
}

export interface OnchainChartResponse {
  ok: boolean;
  symbol: string;
  window: OnchainWindow;
  points: OnchainPoint[];
}
