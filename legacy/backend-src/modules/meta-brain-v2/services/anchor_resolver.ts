/**
 * META BRAIN V2 — ANCHOR RESOLVER
 * ================================
 * 
 * Computes the common anchor timestamp (T0) for signal alignment.
 * Mode: LAST_COMPLETE_BUCKET — last completed UTC day boundary.
 * 
 * anchorTs is ONLY set here, never by providers.
 */

import { Horizon } from '../contracts/signal.contract.js';
import { TimeAlignmentPolicy } from '../config/time_alignment.policy.js';

/**
 * Resolve anchor timestamp based on policy.
 */
export function resolveAnchor(
  policy: TimeAlignmentPolicy,
  horizon: Horizon,
  nowTs: number = Date.now()
): number {
  if (policy.anchorMode === 'NOW') {
    return nowTs;
  }

  // LAST_COMPLETE_BUCKET: round down to last completed bucket boundary (UTC 00:00)
  const bucketMs = policy.horizonBucketMs[horizon] || 86_400_000;
  const anchorTs = Math.floor(nowTs / bucketMs) * bucketMs;

  return anchorTs;
}
