/**
 * META BRAIN V2 — META CONFIDENCE SERVICE
 * =========================================
 *
 * Computes Meta Brain's OWN confidence based on:
 *   1. Ensemble entropy (module agreement)
 *   2. Disagreement rate (modules opposing verdict)
 *   3. Coverage ratio
 *
 * Formula:
 *   metaConfidence = baseConf
 *     × exp(-k_entropy × entropy)
 *     × exp(-k_disagree × disagreeRate)
 *     × exp(-k_coverage × (1 - coverageRatio))
 */

import { RegimePolicy } from './policy.contract.js';

export interface MetaConfidenceResult {
  metaConfidence: number;
  baseConfidence: number;
  entropy: number;
  disagreeRate: number;
  coverageRatio: number;
  entropyPenalty: number;
  disagreePenalty: number;
  coveragePenalty: number;
}

/**
 * Compute Shannon entropy of direction distribution [0..log(3)≈1.1]
 * Normalized to [0..1].
 */
function shannonEntropy(directions: string[]): number {
  if (directions.length === 0) return 1;

  const counts: Record<string, number> = { LONG: 0, SHORT: 0, NEUTRAL: 0 };
  for (const d of directions) counts[d] = (counts[d] || 0) + 1;

  const n = directions.length;
  let h = 0;
  for (const c of Object.values(counts)) {
    if (c === 0) continue;
    const p = c / n;
    h -= p * Math.log2(p);
  }

  // Normalize: max entropy = log2(3) ≈ 1.585
  return Math.min(1, h / Math.log2(3));
}

/**
 * Compute disagreement: fraction of modules opposing the final direction.
 */
function computeDisagreement(
  directions: string[],
  finalDirection: string
): number {
  if (directions.length === 0) return 0;
  if (finalDirection === 'NEUTRAL') return 0; // No disagreement when NEUTRAL

  const opposing = finalDirection === 'LONG' ? 'SHORT' : 'LONG';
  const opposingCount = directions.filter(d => d === opposing).length;
  return opposingCount / directions.length;
}

/**
 * Compute Meta Brain's own confidence.
 */
export function computeMetaConfidence(
  baseConfidence: number,
  moduleDirections: string[],
  finalDirection: string,
  totalProviders: number,
  activeProviders: number,
  policy: RegimePolicy
): MetaConfidenceResult {
  const entropy = shannonEntropy(moduleDirections);
  const disagreeRate = computeDisagreement(moduleDirections, finalDirection);
  const coverageRatio = totalProviders > 0 ? activeProviders / totalProviders : 0;

  const entropyPenalty = Math.exp(-policy.confidence.entropyPenaltyK * entropy);
  const disagreePenalty = Math.exp(-policy.confidence.disagreementPenaltyK * disagreeRate);
  const coveragePenalty = Math.exp(-policy.confidence.coveragePenaltyK * (1 - coverageRatio));

  const metaConfidence = Math.max(0, Math.min(1,
    baseConfidence * entropyPenalty * disagreePenalty * coveragePenalty
  ));

  return {
    metaConfidence,
    baseConfidence,
    entropy,
    disagreeRate,
    coverageRatio,
    entropyPenalty,
    disagreePenalty,
    coveragePenalty,
  };
}
