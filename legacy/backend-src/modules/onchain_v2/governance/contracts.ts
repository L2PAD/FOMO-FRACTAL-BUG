/**
 * OnChain V2 — Governance Contracts
 * ==================================
 * 
 * Types for 30-day institutional governance model.
 * 
 * PHILOSOPHY:
 * - Manual control, NOT automated trading
 * - Explicit decisions, NOT implicit signals
 * - Audit trail, NOT black box
 * - Conservative defaults, NOT aggressive optimization
 */

// ═══════════════════════════════════════════════════════════════
// POLICY: Weights & Thresholds
// ═══════════════════════════════════════════════════════════════

export interface OnchainGovWeights {
  exchangePressureWeight: number;  // 0..1
  flowScoreWeight: number;         // 0..1
  whaleActivityWeight: number;     // 0..1
  networkHeatWeight: number;       // 0..1
  velocityWeight: number;          // 0..1
  distributionSkewWeight: number;  // 0..1
}

export interface OnchainGovThresholds {
  minUsableConfidence: number;   // 0..1, default 0.40
  strongInflow: number;          // 0..1, default 0.30
  moderateInflow: number;        // 0..1, default 0.15
  strongOutflow: number;         // 0..1, default -0.30
  moderateOutflow: number;       // 0..1, default -0.15
  neutralZone: number;           // Width of neutral zone, default 0.10
}

export interface OnchainGovGuardrails {
  providerHealthyRequired: boolean;  // Must have healthy provider
  minSamples30d: number;             // Minimum observations in 30d window
  driftMaxPsi: number;               // Max PSI before blocking
  crisisBlock: boolean;              // Block if crisis detected
  maxLatencyMs: number;              // Max acceptable latency
  requireManualApproval: boolean;    // Require human approval for changes
}

export type OnchainGovPolicyStatus = 'DRAFT' | 'PROPOSED' | 'ACTIVE' | 'ARCHIVED';

export interface OnchainGovPolicy {
  id: string;
  version: string;
  name: string;
  description: string;
  
  weights: OnchainGovWeights;
  thresholds: OnchainGovThresholds;
  guardrails: OnchainGovGuardrails;
  
  status: OnchainGovPolicyStatus;
  createdAt: number;
  createdBy: string;
  activatedAt?: number;
  activatedBy?: string;
  archivedAt?: number;
  archivedBy?: string;
}

// ═══════════════════════════════════════════════════════════════
// STATE: Active Governance State
// ═══════════════════════════════════════════════════════════════

export interface OnchainGovState {
  activePolicyId: string | null;
  activePolicyVersion: string | null;
  updatedAt: number;
  updatedBy: string;
  notes: string[];
  
  // Runtime state
  isHealthy: boolean;
  lastHealthCheck: number;
  guardrailsPass: boolean;
  guardrailsViolations: string[];
}

// ═══════════════════════════════════════════════════════════════
// DECISION: Governance Decision Output
// ═══════════════════════════════════════════════════════════════

export type OnchainGovDecisionType = 'ALLOW' | 'BLOCK' | 'SAFE_MODE';

export interface OnchainGovDecision {
  decision: OnchainGovDecisionType;
  reasons: string[];
  guardrailsEvaluation: {
    providerHealthy: boolean;
    sampleCount30d: number;
    driftPsi30d: number;
    crisisFlag: boolean;
    allPassed: boolean;
  };
  policyId: string | null;
  evaluatedAt: number;
}

// ═══════════════════════════════════════════════════════════════
// AUDIT: Immutable Audit Log Entry
// ═══════════════════════════════════════════════════════════════

export type OnchainGovAuditAction = 
  | 'POLICY_CREATED'
  | 'POLICY_PROPOSED'
  | 'POLICY_ACTIVATED'
  | 'POLICY_ARCHIVED'
  | 'STATE_UPDATED'
  | 'GUARDRAILS_VIOLATION'
  | 'DECISION_MADE'
  | 'MANUAL_OVERRIDE'
  | 'PROVIDER_RESET';

export interface OnchainGovAuditEntry {
  id: string;
  action: OnchainGovAuditAction;
  actor: string;
  timestamp: number;
  
  policyId?: string;
  previousPolicyId?: string;
  decision?: OnchainGovDecisionType;
  
  details: Record<string, any>;
  notes?: string;
}

// ═══════════════════════════════════════════════════════════════
// DRY RUN: Policy Simulation
// ═══════════════════════════════════════════════════════════════

export interface OnchainGovDryRunResult {
  ok: boolean;
  policy: OnchainGovPolicy;
  guardrailsEvaluation: OnchainGovDecision['guardrailsEvaluation'];
  computedDeltas: {
    weightsDelta: Partial<OnchainGovWeights>;
    thresholdsDelta: Partial<OnchainGovThresholds>;
    guardrailsDelta: Partial<OnchainGovGuardrails>;
  };
  warnings: string[];
  wouldAllow: boolean;
  simulatedAt: number;
}

// ═══════════════════════════════════════════════════════════════
// DEFAULT POLICY v1
// ═══════════════════════════════════════════════════════════════

export const DEFAULT_POLICY_V1: Omit<OnchainGovPolicy, 'id' | 'createdAt' | 'createdBy'> = {
  version: '1.0.0',
  name: 'Default Conservative Policy',
  description: 'Initial conservative policy for OnChain V2 governance. Prioritizes stability over sensitivity.',
  
  weights: {
    exchangePressureWeight: 0.35,
    flowScoreWeight: 0.25,
    whaleActivityWeight: 0.20,
    networkHeatWeight: 0.10,
    velocityWeight: 0.05,
    distributionSkewWeight: 0.05,
  },
  
  thresholds: {
    minUsableConfidence: 0.40,
    strongInflow: 0.30,
    moderateInflow: 0.15,
    strongOutflow: -0.30,
    moderateOutflow: -0.15,
    neutralZone: 0.10,
  },
  
  guardrails: {
    providerHealthyRequired: true,
    minSamples30d: 200,
    driftMaxPsi: 0.20,
    crisisBlock: true,
    maxLatencyMs: 5000,
    requireManualApproval: true,
  },
  
  status: 'ACTIVE',
};

console.log('[OnChain V2] Governance Contracts loaded');
