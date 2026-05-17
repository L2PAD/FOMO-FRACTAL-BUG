/**
 * META BRAIN V2 — SIGNAL AGGREGATOR (Policy-Driven)
 * ====================================================
 *
 * Full pipeline:
 *   collect → align → normalize → calibrate → gate → policy weights → aggregate → metaConfidence
 *
 * Policy determines: base weights, verdict thresholds, gate rules.
 */

import { Horizon, AlignmentResult } from '../contracts/signal.contract.js';
import { collectSignals } from '../services/signal-collector.service.js';
import { alignSignals } from '../services/signal_alignment.service.js';
import { DEFAULT_TIME_POLICY } from '../config/time_alignment.policy.js';
import { normalizeAll } from './signal_normalizer.js';
import { applyGates, MetaStatus } from './gate_engine.js';
import { applyWeights, WeightedSignal } from './weight_engine.js';
import { getMarketRegime, RegimeResult } from '../weights/market_regime.provider.js';
import { resolvePolicy } from '../policy/policy_resolver.js';
import { RegimePolicy, MetaRegime } from '../policy/policy.contract.js';
import { computeMetaConfidence, MetaConfidenceResult } from '../policy/meta_confidence.service.js';
import { calibrate, CalibrationResult } from '../calibration/calibration.service.js';
import { getProviderCount, getActiveProviderCount } from '../registry/providers.registry.js';

type Direction = 'LONG' | 'SHORT' | 'NEUTRAL';

export interface AggregationResult {
  asset: string;
  horizonDays: number;

  rawScore: number;
  rawVerdict: Direction;
  rawConfidence: number;

  /** Meta Brain's own confidence (entropy/disagreement/coverage adjusted) */
  metaConfidence: MetaConfidenceResult;

  metaStatus: MetaStatus;
  coverage: {
    total: number;
    aligned: number;
    gated: number;
    active: number;
    dropped: number;
  };

  /** Active policy */
  policy: RegimePolicy;
  regime: MetaRegime;
  regimeDetail: RegimeResult;

  weights: Record<string, number>;
  signals: WeightedSignal[];
  driftInfo: Record<string, { score: number; penalty: number; status: string }>;

  /** Calibration info per signal */
  calibrationInfo: Record<string, CalibrationResult>;

  alignment: AlignmentResult;
  gatedModules: Array<{ module: string; reason: string }>;
  durationMs: number;
}

function horizonFromDays(days: number): Horizon {
  if (days <= 1) return '1D';
  if (days <= 7) return '7D';
  return '30D';
}

export async function aggregate(asset: string, horizonDays: number): Promise<AggregationResult> {
  const t0 = Date.now();
  const horizon = horizonFromDays(horizonDays);

  // Stage A: Collect + Regime (parallel)
  const [collected, regimeResult, activeCount] = await Promise.all([
    collectSignals(asset, horizonDays),
    getMarketRegime(asset),
    getActiveProviderCount(),
  ]);

  // Stage B: Resolve policy
  const policy = resolvePolicy(regimeResult.metaRegime);

  // Stage C: Align
  const alignment = alignSignals(
    collected.signals,
    collected.dropped,
    horizon,
    DEFAULT_TIME_POLICY
  );

  // Stage D: Normalize
  const normalized = normalizeAll(alignment.aligned);

  // Stage E: Calibrate confidence (Phase 4)
  const calibrationInfo: Record<string, CalibrationResult> = {};
  for (const norm of normalized) {
    const raw = alignment.aligned.find(s => s.module === norm.module);
    if (raw) {
      const cal = await calibrate(norm.module, asset, horizonDays, raw.confidence);
      calibrationInfo[norm.module] = cal;
      // Replace raw confidence with calibrated in normalization
      if (cal.status === 'CALIBRATED') {
        norm.normalizedScore = (raw.score ?? 0) * cal.confidence;
        norm.rawConfidence = cal.confidence;
      }
    }
  }

  // Stage F: Gate
  const gateResult = applyGates(normalized, alignment.aligned);

  // Stage G: Weight (policy-driven)
  const weightResult = await applyWeights(
    gateResult.passed,
    alignment.aligned,
    policy,
    asset,
    horizonDays,
  );

  // Stage H: Aggregate score
  let rawScore = 0;
  let rawConfidence = 0;

  if (weightResult.weighted.length > 0) {
    rawScore = weightResult.weighted.reduce((sum, w) => sum + w.weightedScore, 0);
    rawConfidence = gateResult.passed.reduce((sum, p) => {
      const w = weightResult.weighted.find(ws => ws.module === p.module);
      return sum + (w?.weight ?? 0) * p.rawConfidence;
    }, 0);
  }

  rawScore = Math.max(-1, Math.min(1, rawScore));
  rawConfidence = Math.max(0, Math.min(1, rawConfidence));

  // Stage I: Raw verdict (policy thresholds)
  let rawVerdict: Direction = 'NEUTRAL';
  if (rawScore >= policy.thresholds.enter) rawVerdict = 'LONG';
  else if (rawScore <= -policy.thresholds.enter) rawVerdict = 'SHORT';

  // Stage J: Meta Confidence (entropy + disagreement + coverage)
  const moduleDirections = weightResult.weighted.map(w => {
    const aligned = alignment.aligned.find(a => a.module === w.module);
    return aligned?.direction ?? 'NEUTRAL';
  });

  const metaConf = computeMetaConfidence(
    rawConfidence,
    moduleDirections,
    rawVerdict,
    activeCount,
    weightResult.weighted.length,
    policy
  );

  return {
    asset,
    horizonDays,
    rawScore,
    rawVerdict,
    rawConfidence,
    metaConfidence: metaConf,
    metaStatus: gateResult.metaStatus,
    coverage: {
      total: activeCount,
      aligned: alignment.coverage.aligned,
      gated: gateResult.gated.length,
      active: gateResult.passed.length,
      dropped: alignment.coverage.dropped,
    },
    policy,
    regime: regimeResult.metaRegime,
    regimeDetail: regimeResult,
    weights: weightResult.effectiveWeights,
    signals: weightResult.weighted,
    driftInfo: weightResult.driftInfo,
    calibrationInfo,
    alignment,
    gatedModules: gateResult.gated,
    durationMs: Date.now() - t0,
  };
}
