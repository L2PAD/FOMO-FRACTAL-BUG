/**
 * META BRAIN V2 — PROVIDER CONTRACT
 * ==================================
 * 
 * Interface that every signal provider MUST implement.
 * Adding a new module = 1 new file implementing this interface + registration.
 * 
 * @sealed v1.0
 */

import { RawMetaSignal, Horizon } from './signal.contract.js';

export interface SignalProviderInput {
  asset: string;
  horizonDays: number;
  horizon: Horizon;
  nowTs: number;
}

export interface MetaSignalProvider {
  /** Unique key for this provider */
  readonly key: string;

  /** Human-readable version */
  readonly version: string;

  /**
   * Fetch signal from the module.
   * Provider MUST set: asOfTs, ttlMs, sourceId.
   * Provider MUST NOT set: anchorTs.
   */
  getSignal(input: SignalProviderInput): Promise<RawMetaSignal>;
}
