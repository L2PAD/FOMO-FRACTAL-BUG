/**
 * Layer 8 — Market Social Impact
 *
 * Bridge: translates social narrative assessment into market-level impact.
 *
 * HARD RULES:
 * - probabilityDelta ≤ 0.05 (social rarely moves probability directly)
 * - confidenceDelta ≤ 0.2
 * - timingImpact = primary use of social
 */
import type { NarrativeAssessment, SocialIntel } from '../types/narrative.types.js';

export function computeMarketSocialImpact(assessments: NarrativeAssessment[]): SocialIntel {
  if (!assessments.length) {
    return {
      originQuality: 0, echoScore: 0, saturationScore: 0,
      lifecycle: 'DORMANT', socialStrength: 0, socialConfidence: 0,
      probabilityDelta: 0, confidenceDelta: 0, alignmentDelta: 0, narrativeDelta: 0,
      whyHelpful: [], whyRisky: [],
      topOrigin: null, topAmplifiers: [],
    };
  }

  // Use strongest cluster as primary signal
  const primary = assessments.reduce((best, a) => a.socialStrength > best.socialStrength ? a : best);

  // Aggregate across all clusters
  const avgEcho = assessments.reduce((s, a) => s + a.echoScore, 0) / assessments.length;
  const avgSaturation = assessments.reduce((s, a) => s + a.saturationScore, 0) / assessments.length;
  const maxStrength = primary.socialStrength;
  const maxConfidence = primary.socialConfidence;

  // === IMPACT CALCULATION ===

  // Probability: capped at 0.05, only if high-trust origin + low saturation
  let probabilityDelta = 0;
  if (primary.origin.trustScore > 0.7 && avgSaturation < 0.4 && primary.lifecycle === 'EARLY') {
    probabilityDelta = Math.min(0.05, primary.origin.trustScore * 0.05);
  }

  // Confidence: up to 0.2, based on origin quality and freshness
  let confidenceDelta = 0;
  if (primary.lifecycle === 'EARLY' || primary.lifecycle === 'EXPANDING') {
    confidenceDelta = Math.min(0.2, maxConfidence * 0.15 * (1 - avgEcho));
  } else if (primary.lifecycle === 'SATURATED') {
    confidenceDelta = -0.05; // saturated narrative reduces confidence in edge
  }

  // Alignment: how much social aligns with other signals
  let alignmentDelta = 0;
  if (maxStrength > 0.5 && avgEcho < 0.5) {
    alignmentDelta = Math.min(0.15, maxStrength * 0.1);
  }

  // Narrative: how much the story is building
  let narrativeDelta = 0;
  if (primary.lifecycle === 'EARLY') narrativeDelta = 0.2;
  else if (primary.lifecycle === 'EXPANDING') narrativeDelta = 0.1;
  else if (primary.lifecycle === 'SATURATED') narrativeDelta = -0.1;
  else if (primary.lifecycle === 'FADING') narrativeDelta = -0.15;

  // === REASONS ===
  const whyHelpful: string[] = [];
  const whyRisky: string[] = [];

  if (primary.origin.trustScore > 0.6) whyHelpful.push(`High-trust origin (${primary.origin.authorName || 'unknown'})`);
  if (primary.lifecycle === 'EARLY') whyHelpful.push('Narrative is early — potential edge');
  if (primary.lifecycle === 'EXPANDING' && avgEcho < 0.4) whyHelpful.push('Narrative expanding with low echo — organic spread');
  if (primary.highQualityAmplifiers.length > 0) whyHelpful.push(`Quality amplifiers: ${primary.highQualityAmplifiers.slice(0, 2).join(', ')}`);

  if (avgEcho > 0.6) whyRisky.push(`High echo (${(avgEcho * 100).toFixed(0)}%) — mostly reposts`);
  if (avgSaturation > 0.6) whyRisky.push(`High saturation (${(avgSaturation * 100).toFixed(0)}%) — narrative exhausted`);
  if (primary.lifecycle === 'SATURATED') whyRisky.push('Narrative already saturated — late entry risk');
  if (primary.lifecycle === 'FADING') whyRisky.push('Narrative fading — no fresh drivers');
  if (primary.origin.trustScore < 0.3) whyRisky.push('Low-trust origin — signal may be noise');

  return {
    originQuality: Math.round(primary.origin.trustScore * 100) / 100,
    echoScore: Math.round(avgEcho * 100) / 100,
    saturationScore: Math.round(avgSaturation * 100) / 100,
    lifecycle: primary.lifecycle,
    socialStrength: Math.round(maxStrength * 100) / 100,
    socialConfidence: Math.round(maxConfidence * 100) / 100,
    probabilityDelta: Math.round(probabilityDelta * 1000) / 1000,
    confidenceDelta: Math.round(confidenceDelta * 1000) / 1000,
    alignmentDelta: Math.round(alignmentDelta * 1000) / 1000,
    narrativeDelta: Math.round(narrativeDelta * 1000) / 1000,
    whyHelpful,
    whyRisky,
    topOrigin: primary.origin.authorName,
    topAmplifiers: primary.highQualityAmplifiers.slice(0, 3),
  };
}
