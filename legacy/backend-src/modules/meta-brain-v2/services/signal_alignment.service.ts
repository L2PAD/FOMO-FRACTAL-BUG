/**
 * META BRAIN V2 — SIGNAL ALIGNMENT SERVICE
 * ==========================================
 * 
 * Aligns raw signals to a common anchor timestamp.
 * 
 * For each signal:
 *   1. Check freshness: now - asOfTs <= ttlMs
 *   2. Check skew:      abs(asOfTs - anchorTs) <= maxSkewMs
 *   3. If both pass → aligned (anchorTs added)
 *   4. If either fails → dropped (with reason)
 * 
 * anchorTs is computed by anchor_resolver, NOT by providers.
 */

import {
  RawMetaSignal,
  AlignedMetaSignal,
  DroppedSignal,
  AlignmentResult,
  Horizon,
} from '../contracts/signal.contract.js';
import { TimeAlignmentPolicy, DEFAULT_TIME_POLICY } from '../config/time_alignment.policy.js';
import { resolveAnchor } from './anchor_resolver.js';
import { getProviderCount } from '../registry/providers.registry.js';

/**
 * Align a set of raw signals + already-dropped signals.
 */
export function alignSignals(
  rawSignals: RawMetaSignal[],
  alreadyDropped: DroppedSignal[],
  horizon: Horizon,
  policy: TimeAlignmentPolicy = DEFAULT_TIME_POLICY,
  nowTs: number = Date.now()
): AlignmentResult {
  const anchorTs = resolveAnchor(policy, horizon, nowTs);
  const aligned: AlignedMetaSignal[] = [];
  const dropped: DroppedSignal[] = [...alreadyDropped];

  for (const signal of rawSignals) {
    const moduleTtl = policy.ttlMsByModule[signal.module] ?? signal.ttlMs;
    const moduleSkew = policy.maxSkewMsByModule[signal.module] ?? 24 * 3_600_000;

    // 1. Freshness check
    const age = nowTs - signal.asOfTs;
    if (age > moduleTtl) {
      dropped.push({
        module: signal.module,
        reason: 'STALE',
        asOfTs: signal.asOfTs,
        ttlMs: moduleTtl,
        detail: `Age ${Math.round(age/3_600_000)}h exceeds TTL ${Math.round(moduleTtl/3_600_000)}h`,
      });
      continue;
    }

    // 2. Skew check
    const skew = Math.abs(signal.asOfTs - anchorTs);
    if (skew > moduleSkew) {
      dropped.push({
        module: signal.module,
        reason: 'SKEW',
        asOfTs: signal.asOfTs,
        detail: `Skew ${Math.round(skew/3_600_000)}h exceeds max ${Math.round(moduleSkew/3_600_000)}h`,
      });
      continue;
    }

    // 3. Passed both checks → align
    aligned.push({
      ...signal,
      anchorTs,
    });
  }

  const total = getProviderCount();
  return {
    anchorTs,
    coverage: {
      total,
      aligned: aligned.length,
      dropped: dropped.length,
    },
    aligned,
    dropped,
  };
}
