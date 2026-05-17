/**
 * META BRAIN V2 — GATE ENGINE
 * ============================
 *
 * Pre-weight filters:
 *   - Health gate: FAIL → drop
 *   - Drift gate: high drift → score penalty
 *   - Coverage guard: determines metaStatus (dynamic, based on provider count)
 */

import { AlignedMetaSignal } from '../contracts/signal.contract.js';
import { NormalizedSignal } from './signal_normalizer.js';
import { getProviderCount } from '../registry/providers.registry.js';

export type MetaStatus = 'OK' | 'DEGRADED' | 'INSUFFICIENT';

export interface GateResult {
  passed: NormalizedSignal[];
  gated: Array<{ module: string; reason: string }>;
  metaStatus: MetaStatus;
  alignedCount: number;
}

/**
 * Apply gates to normalized signals.
 */
export function applyGates(
  normalized: NormalizedSignal[],
  aligned: AlignedMetaSignal[]
): GateResult {
  const passed: NormalizedSignal[] = [];
  const gated: Array<{ module: string; reason: string }> = [];

  for (const norm of normalized) {
    const raw = aligned.find(s => s.module === norm.module);
    if (!raw) {
      gated.push({ module: norm.module, reason: 'NO_RAW_SIGNAL' });
      continue;
    }

    // Health gate
    if (raw.health === 'FAIL') {
      gated.push({ module: norm.module, reason: 'HEALTH_FAIL' });
      continue;
    }

    // Drift gate: high drift → reduce score but don't drop
    if (raw.drift && raw.drift > 0.7) {
      norm.normalizedScore *= 0.5;
    }

    passed.push(norm);
  }

  // Coverage guard — dynamic thresholds based on registered providers
  const totalProviders = getProviderCount();
  const okThreshold = Math.max(2, Math.ceil(totalProviders * 0.6));    // 60%+ → OK
  const degradedThreshold = Math.max(1, Math.ceil(totalProviders * 0.4)); // 40%+ → DEGRADED

  const alignedCount = normalized.length;
  let metaStatus: MetaStatus = 'OK';
  if (passed.length >= okThreshold) metaStatus = 'OK';
  else if (passed.length >= degradedThreshold) metaStatus = 'DEGRADED';
  else metaStatus = 'INSUFFICIENT';

  return { passed, gated, metaStatus, alignedCount };
}
