/**
 * META BRAIN V2 — POLICY RESOLVER
 * =================================
 *
 * Resolves active regime policy. Falls back to TRANSITION.
 */

import { RegimePolicy, MetaRegime } from './policy.contract.js';
import { META_BRAIN_POLICIES } from './meta_brain_policies.js';

export function resolvePolicy(regime: MetaRegime): RegimePolicy {
  return META_BRAIN_POLICIES[regime] ?? META_BRAIN_POLICIES['TRANSITION'];
}

export function getAllPolicies(): Record<string, RegimePolicy> {
  return META_BRAIN_POLICIES;
}
