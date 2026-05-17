/**
 * META BRAIN V2 — TIME ALIGNMENT POLICY
 * ======================================
 * 
 * Single config file for all time alignment parameters.
 * 
 * @sealed v1.0
 */

import { Horizon } from '../contracts/signal.contract.js';

export interface TimeAlignmentPolicy {
  /** How to pick the common anchor timestamp */
  anchorMode: 'NOW' | 'LAST_COMPLETE_BUCKET';

  /** Max allowed time skew per module (ms) */
  maxSkewMsByModule: Record<string, number>;

  /** Signal TTL per module (ms) — how long a signal is "fresh" */
  ttlMsByModule: Record<string, number>;

  /** Bucket size per horizon (ms) */
  horizonBucketMs: Record<Horizon, number>;

  /** Fallback rules when modules are missing */
  fallback: {
    allowMissingModules: string[];
    minModulesRequired: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// DEFAULT POLICY
// ═══════════════════════════════════════════════════════════════

const HOUR = 3_600_000;
const DAY = 86_400_000;

export const DEFAULT_TIME_POLICY: TimeAlignmentPolicy = {
  anchorMode: 'LAST_COMPLETE_BUCKET',

  maxSkewMsByModule: {
    exchange:  7 * 24 * HOUR,   // Exchange ML runs may be infrequent
    sentiment: 24 * HOUR,       // Sentiment aggregates over 6-24h windows
    onchain:   24 * HOUR,       // On-chain data updates slowly
    fractal:   24 * HOUR,
  },

  ttlMsByModule: {
    exchange:  7 * 24 * HOUR,   // Keep active snapshot valid for 7 days
    sentiment: 24 * HOUR,       // Sentiment valid for 24h
    onchain:   48 * HOUR,
    fractal:   48 * HOUR,
  },

  horizonBucketMs: {
    '1D': DAY,
    '7D': DAY,
    '30D': DAY,
  },

  fallback: {
    allowMissingModules: ['sentiment', 'onchain'],
    minModulesRequired: 2,
  },
};
