/**
 * OnChain V2 — Governance Service
 * =================================
 * 
 * Core governance logic:
 * - Policy management (CRUD + versioning)
 * - State management (active policy tracking)
 * - Guardrails evaluation
 * - Audit logging
 * 
 * PHILOSOPHY:
 * - All changes are explicit and audited
 * - No automatic policy switches
 * - Dry-run before apply
 */

import { randomUUID } from 'crypto';
import {
  OnchainGovPolicy,
  OnchainGovState,
  OnchainGovDecision,
  OnchainGovAuditEntry,
  OnchainGovDryRunResult,
  OnchainGovWeights,
  OnchainGovThresholds,
  OnchainGovGuardrails,
  OnchainGovPolicyStatus,
  OnchainGovDecisionType,
  DEFAULT_POLICY_V1,
} from './contracts.js';

import {
  OnchainGovPolicyModel,
  OnchainGovStateModel,
  OnchainGovAuditModel,
  IOnchainGovPolicyDoc,
  IOnchainGovStateDoc,
} from './models.js';

import { getOnchainProvider, isProviderInitialized } from '../providers/index.js';
import { OnchainObservationModel } from '../core/persistence/models.js';

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function generatePolicyId(): string {
  return `pol_${randomUUID().split('-')[0]}`;
}

function generateAuditId(): string {
  return `aud_${Date.now()}_${randomUUID().split('-')[0]}`;
}

function docToPolicy(doc: IOnchainGovPolicyDoc): OnchainGovPolicy {
  return {
    id: doc.id,
    version: doc.version,
    name: doc.name,
    description: doc.description,
    weights: doc.weights,
    thresholds: doc.thresholds,
    guardrails: doc.guardrails,
    status: doc.status,
    createdAt: doc.createdAt,
    createdBy: doc.createdBy,
    activatedAt: doc.activatedAt,
    activatedBy: doc.activatedBy,
    archivedAt: doc.archivedAt,
    archivedBy: doc.archivedBy,
  };
}

function docToState(doc: IOnchainGovStateDoc): OnchainGovState {
  return {
    activePolicyId: doc.activePolicyId,
    activePolicyVersion: doc.activePolicyVersion,
    updatedAt: doc.updatedAt,
    updatedBy: doc.updatedBy,
    notes: doc.notes || [],
    isHealthy: doc.isHealthy,
    lastHealthCheck: doc.lastHealthCheck,
    guardrailsPass: doc.guardrailsPass,
    guardrailsViolations: doc.guardrailsViolations || [],
  };
}

// ═══════════════════════════════════════════════════════════════
// GOVERNANCE SERVICE
// ═══════════════════════════════════════════════════════════════

export class OnchainGovernanceService {
  private initialized = false;
  
  // ─────────────────────────────────────────────────────────────
  // INITIALIZATION
  // ─────────────────────────────────────────────────────────────
  
  async initialize(): Promise<void> {
    if (this.initialized) return;
    
    // Ensure state document exists
    const state = await OnchainGovStateModel.findOne({ key: 'ACTIVE_STATE' });
    if (!state) {
      await OnchainGovStateModel.create({
        key: 'ACTIVE_STATE',
        activePolicyId: null,
        activePolicyVersion: null,
        updatedAt: Date.now(),
        updatedBy: 'SYSTEM',
        notes: ['Initial state created'],
        isHealthy: false,
        lastHealthCheck: 0,
        guardrailsPass: true,
        guardrailsViolations: [],
      });
      console.log('[Governance] Initial state created');
    }
    
    // Ensure default policy exists
    const activePolicy = await OnchainGovPolicyModel.findOne({ status: 'ACTIVE' });
    if (!activePolicy) {
      await this.seedDefaultPolicy();
    }
    
    this.initialized = true;
    console.log('[Governance] Service initialized');
  }
  
  private async seedDefaultPolicy(): Promise<void> {
    const policyId = generatePolicyId();
    const now = Date.now();
    
    const policy = {
      id: policyId,
      ...DEFAULT_POLICY_V1,
      createdAt: now,
      createdBy: 'SYSTEM',
      activatedAt: now,
      activatedBy: 'SYSTEM',
    };
    
    await OnchainGovPolicyModel.create(policy);
    
    // Update state
    await OnchainGovStateModel.findOneAndUpdate(
      { key: 'ACTIVE_STATE' },
      {
        activePolicyId: policyId,
        activePolicyVersion: DEFAULT_POLICY_V1.version,
        updatedAt: now,
        updatedBy: 'SYSTEM',
        $push: { notes: 'Default policy v1 activated' },
      }
    );
    
    // Audit log
    await this.logAudit({
      action: 'POLICY_ACTIVATED',
      actor: 'SYSTEM',
      policyId,
      details: { reason: 'Initial seed', version: DEFAULT_POLICY_V1.version },
    });
    
    console.log(`[Governance] Default policy seeded: ${policyId}`);
  }
  
