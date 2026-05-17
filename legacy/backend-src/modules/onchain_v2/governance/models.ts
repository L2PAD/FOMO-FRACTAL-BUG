/**
 * OnChain V2 — Governance Models (MongoDB)
 * =========================================
 * 
 * Persistence layer for governance:
 * - Policies (versioned, immutable once activated)
 * - State (single active state document)
 * - Audit Log (append-only)
 */

import mongoose, { Schema, Document, Types } from 'mongoose';
import {
  OnchainGovPolicy,
  OnchainGovState,
  OnchainGovAuditEntry,
  OnchainGovWeights,
  OnchainGovThresholds,
  OnchainGovGuardrails,
  OnchainGovPolicyStatus,
  OnchainGovAuditAction,
} from './contracts.js';

// ═══════════════════════════════════════════════════════════════
// 1. POLICY MODEL
// ═══════════════════════════════════════════════════════════════

export interface IOnchainGovPolicyDoc extends Document {
  _id: Types.ObjectId;
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

const WeightsSchema = new Schema<OnchainGovWeights>({
  exchangePressureWeight: { type: Number, required: true, min: 0, max: 1 },
  flowScoreWeight: { type: Number, required: true, min: 0, max: 1 },
  whaleActivityWeight: { type: Number, required: true, min: 0, max: 1 },
  networkHeatWeight: { type: Number, required: true, min: 0, max: 1 },
  velocityWeight: { type: Number, required: true, min: 0, max: 1 },
  distributionSkewWeight: { type: Number, required: true, min: 0, max: 1 },
}, { _id: false });

const ThresholdsSchema = new Schema<OnchainGovThresholds>({
  minUsableConfidence: { type: Number, required: true, min: 0, max: 1 },
  strongInflow: { type: Number, required: true },
  moderateInflow: { type: Number, required: true },
  strongOutflow: { type: Number, required: true },
  moderateOutflow: { type: Number, required: true },
  neutralZone: { type: Number, required: true, min: 0 },
}, { _id: false });

const GuardrailsSchema = new Schema<OnchainGovGuardrails>({
  providerHealthyRequired: { type: Boolean, required: true },
  minSamples30d: { type: Number, required: true, min: 0 },
  driftMaxPsi: { type: Number, required: true, min: 0 },
  crisisBlock: { type: Boolean, required: true },
  maxLatencyMs: { type: Number, required: true, min: 0 },
  requireManualApproval: { type: Boolean, required: true },
}, { _id: false });

const OnchainGovPolicySchema = new Schema<IOnchainGovPolicyDoc>({
  id: { type: String, required: true, unique: true, index: true },
  version: { type: String, required: true },
  name: { type: String, required: true },
  description: { type: String, default: '' },
  
  weights: { type: WeightsSchema, required: true },
  thresholds: { type: ThresholdsSchema, required: true },
  guardrails: { type: GuardrailsSchema, required: true },
  
  status: { 
    type: String, 
    required: true, 
    enum: ['DRAFT', 'PROPOSED', 'ACTIVE', 'ARCHIVED'],
    default: 'DRAFT',
    index: true,
  },
  
  createdAt: { type: Number, required: true },
  createdBy: { type: String, required: true },
  activatedAt: { type: Number },
  activatedBy: { type: String },
  archivedAt: { type: Number },
  archivedBy: { type: String },
}, {
  collection: 'onchain_v2_gov_policies',
});

OnchainGovPolicySchema.index({ status: 1, createdAt: -1 });

export const OnchainGovPolicyModel = mongoose.models.OnchainV2GovPolicy ||
  mongoose.model<IOnchainGovPolicyDoc>('OnchainV2GovPolicy', OnchainGovPolicySchema, 'onchain_v2_policies');

// ═══════════════════════════════════════════════════════════════
// 2. STATE MODEL (Single Document)
// ═══════════════════════════════════════════════════════════════

export interface IOnchainGovStateDoc extends Document {
  _id: Types.ObjectId;
  key: string;  // Always 'ACTIVE_STATE'
  activePolicyId: string | null;
  activePolicyVersion: string | null;
  updatedAt: number;
  updatedBy: string;
  notes: string[];
  
  isHealthy: boolean;
  lastHealthCheck: number;
  guardrailsPass: boolean;
  guardrailsViolations: string[];
}

const OnchainGovStateSchema = new Schema<IOnchainGovStateDoc>({
  key: { type: String, required: true, unique: true, default: 'ACTIVE_STATE' },
  activePolicyId: { type: String, default: null },
  activePolicyVersion: { type: String, default: null },
  updatedAt: { type: Number, required: true },
  updatedBy: { type: String, required: true },
  notes: [{ type: String }],
  
  isHealthy: { type: Boolean, default: false },
  lastHealthCheck: { type: Number, default: 0 },
  guardrailsPass: { type: Boolean, default: true },
  guardrailsViolations: [{ type: String }],
}, {
  collection: 'onchain_v2_gov_state',
});

export const OnchainGovStateModel = mongoose.models.OnchainV2GovState ||
  mongoose.model<IOnchainGovStateDoc>('OnchainV2GovState', OnchainGovStateSchema);

// ═══════════════════════════════════════════════════════════════
// 3. AUDIT LOG MODEL (Append-Only)
// ═══════════════════════════════════════════════════════════════

export interface IOnchainGovAuditDoc extends Document {
  _id: Types.ObjectId;
  id: string;
  action: OnchainGovAuditAction;
  actor: string;
  timestamp: number;
  
  policyId?: string;
  previousPolicyId?: string;
  decision?: string;
  
  details: Record<string, any>;
  notes?: string;
}

const OnchainGovAuditSchema = new Schema<IOnchainGovAuditDoc>({
  id: { type: String, required: true, unique: true, index: true },
  action: { 
    type: String, 
    required: true,
    enum: [
      'POLICY_CREATED', 'POLICY_PROPOSED', 'POLICY_ACTIVATED', 'POLICY_ARCHIVED',
      'STATE_UPDATED', 'GUARDRAILS_VIOLATION', 'DECISION_MADE', 
      'MANUAL_OVERRIDE', 'PROVIDER_RESET'
    ],
    index: true,
  },
  actor: { type: String, required: true, index: true },
  timestamp: { type: Number, required: true, index: true },
  
  policyId: { type: String },
  previousPolicyId: { type: String },
  decision: { type: String },
  
  details: { type: Schema.Types.Mixed, default: {} },
  notes: { type: String },
}, {
  collection: 'onchain_v2_gov_audit',
});

OnchainGovAuditSchema.index({ timestamp: -1 });
OnchainGovAuditSchema.index({ action: 1, timestamp: -1 });

export const OnchainGovAuditModel = mongoose.models.OnchainV2GovAudit ||
  mongoose.model<IOnchainGovAuditDoc>('OnchainV2GovAudit', OnchainGovAuditSchema, 'onchain_v2_audits');

console.log('[OnChain V2] Governance Models loaded');
