/**
 * UI Helpers
 * ===========
 * 
 * PHASE 3: Color and tone helpers for Alt Liquidity Signal
 */

import type { LiquidityRegime, FlagSeverity, GuardrailState, ScoreTone, RegimeTone } from './types';

export function scoreTone(score: number): ScoreTone {
  if (score >= 70) return 'good';
  if (score >= 40) return 'mid';
  return 'bad';
}

export function scoreColor(score: number): string {
  if (score >= 70) return '#22c55e'; // green
  if (score >= 40) return '#6b7280'; // gray
  return '#ef4444'; // red
}

export function regimeTone(regime: LiquidityRegime): RegimeTone {
  switch (regime) {
    case 'RISK_ON_ALTS': return 'good';
    case 'RISK_OFF': return 'bad';
    case 'STABLE_INFLOW': return 'mid';
    case 'BTC_FLIGHT': return 'mid';
    default: return 'neutral';
  }
}

export function regimeColor(regime: LiquidityRegime): string {
  switch (regime) {
    case 'RISK_ON_ALTS': return '#22c55e'; // green
    case 'RISK_OFF': return '#ef4444'; // red
    case 'STABLE_INFLOW': return '#f97316'; // orange
    case 'BTC_FLIGHT': return '#eab308'; // yellow
    default: return '#6b7280'; // gray
  }
}

export function regimeLabel(regime: LiquidityRegime): string {
  switch (regime) {
    case 'RISK_ON_ALTS': return 'Risk-On Alts';
    case 'RISK_OFF': return 'Risk-Off';
    case 'STABLE_INFLOW': return 'Stable Inflow';
    case 'BTC_FLIGHT': return 'BTC Flight';
    default: return 'Neutral';
  }
}

export function severityColor(severity: FlagSeverity): string {
  switch (severity) {
    case 'INFO': return '#6b7280'; // gray
    case 'WARN': return '#eab308'; // yellow
    case 'DEGRADED': return '#f97316'; // orange
    case 'CRITICAL': return '#ef4444'; // red
    default: return '#6b7280';
  }
}

export function guardrailColor(state: GuardrailState): string {
  switch (state) {
    case 'HEALTHY': return '#22c55e'; // green
    case 'WARN': return '#eab308'; // yellow
    case 'DEGRADED': return '#f97316'; // orange
    case 'CRITICAL': return '#ef4444'; // red
    case 'FROZEN': return '#3b82f6'; // blue
    default: return '#6b7280';
  }
}

export function formatNumber(num: number, decimals: number = 2): string {
  if (num >= 1e12) return `${(num / 1e12).toFixed(decimals)}T`;
  if (num >= 1e9) return `${(num / 1e9).toFixed(decimals)}B`;
  if (num >= 1e6) return `${(num / 1e6).toFixed(decimals)}M`;
  if (num >= 1e3) return `${(num / 1e3).toFixed(decimals)}K`;
  return num.toFixed(decimals);
}

export function formatDelta(delta: number | null): string {
  if (delta === null) return 'N/A';
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${delta.toFixed(2)}%`;
}
