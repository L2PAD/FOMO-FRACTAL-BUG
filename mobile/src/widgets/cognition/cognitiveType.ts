/**
 * COGNITIVE TYPOGRAPHY  ·  Iteration 4·α (refined post-review)
 *
 * Hierarchy of thought, not typography helpers.
 *
 *   Layer 1   cognition / thesis      (max weight, full presence)
 *   Layer 2   decision                (high weight, slightly tighter)
 *   Layer 3   explanation             (quiet via spacing/weight, NOT opacity)
 *   Layer 4   telemetry               (almost background, tiny, dim)
 *
 *
 *   Rule:  L3 must NEVER compete with L1.
 *          Explanation feels quiet through softer weight, generous
 *          line-height and breathing letter-spacing — NEVER through
 *          opacity, which turns into "disabled UI".
 *
 *
 *   Pressure axis (post-review refinement):
 *     L1 cognition takes an additional `pressure` parameter to encode
 *     semantic pressure within the same hue family.
 *       'authority'      — sharp, firm, tight letter-spacing.
 *                          Decision-level suppression (SUPPRESSED).
 *       'institutional'  — calm, breathing letter-spacing.
 *                          Capital-level suppression (RISK_OFF).
 *       'ambient'        — soft, wide letter-spacing, lower weight.
 *                          Background hero state.
 *
 *     Same family, different pressure.
 */
import { TextStyle } from 'react-native';
import { SemanticEnergy, tokenFor } from './cognitiveTokens';

type Theme = any;
export type Pressure = 'authority' | 'institutional' | 'ambient';

function colorForTone(colors: Theme, energy: SemanticEnergy | undefined, fallback: string): string {
  if (!energy) return fallback;
  const tok = tokenFor(energy);
  return (colors as any)[tok.colorKey] || fallback;
}

function pressureCfg(pressure: Pressure): { ls: number; lhMul: number; fw: TextStyle['fontWeight'] } {
  if (pressure === 'institutional') return { ls: 1.4,  lhMul: 1.28, fw: '800' };
  if (pressure === 'ambient')       return { ls: 1.8,  lhMul: 1.42, fw: '700' };
  return                                   { ls: 0.25, lhMul: 1.08, fw: '900' };
}

/**
 * Layer 1 — cognition / thesis.
 * Used for hero state labels: "SUPPRESSED", "RISK OFF", "DORMANT".
 * Pressure differentiates same-tone heroes (decision vs capital).
 */
export function cognitionStyle(
  colors: Theme,
  tone?: SemanticEnergy,
  size: 'lg' | 'xl' | 'xxl' = 'xl',
  pressure: Pressure = 'authority',
): TextStyle {
  const fontSize = size === 'xxl' ? 28 : size === 'xl' ? 22 : 17;
  const p = pressureCfg(pressure);
  return {
    fontSize,
    fontWeight: p.fw,
    letterSpacing: p.ls,
    lineHeight: Math.round(fontSize * p.lhMul),
    color: colorForTone(colors, tone, colors.textPrimary),
  };
}

/**
 * Layer 2 — decision.
 */
export function decisionStyle(
  colors: Theme,
  tone?: SemanticEnergy,
  size: 'sm' | 'md' = 'md',
): TextStyle {
  const fontSize = size === 'sm' ? 11 : 13;
  return {
    fontSize,
    fontWeight: '800',
    letterSpacing: 0.5,
    lineHeight: Math.round(fontSize * 1.32),
    color: colorForTone(colors, tone, colors.textPrimary),
  };
}

/**
 * Layer 3 — explanation.
 * Quiet via softer weight + generous line-height + breathing
 * letter-spacing.  No opacity tricks — explanation is a THOUGHT,
 * not a disabled label.
 */
export function explanationStyle(
  colors: Theme,
  tone?: SemanticEnergy,
): TextStyle {
  return {
    fontSize: 12,
    fontWeight: '400',
    fontStyle: 'italic',
    letterSpacing: 0.25,
    lineHeight: 19,
    color: colorForTone(colors, tone, colors.textMuted),
  };
}

/**
 * Layer 4 — telemetry.
 * Almost background.  Used for caps headers, percentages, counts.
 */
export function telemetryStyle(
  colors: Theme,
  tone?: SemanticEnergy,
): TextStyle {
  return {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.4,
    lineHeight: 13,
    color: colorForTone(colors, tone, colors.textMuted),
    opacity: 0.75,
  };
}

/** L4 numeric variant — for percentages, scores, counts. */
export function telemetryNumberStyle(
  colors: Theme,
  tone?: SemanticEnergy,
  size: 'md' | 'lg' = 'md',
): TextStyle {
  return {
    fontSize: size === 'lg' ? 22 : 14,
    fontWeight: '800',
    letterSpacing: 0.3,
    color: colorForTone(colors, tone, colors.textMuted),
    opacity: 0.8,
  };
}
