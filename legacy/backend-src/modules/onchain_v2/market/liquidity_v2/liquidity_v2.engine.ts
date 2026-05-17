/**
 * OnChain V2 — LiquidityScore v2 Engine
 * =======================================
 * 
 * BLOCK 7: Composite score computation from normalized signals.
 */

import { clamp01 } from '../../normalization/normalizer.math.js';
import {
  LARE_V2_VERSION,
  LARE_V2_WEIGHTS,
  LARE_V2_REGIMES,
  LARE_V2_RISK_CAP,
  LARE_V2_CONFIDENCE,
  type LareV2Regime,
  type LareV2Window,
} from './liquidity_v2.contracts.js';
import type { NormalizedSignal } from '../../normalization/normalizer.types.js';

// ═══════════════════════════════════════════════════════════════
// OUTPUT TYPE
// ═══════════════════════════════════════════════════════════════

export interface LareV2Gate {
  riskCap: number;            // 0-1: max recommended alt exposure
  allowAggressiveRisk: boolean;
  blockNewPositions: boolean;
  reason: string;
}

export interface LareV2Output {
  version: string;
  window: LareV2Window;
  bucketTs: number;
  computedAt: number;
  
  score: number;              // 0-100
  confidence: number;         // 0-1
  regime: LareV2Regime;
  
  gate: LareV2Gate;
  
  components: NormalizedSignal[];
  drivers: string[];
  flags: string[];
}

// ═══════════════════════════════════════════════════════════════
// REGIME COMPUTATION
// ═══════════════════════════════════════════════════════════════

function computeRegime(score: number): LareV2Regime {
  if (score >= LARE_V2_REGIMES.RISK_ON_ALTS) return 'RISK_ON_ALTS';
  if (score >= LARE_V2_REGIMES.MODERATE_RISK_ON) return 'MODERATE_RISK_ON';
  if (score >= LARE_V2_REGIMES.NEUTRAL_LOW) return 'NEUTRAL';
  if (score >= LARE_V2_REGIMES.MODERATE_RISK_OFF) return 'MODERATE_RISK_OFF';
  return 'RISK_OFF';
}

// ═══════════════════════════════════════════════════════════════
// CONFIDENCE AGGREGATION
// ═══════════════════════════════════════════════════════════════

function aggregateConfidence(components: NormalizedSignal[]): number {
  const w = LARE_V2_WEIGHTS;
  
  const getConf = (key: string) => 
    components.find(c => c.key === key)?.confidence ?? 0;
  
  // Weighted sum
  let conf = 
    w.market * getConf('market') +
    w.flow * getConf('flow') +
    w.bridge * getConf('bridge') +
    w.stables * getConf('stables');
  
  // Penalty for missing components (confidence ≈ 0)
  const zeros = components.filter(c => (c.confidence ?? 0) <= 0.001).length;
  const penalty = 
    zeros >= 2 ? LARE_V2_CONFIDENCE.PENALTY_TWO_MISSING :
    zeros === 1 ? LARE_V2_CONFIDENCE.PENALTY_ONE_MISSING : 1.0;
  
  return clamp01(conf * penalty);
}

// ═══════════════════════════════════════════════════════════════
// MAIN ENGINE
// ═══════════════════════════════════════════════════════════════

export function buildLareV2(
  window: LareV2Window,
  bucketTs: number,
  components: NormalizedSignal[]
): LareV2Output {
  const w = LARE_V2_WEIGHTS;
  
  // Helper to get score for component
  const getScore = (key: string) => 
    components.find(c => c.key === key)?.score ?? 50;
  
  // Weighted base score
  const baseScore = 
    w.market * getScore('market') +
    w.flow * getScore('flow') +
    w.bridge * getScore('bridge') +
    w.stables * getScore('stables');
  
  // Aggregate confidence
  const confidence = aggregateConfidence(components);
  
  // IMPORTANT: Don't multiply score by confidence directly.
  // Instead: shrink towards neutral (50) as confidence decreases.
  // Formula: score = 50 + (base - 50) * (0.35 + 0.65 * confidence)
  const dampingFactor = 0.35 + 0.65 * confidence;
  const score = 50 + (baseScore - 50) * dampingFactor;
  
  // Determine regime
  const regime = computeRegime(score);
  
  // Collect drivers and flags
  const drivers: string[] = [];
  const flags: string[] = [];
  
  for (const c of components) {
    for (const f of (c.flags ?? [])) {
      // Handle both string flags and object flags
      const flagStr = typeof f === 'string' ? f : (f as any)?.code ?? String(f);
      flags.push(`${c.key.toUpperCase()}_${flagStr}`);
    }
    for (const d of (c.drivers ?? [])) {
      drivers.push(`${c.key}: ${d}`);
    }
  }
  
  // Add score-based drivers
  if (score >= 65) drivers.push('LARE: Strong risk-on signal');
  else if (score >= 55) drivers.push('LARE: Moderate risk appetite');
  else if (score <= 35) drivers.push('LARE: Elevated caution');
  
  // Gate logic
  const allowAggressiveRisk = 
    confidence >= LARE_V2_CONFIDENCE.MIN_FOR_AGGRESSIVE && 
    (regime === 'RISK_ON_ALTS' || regime === 'MODERATE_RISK_ON');
  
  const blockNewPositions = 
    confidence < LARE_V2_CONFIDENCE.MIN_FOR_POSITIONS || 
    regime === 'RISK_OFF';
  
  const riskCap = 
    regime === 'RISK_ON_ALTS' ? LARE_V2_RISK_CAP.RISK_ON_ALTS :
    regime === 'MODERATE_RISK_ON' ? LARE_V2_RISK_CAP.MODERATE_RISK_ON :
    regime === 'NEUTRAL' ? LARE_V2_RISK_CAP.NEUTRAL :
    regime === 'MODERATE_RISK_OFF' ? LARE_V2_RISK_CAP.MODERATE_RISK_OFF :
    LARE_V2_RISK_CAP.RISK_OFF;
  
  const reason = blockNewPositions
    ? `Blocked: confidence=${confidence.toFixed(2)} regime=${regime}`
    : `Cap=${(riskCap * 100).toFixed(0)}% confidence=${confidence.toFixed(2)} regime=${regime}`;
  
  return {
    version: LARE_V2_VERSION,
    window,
    bucketTs,
    computedAt: Date.now(),
    score: Math.round(score * 100) / 100,
    confidence: Math.round(confidence * 100) / 100,
    regime,
    gate: {
      riskCap,
      allowAggressiveRisk,
      blockNewPositions,
      reason,
    },
    components,
    drivers: drivers.slice(0, 8),
    flags: [...new Set(flags)],
  };
}

console.log('[OnChain V2] LiquidityScore v2 engine loaded');