  // ─────────────────────────────────────────────────────────────
  // POLICY MANAGEMENT
  // ─────────────────────────────────────────────────────────────
  
  async getActivePolicy(): Promise<OnchainGovPolicy | null> {
    await this.initialize();
    
    const policy = await OnchainGovPolicyModel.findOne({ status: 'ACTIVE' });
    return policy ? docToPolicy(policy) : null;
  }
  
  async getPolicyById(policyId: string): Promise<OnchainGovPolicy | null> {
    const policy = await OnchainGovPolicyModel.findOne({ id: policyId });
    return policy ? docToPolicy(policy) : null;
  }
  
  async listPolicies(status?: OnchainGovPolicyStatus): Promise<OnchainGovPolicy[]> {
    const query = status ? { status } : {};
    const policies = await OnchainGovPolicyModel.find(query).sort({ createdAt: -1 });
    return policies.map(docToPolicy);
  }
  
  async proposePolicy(
    draft: {
      name: string;
      description?: string;
      version: string;
      weights: OnchainGovWeights;
      thresholds: OnchainGovThresholds;
      guardrails: OnchainGovGuardrails;
    },
    actor: string
  ): Promise<OnchainGovPolicy> {
    await this.initialize();
    
    const policyId = generatePolicyId();
    const now = Date.now();
    
    // Validate weights sum to ~1
    const weightsSum = Object.values(draft.weights).reduce((a, b) => a + b, 0);
    if (Math.abs(weightsSum - 1.0) > 0.01) {
      throw new Error(`Weights must sum to 1.0, got ${weightsSum.toFixed(3)}`);
    }
    
    const policy: OnchainGovPolicy = {
      id: policyId,
      version: draft.version,
      name: draft.name,
      description: draft.description || '',
      weights: draft.weights,
      thresholds: draft.thresholds,
      guardrails: draft.guardrails,
      status: 'PROPOSED',
      createdAt: now,
      createdBy: actor,
    };
    
    await OnchainGovPolicyModel.create(policy);
    
    await this.logAudit({
      action: 'POLICY_PROPOSED',
      actor,
      policyId,
      details: { version: draft.version, name: draft.name },
    });
    
    return policy;
  }
  
  async applyPolicy(policyId: string, actor: string): Promise<OnchainGovState> {
    await this.initialize();
    
    // Get proposed policy
    const policy = await OnchainGovPolicyModel.findOne({ id: policyId });
    if (!policy) {
      throw new Error(`Policy not found: ${policyId}`);
    }
    
    if (policy.status !== 'PROPOSED' && policy.status !== 'DRAFT') {
      throw new Error(`Policy must be PROPOSED or DRAFT to apply, got ${policy.status}`);
    }
    
    // Evaluate guardrails
    const guardrailsEval = await this.evaluateGuardrails(policy.guardrails);
    if (!guardrailsEval.allPassed) {
      throw new Error(`Guardrails failed: ${guardrailsEval.reasons?.join(', ')}`);
    }
    
    const now = Date.now();
    
    // Archive current active policy
    const currentState = await this.getState();
    if (currentState.activePolicyId) {
      await OnchainGovPolicyModel.findOneAndUpdate(
        { id: currentState.activePolicyId },
        { status: 'ARCHIVED', archivedAt: now, archivedBy: actor }
      );
      
      await this.logAudit({
        action: 'POLICY_ARCHIVED',
        actor,
        policyId: currentState.activePolicyId,
        details: { reason: 'Replaced by new policy' },
      });
    }
    
    // Activate new policy
    await OnchainGovPolicyModel.findOneAndUpdate(
      { id: policyId },
      { status: 'ACTIVE', activatedAt: now, activatedBy: actor }
    );
    
    // Update state
    const updatedState = await OnchainGovStateModel.findOneAndUpdate(
      { key: 'ACTIVE_STATE' },
      {
        activePolicyId: policyId,
        activePolicyVersion: policy.version,
        updatedAt: now,
        updatedBy: actor,
        $push: { notes: `Policy ${policyId} activated` },
      },
      { new: true }
    );
    
    await this.logAudit({
      action: 'POLICY_ACTIVATED',
      actor,
      policyId,
      previousPolicyId: currentState.activePolicyId || undefined,
      details: { version: policy.version },
    });
    
    return docToState(updatedState!);
  }
  
