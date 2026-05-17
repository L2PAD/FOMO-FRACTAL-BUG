/**
 * META BRAIN V2 — WEIGHT ENGINE (Policy-Driven)
 * ================================================
 *
 * Weight per module:
 *   w_i = policyBaseWeight_i × regimeMult_i × accuracyMult_i × driftPenalty_i × healthMult_i × driftMult_i
 *   w'_i = w_i / Σ(w_j)  (renormalized to sum = 1.0)
 *
 * policyBaseWeight comes from active RegimePolicy (not static BASE_WEIGHTS).
 * regimeMult still applies on top for fine-tuning.
 */

import { NormalizedSignal } from './signal_normalizer.js';
import { AlignedMetaSignal } from '../contracts/signal.contract.js';
import { REGIME_MULT, HEALTH_MULT } from '../weights/regime_weights.js';
import { RegimePolicy, MetaRegime } from '../policy/policy.contract.js';
import { getAllAccuracyMults, AccuracyInfo } from '../performance/performance.service.js';
import { getAllDriftStates } from '../drift/drift.repo.js';
import { getCorrelationPenalties } from '../correlation/correlation.service.js';

export interface WeightedSignal {
  module: string;
  normalizedScore: number;
  weight: number;
  weightedScore: number;
  rawWeight: number;
  policyBaseWeight: number;
  regimeMult: number;
  accuracyMult: number;
  driftPenalty: number;
  healthMult: number;
  driftMult: number;
  correlationPenalty: number;
}

export interface WeightResult {
  weighted: WeightedSignal[];
  effectiveWeights: Record<string, number>;
  totalWeight: number;
  regime: MetaRegime;
  accuracyInfo: Record<string, AccuracyInfo>;
  driftInfo: Record<string, { score: number; penalty: number; status: string }>;
}

function driftMultiplier(drift: number | undefined): number {
  if (drift === undefined || drift <= 0) return 1.0;
  return Math.exp(-2 * drift);
}

/**
 * Apply policy-driven weights.
 *
 * Weight per module:
 *   w_i = policyBase × regimeMult × accuracyMult × driftPenalty × healthMult × driftMult × correlationPenalty
 *   w'_i = w_i / Σ(w_j) (renormalized)
 */
export async function applyWeights(
  signals: NormalizedSignal[],
  aligned: AlignedMetaSignal[],
  policy: RegimePolicy,
  asset: string = 'BTC',
  horizonDays: number = 7,
): Promise<WeightResult> {
  const regimeMults = REGIME_MULT[policy.regime] ?? REGIME_MULT['TRANSITION'];

  const [accuracyMap, driftStates, corrPenalties] = await Promise.all([
    getAllAccuracyMults(asset, horizonDays),
    getAllDriftStates(asset, horizonDays),
    getCorrelationPenalties(asset, horizonDays),
  ]);

  const driftPenaltyMap: Record<string, { score: number; penalty: number; status: string }> = {};
  for (const ds of driftStates) {
    driftPenaltyMap[ds.moduleId] = { score: ds.driftScore, penalty: ds.penalty, status: ds.status };
  }

  const items: Array<{
    sig: NormalizedSignal;
    pBase: number;
    regM: number;
    accM: number;
    dP: number;
    hM: number;
    dM: number;
    cP: number;
    rawW: number;
  }> = [];

  let sumRaw = 0;

  for (const sig of signals) {
    const raw = aligned.find(s => s.module === sig.module);
    // Policy base weight (regime-specific)
    const pBase = policy.weights[sig.module] ?? 0.1;
    const regM = regimeMults[sig.module] ?? 1.0;
    const accM = accuracyMap[sig.module]?.accuracyMult ?? 1.0;
    const dP = driftPenaltyMap[sig.module]?.penalty ?? 1.0;
    const hM = HEALTH_MULT[raw?.health ?? 'OK'] ?? 1.0;
    const dM = driftMultiplier(raw?.drift);
    const cP = corrPenalties[sig.module] ?? 1.0;

    const rawW = pBase * regM * accM * dP * hM * dM * cP;
    sumRaw += rawW;

    items.push({ sig, pBase, regM, accM, dP, hM, dM, cP, rawW });
  }

  const weighted: WeightedSignal[] = [];
  const effectiveWeights: Record<string, number> = {};

  for (const item of items) {
    const w = sumRaw > 0 ? item.rawW / sumRaw : 0;

    weighted.push({
      module: item.sig.module,
      normalizedScore: item.sig.normalizedScore,
      weight: w,
      weightedScore: w * item.sig.normalizedScore,
      rawWeight: item.rawW,
      policyBaseWeight: item.pBase,
      regimeMult: item.regM,
      accuracyMult: item.accM,
      driftPenalty: item.dP,
      healthMult: item.hM,
      driftMult: item.dM,
      correlationPenalty: item.cP,
    });

    effectiveWeights[item.sig.module] = w;
  }

  return {
    weighted,
    effectiveWeights,
    totalWeight: sumRaw,
    regime: policy.regime,
    accuracyInfo: accuracyMap,
    driftInfo: driftPenaltyMap,
  };
}
