/**
 * LiquidityScore Governance
 * ==========================
 * 
 * PHASE 2.1: Guardrails adapter for liquidity engine
 * 
 * Applies governance rules to confidence and output.
 */

import {
  LiquidityGovernance,
  LiquidityFlag,
  FlagSeverity,
  GuardrailAction,
  LIQUIDITY_THRESHOLDS as T,
} from './contracts';

export interface GovernanceInput {
  confidenceBase: number;
  flags: LiquidityFlag[];
  latestAge: number;
  sampleCount: number;
  keysPresent: number;
}

export interface GovernanceResult {
  governance: LiquidityGovernance;
  finalConfidence: number;
  shouldBlockOutput: boolean;
}

/**
 * Apply governance rules to liquidity output
 */
export function applyGovernance(input: GovernanceInput): GovernanceResult {
  const reasons: string[] = [];
  let modifier = 1.0;
  let state: 'HEALTHY' | 'WARN' | 'DEGRADED' | 'CRITICAL' = 'HEALTHY';
  let action: GuardrailAction = GuardrailAction.NONE;

  // Check for CRITICAL flags
  const hasCritical = input.flags.some(f => f.severity === FlagSeverity.CRITICAL);
  if (hasCritical) {
    state = 'CRITICAL';
    action = GuardrailAction.BLOCK_OUTPUT;
    modifier = 0;
    reasons.push('CRITICAL: No data available');
    
    return {
      governance: { guardrailState: state, guardrailAction: action, confidenceModifier: modifier, reasons },
      finalConfidence: 0,
      shouldBlockOutput: true,
    };
  }

  // Check for DEGRADED flags
  const hasDegraded = input.flags.some(f => f.severity === FlagSeverity.DEGRADED);
  if (hasDegraded) {
    state = 'DEGRADED';
    action = GuardrailAction.DOWNWEIGHT;
    modifier = 0.4;
    reasons.push('DEGRADED: Data quality insufficient');
  }

  // Check for WARN flags (if not already degraded)
  const hasWarn = input.flags.some(f => f.severity === FlagSeverity.WARN);
  if (hasWarn && state === 'HEALTHY') {
    state = 'WARN';
    action = GuardrailAction.DOWNWEIGHT;
    modifier = 0.85;
    reasons.push('WARN: Some data quality issues');
  }

  // Additional checks
  if (input.latestAge > T.VERY_STALE_MS && state !== 'CRITICAL') {
    if (state === 'HEALTHY') state = 'WARN';
    modifier = Math.min(modifier, 0.6);
    reasons.push(`DATA_STALE(age=${Math.round(input.latestAge / 60000)}m)`);
    if (action === GuardrailAction.NONE) action = GuardrailAction.DOWNWEIGHT;
  }

  if (input.sampleCount < T.SAMPLE_COUNT_TARGET * 0.3) {
    if (state === 'HEALTHY' || state === 'WARN') state = 'DEGRADED';
    modifier = Math.min(modifier, 0.3);
    reasons.push(`LOW_SAMPLES(${input.sampleCount})`);
    action = GuardrailAction.DOWNWEIGHT;
  }

  if (input.keysPresent < 3) {
    if (state === 'HEALTHY' || state === 'WARN') state = 'DEGRADED';
    modifier = Math.min(modifier, 0.5);
    reasons.push(`PARTIAL_DATA(${input.keysPresent}/5 keys)`);
    action = GuardrailAction.DOWNWEIGHT;
  }

  const finalConfidence = Math.max(0, Math.min(1, input.confidenceBase * modifier));

  return {
    governance: {
      guardrailState: state,
      guardrailAction: action,
      confidenceModifier: modifier,
      reasons,
    },
    finalConfidence,
    shouldBlockOutput: false,
  };
}

console.log('[Liquidity] Governance loaded');