  // ─────────────────────────────────────────────────────────────
  // DRY RUN
  // ─────────────────────────────────────────────────────────────
  
  async dryRun(
    draft: {
      weights: OnchainGovWeights;
      thresholds: OnchainGovThresholds;
      guardrails: OnchainGovGuardrails;
    }
  ): Promise<OnchainGovDryRunResult> {
    await this.initialize();
    
    const activePolicy = await this.getActivePolicy();
    const guardrailsEval = await this.evaluateGuardrails(draft.guardrails);
    
    // Compute deltas
    const weightsDelta: Partial<OnchainGovWeights> = {};
    const thresholdsDelta: Partial<OnchainGovThresholds> = {};
    const guardrailsDelta: Partial<OnchainGovGuardrails> = {};
    
    if (activePolicy) {
      for (const [key, value] of Object.entries(draft.weights)) {
        const oldValue = (activePolicy.weights as any)[key];
        if (Math.abs(value - oldValue) > 0.001) {
          (weightsDelta as any)[key] = value - oldValue;
        }
      }
      
      for (const [key, value] of Object.entries(draft.thresholds)) {
        const oldValue = (activePolicy.thresholds as any)[key];
        if (Math.abs(value - oldValue) > 0.001) {
          (thresholdsDelta as any)[key] = value - oldValue;
        }
      }
      
      for (const [key, value] of Object.entries(draft.guardrails)) {
        const oldValue = (activePolicy.guardrails as any)[key];
        if (value !== oldValue) {
          (guardrailsDelta as any)[key] = value;
        }
      }
    }
    
    const warnings: string[] = [];
    
    // Validate weights sum
    const weightsSum = Object.values(draft.weights).reduce((a, b) => a + b, 0);
    if (Math.abs(weightsSum - 1.0) > 0.01) {
      warnings.push(`Weights sum to ${weightsSum.toFixed(3)}, should be 1.0`);
    }
    
    // Check if guardrails are too loose
    if (draft.guardrails.minSamples30d < 100) {
      warnings.push('minSamples30d < 100 may be too loose');
    }
    if (draft.guardrails.driftMaxPsi > 0.3) {
      warnings.push('driftMaxPsi > 0.3 may be too permissive');
    }
    
    return {
      ok: guardrailsEval.allPassed && warnings.length === 0,
      policy: {
        id: 'DRY_RUN',
        version: 'preview',
        name: 'Dry Run Preview',
        description: '',
        weights: draft.weights,
        thresholds: draft.thresholds,
        guardrails: draft.guardrails,
        status: 'DRAFT',
        createdAt: Date.now(),
        createdBy: 'DRY_RUN',
      },
      guardrailsEvaluation: guardrailsEval,
      computedDeltas: {
        weightsDelta,
        thresholdsDelta,
        guardrailsDelta,
      },
      warnings,
      wouldAllow: guardrailsEval.allPassed,
      simulatedAt: Date.now(),
    };
  }
  
  // ─────────────────────────────────────────────────────────────
  // STATE MANAGEMENT
  // ─────────────────────────────────────────────────────────────
  
  async getState(): Promise<OnchainGovState> {
    await this.initialize();
    
    const state = await OnchainGovStateModel.findOne({ key: 'ACTIVE_STATE' });
    if (!state) {
      throw new Error('Governance state not initialized');
    }
    
    return docToState(state);
  }
  
  async updateHealthStatus(): Promise<OnchainGovState> {
    await this.initialize();
    
    const guardrailsEval = await this.evaluateGuardrails();
    const now = Date.now();
    
    const state = await OnchainGovStateModel.findOneAndUpdate(
      { key: 'ACTIVE_STATE' },
      {
        isHealthy: guardrailsEval.allPassed,
        lastHealthCheck: now,
        guardrailsPass: guardrailsEval.allPassed,
        guardrailsViolations: guardrailsEval.reasons || [],
        updatedAt: now,
        updatedBy: 'HEALTH_CHECK',
      },
      { new: true }
    );
    
    if (!guardrailsEval.allPassed) {
      await this.logAudit({
        action: 'GUARDRAILS_VIOLATION',
        actor: 'HEALTH_CHECK',
        details: {
          violations: guardrailsEval.reasons,
          evaluation: guardrailsEval,
        },
      });
    }
    
    return docToState(state!);
  }
  
  // ─────────────────────────────────────────────────────────────
  // GUARDRAILS EVALUATION
  // ─────────────────────────────────────────────────────────────
  
