/**
 * META BRAIN V2 — SIGNAL COLLECTOR
 * =================================
 * 
 * Parallel collection with per-provider timeout.
 * If a provider hangs → FAIL with reason=TIMEOUT.
 * If a provider throws → FAIL with reason=ERROR.
 * 
 * Meta Brain must NEVER hang.
 */

import { RawMetaSignal, Horizon, DroppedSignal } from '../contracts/signal.contract.js';
import { SignalProviderInput } from '../contracts/provider.contract.js';
import { getActiveProviders } from '../registry/providers.registry.js';

const PROVIDER_TIMEOUT_MS = 5000;

interface CollectorResult {
  signals: RawMetaSignal[];
  dropped: DroppedSignal[];
  durationMs: number;
}

function horizonFromDays(days: number): Horizon {
  if (days <= 1) return '1D';
  if (days <= 7) return '7D';
  return '30D';
}

async function fetchWithTimeout(
  provider: { key: string; getSignal: (input: SignalProviderInput) => Promise<RawMetaSignal> },
  input: SignalProviderInput,
  timeoutMs: number
): Promise<RawMetaSignal | DroppedSignal> {
  return Promise.race([
    provider.getSignal(input).catch((err: any) => ({
      module: provider.key,
      reason: 'ERROR' as const,
      detail: String(err?.message || err),
    })),
    new Promise<DroppedSignal>((resolve) =>
      setTimeout(() => resolve({
        module: provider.key,
        reason: 'TIMEOUT' as const,
        detail: `Provider exceeded ${timeoutMs}ms`,
      }), timeoutMs)
    ),
  ]);
}

function isDropped(result: any): result is DroppedSignal {
  return 'reason' in result && !('score' in result);
}

/**
 * Collect signals from all registered providers in parallel.
 */
export async function collectSignals(
  asset: string,
  horizonDays: number
): Promise<CollectorResult> {
  const t0 = Date.now();
  const horizon = horizonFromDays(horizonDays);

  const input: SignalProviderInput = {
    asset: asset.toUpperCase(),
    horizonDays,
    horizon,
    nowTs: Date.now(),
  };

  const results = await Promise.all(
    (await getActiveProviders()).map(p => fetchWithTimeout(p, input, PROVIDER_TIMEOUT_MS))
  );

  const signals: RawMetaSignal[] = [];
  const dropped: DroppedSignal[] = [];

  for (const r of results) {
    if (isDropped(r)) {
      dropped.push(r);
    } else {
      signals.push(r);
    }
  }

  return {
    signals,
    dropped,
    durationMs: Date.now() - t0,
  };
}
