/**
 * OnChain Governance API Client
 */

const API_URL = process.env.REACT_APP_BACKEND_URL || "";

export interface OnchainGovWeights {
  exchangePressureWeight: number;
  flowScoreWeight: number;
  whaleActivityWeight: number;
  networkHeatWeight: number;
  velocityWeight: number;
  distributionSkewWeight: number;
}

export interface OnchainGovThresholds {
  minUsableConfidence: number;
  strongInflow: number;
  moderateInflow: number;
  strongOutflow: number;
  moderateOutflow: number;
  neutralZone: number;
}

export interface OnchainGovGuardrails {
  providerHealthyRequired: boolean;
  minSamples30d: number;
  driftMaxPsi: number;
  crisisBlock: boolean;
  maxLatencyMs: number;
  requireManualApproval: boolean;
}

export interface OnchainGovPolicy {
  id: string;
  version: string;
  name: string;
  description: string;
  weights: OnchainGovWeights;
  thresholds: OnchainGovThresholds;
  guardrails: OnchainGovGuardrails;
  status: 'DRAFT' | 'PROPOSED' | 'ACTIVE' | 'ARCHIVED';
  createdAt: number;
  createdBy: string;
  activatedAt?: number;
  activatedBy?: string;
}

export interface OnchainGovState {
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

export interface GuardrailsEvaluation {
  providerHealthy: boolean;
  sampleCount30d: number;
  driftPsi30d: number;
  crisisFlag: boolean;
  allPassed: boolean;
  reasons?: string[];
}

export interface OnchainGovStateResponse {
  ok: boolean;
  state: OnchainGovState;
  activePolicy: {
    id: string;
    version: string;
    name: string;
    status: string;
  } | null;
  guardrails: GuardrailsEvaluation;
  timestamp: number;
}

export interface OnchainRuntimeResponse {
  enabled: boolean;
  provider: 'mock' | 'rpc' | 'api';
  rpcConfigured: boolean;
  rpcHealthy: boolean;
  latestBlock: number | null;
  providerInitialized: boolean;
  now: number;
  notes: string[];
}

export interface OnchainAuditEntry {
  id: string;
  action: string;
  actor: string;
  timestamp: number;
  policyId?: string;
  previousPolicyId?: string;
  decision?: string;
  details: Record<string, any>;
  notes?: string;
}

export interface DryRunResult {
  ok: boolean;
  policy: OnchainGovPolicy;
  guardrailsEvaluation: GuardrailsEvaluation;
  computedDeltas: {
    weightsDelta: Partial<OnchainGovWeights>;
    thresholdsDelta: Partial<OnchainGovThresholds>;
    guardrailsDelta: Partial<OnchainGovGuardrails>;
  };
  warnings: string[];
  wouldAllow: boolean;
  simulatedAt: number;
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 300)}`);
  }
  return res.json();
}

export async function getRuntime(): Promise<OnchainRuntimeResponse> {
  return fetchJSON(`${API_URL}/api/v10/onchain-v2/runtime`);
}

export async function getGovState(): Promise<OnchainGovStateResponse> {
  return fetchJSON(`${API_URL}/api/v10/onchain-v2/admin/governance/state`);
}

export async function getActivePolicy(): Promise<{ ok: boolean; policy: OnchainGovPolicy }> {
  return fetchJSON(`${API_URL}/api/v10/onchain-v2/admin/governance/policy/active`);
}

export async function dryRun(draft: {
  weights: OnchainGovWeights;
  thresholds: OnchainGovThresholds;
  guardrails: OnchainGovGuardrails;
}): Promise<{ ok: boolean; result: DryRunResult }> {
  return fetchJSON(`${API_URL}/api/v10/onchain-v2/admin/governance/policy/dry-run`, {
    method: "POST",
    body: JSON.stringify(draft),
  });
}

export async function proposePolicy(draft: {
  name: string;
  description?: string;
  version: string;
  weights: OnchainGovWeights;
  thresholds: OnchainGovThresholds;
  guardrails: OnchainGovGuardrails;
}): Promise<{ ok: boolean; policy: OnchainGovPolicy; message: string }> {
  return fetchJSON(`${API_URL}/api/v10/onchain-v2/admin/governance/policy/propose`, {
    method: "POST",
    body: JSON.stringify(draft),
  });
}

export async function applyPolicy(policyId: string): Promise<{ ok: boolean; state: OnchainGovState; message: string }> {
  return fetchJSON(`${API_URL}/api/v10/onchain-v2/admin/governance/policy/apply`, {
    method: "POST",
    body: JSON.stringify({ policyId }),
  });
}

export async function getAuditLog(limit = 50): Promise<{ ok: boolean; entries: OnchainAuditEntry[]; count: number }> {
  return fetchJSON(`${API_URL}/api/v10/onchain-v2/admin/governance/audit?limit=${limit}`);
}