  async evaluateGuardrails(
    guardrails?: OnchainGovGuardrails
  ): Promise<OnchainGovDecision['guardrailsEvaluation'] & { reasons?: string[] }> {
    // Use active policy guardrails if not provided
    if (!guardrails) {
      const activePolicy = await this.getActivePolicy();
      guardrails = activePolicy?.guardrails || DEFAULT_POLICY_V1.guardrails;
    }
    
    const reasons: string[] = [];
    
    // 1. Provider health
    let providerHealthy = false;
    try {
      if (isProviderInitialized()) {
        const provider = getOnchainProvider();
        const health = await provider.getHealth();
        providerHealthy = health.status === 'UP';
      }
    } catch {
      providerHealthy = false;
    }
    
    if (guardrails.providerHealthyRequired && !providerHealthy) {
      reasons.push('PROVIDER_NOT_HEALTHY');
    }
    
    // 2. Sample count (30d)
    const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
    const sampleCount30d = await OnchainObservationModel.countDocuments({
      createdAt: { $gte: thirtyDaysAgo },
    });
    
    if (sampleCount30d < guardrails.minSamples30d) {
      reasons.push(`INSUFFICIENT_SAMPLES: ${sampleCount30d} < ${guardrails.minSamples30d}`);
    }
    
    // 3. Drift PSI (simplified - would need real drift calculation)
    const driftPsi30d = 0.05;  // Placeholder
    
    if (driftPsi30d > guardrails.driftMaxPsi) {
      reasons.push(`DRIFT_EXCEEDED: ${driftPsi30d.toFixed(3)} > ${guardrails.driftMaxPsi}`);
    }
    
    // 4. Crisis flag (simplified)
    const crisisFlag = false;  // Would check market conditions
    
    if (guardrails.crisisBlock && crisisFlag) {
      reasons.push('CRISIS_DETECTED');
    }
    
    return {
      providerHealthy,
      sampleCount30d,
      driftPsi30d,
      crisisFlag,
      allPassed: reasons.length === 0,
      reasons: reasons.length > 0 ? reasons : undefined,
    };
  }
  
  // ─────────────────────────────────────────────────────────────
  // DECISION MAKING
  // ─────────────────────────────────────────────────────────────
  
  async makeDecision(): Promise<OnchainGovDecision> {
    await this.initialize();
    
    const state = await this.getState();
    const guardrailsEval = await this.evaluateGuardrails();
    
    let decision: OnchainGovDecisionType;
    const reasons: string[] = [];
    
    if (!state.activePolicyId) {
      decision = 'BLOCK';
      reasons.push('NO_ACTIVE_POLICY');
    } else if (!guardrailsEval.allPassed) {
      decision = 'SAFE_MODE';
      reasons.push(...(guardrailsEval.reasons || []));
    } else {
      decision = 'ALLOW';
      reasons.push('ALL_GUARDRAILS_PASSED');
    }
    
    await this.logAudit({
      action: 'DECISION_MADE',
      actor: 'GOVERNANCE_ENGINE',
      policyId: state.activePolicyId || undefined,
      decision,
      details: { guardrailsEval },
    });
    
    return {
      decision,
      reasons,
      guardrailsEvaluation: guardrailsEval,
      policyId: state.activePolicyId,
      evaluatedAt: Date.now(),
    };
  }
  
  // ─────────────────────────────────────────────────────────────
  // AUDIT LOGGING
  // ─────────────────────────────────────────────────────────────
  
  async logAudit(entry: Omit<OnchainGovAuditEntry, 'id' | 'timestamp'>): Promise<void> {
    await OnchainGovAuditModel.create({
      id: generateAuditId(),
      ...entry,
      timestamp: Date.now(),
    });
  }
  
  async getAuditLog(limit = 50, action?: string): Promise<OnchainGovAuditEntry[]> {
    const query = action ? { action } : {};
    const entries = await OnchainGovAuditModel
      .find(query)
      .sort({ timestamp: -1 })
      .limit(limit);
    
    return entries.map(doc => ({
      id: doc.id,
      action: doc.action,
      actor: doc.actor,
      timestamp: doc.timestamp,
      policyId: doc.policyId,
      previousPolicyId: doc.previousPolicyId,
      decision: doc.decision as OnchainGovDecisionType | undefined,
      details: doc.details || {},
      notes: doc.notes,
    }));
  }
}

// Singleton instance
export const governanceService = new OnchainGovernanceService();

console.log('[OnChain V2] Governance Service loaded');
