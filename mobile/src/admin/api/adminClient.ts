/**
 * adminClient — isolated HTTP client for /api/admin/* endpoints.
 *
 * NEVER reads from the shared session.store / auth-bridge of the
 * consumer app.  Pulls the admin secret from AdminAuthContext via a
 * subscriber function injected at provider mount time.  This keeps:
 *
 *   * admin secret out of the customer-app axios instance
 *   * customer JWT out of admin requests
 *   * the two security boundaries from cross-contaminating
 */
import axios, { AxiosInstance } from 'axios';

type GetSecret = () => string | null;
type TouchActivity = () => void;

let getSecret: GetSecret = () => null;
let touchActivity: TouchActivity = () => {};

export function bindAdminAuth(
  secretReader: GetSecret,
  activityWriter: TouchActivity,
) {
  getSecret = secretReader;
  touchActivity = activityWriter;
}

const BASE_URL = (process.env.EXPO_PUBLIC_BACKEND_URL || '').replace(/\/+$/, '');

export const adminClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 20000,
});

adminClient.interceptors.request.use((cfg) => {
  const secret = getSecret();
  if (secret) {
    cfg.headers = cfg.headers || {};
    cfg.headers.Authorization = `Bearer ${secret}`;
  }
  return cfg;
});

adminClient.interceptors.response.use(
  (res) => {
    // Successful admin request — refresh inactivity timer.
    touchActivity();
    return res;
  },
  (err) => Promise.reject(err),
);

// ── Typed API surface (read-only in 3B) ──────────────────────────────

export interface OperatorRow {
  userId: string;
  tier: 'free' | 'pro' | 'trader';
  operatorAccess: any;
  capabilities: any;
  updatedAt: string | null;
}

export interface OperatorListResponse {
  ok: boolean;
  total: number;
  n: number;
  offset: number;
  limit: number;
  rows: OperatorRow[];
}

export interface OperatorListFilters {
  tier?: 'free' | 'pro' | 'trader';
  status?: 'none' | 'invited' | 'pending_review' | 'approved' | 'revoked';
  mode?: 'none' | 'paper' | 'shadow' | 'live';
  hasOverrides?: boolean;
  q?: string;
  limit?: number;
  offset?: number;
}

export const adminApi = {
  async listOperators(filters: OperatorListFilters = {}): Promise<OperatorListResponse> {
    const params: Record<string, any> = {};
    if (filters.tier) params.tier = filters.tier;
    if (filters.status) params.status = filters.status;
    if (filters.mode) params.mode = filters.mode;
    if (typeof filters.hasOverrides === 'boolean') params.hasOverrides = filters.hasOverrides;
    if (filters.q) params.q = filters.q;
    params.limit = filters.limit ?? 50;
    params.offset = filters.offset ?? 0;
    const r = await adminClient.get('/api/admin/operator-access/list', { params });
    return r.data;
  },

  async auditTimeline(userId: string, severity?: string, limit = 100) {
    const r = await adminClient.get('/api/admin/operator-access/audit-timeline', {
      params: { userId, severity, limit },
    });
    return r.data;
  },

  // ── Governance mutations (TIER-3 Phase 3C) ────────────────────────
  // Convention: every mutation returns the authoritative resolved
  // operator record; callers MUST refetch the timeline + replace the
  // local row from the response.  NO optimistic UI updates.

  async setTier(userId: string, tier: 'free' | 'pro' | 'trader') {
    const r = await adminClient.post('/api/admin/operator-access/set-tier', { userId, tier });
    return r.data;
  },

  async setMode(userId: string, mode: 'none' | 'paper' | 'shadow' | 'live') {
    const r = await adminClient.post('/api/admin/operator-access/set-mode', { userId, mode });
    return r.data;
  },

  async setConsoleAccess(userId: string, consoleAccess: boolean) {
    const r = await adminClient.post('/api/admin/operator-access/set-console-access', {
      userId, consoleAccess,
    });
    return r.data;
  },

  async overrideCapability(
    userId: string,
    capability: 'tradingOsVisible' | 'paperTrading' | 'shadowTrading' | 'executionConsole' | 'liveTrading',
    value: 'granted' | 'revoked' | 'clear',
    reason?: string,
  ) {
    const r = await adminClient.post('/api/admin/operator-access/override-capability', {
      userId, capability, value, reason,
    });
    return r.data;
  },

  async grantLiveAuthority(
    userId: string,
    typedConfirmation: string,
    reason: string,
    expiresAt?: string | null,
  ) {
    const r = await adminClient.post('/api/admin/operator-access/grant-live-authority', {
      userId, typedConfirmation, reason, expiresAt,
    });
    return r.data;
  },

  async revokeLiveAuthority(userId: string, reason: string) {
    const r = await adminClient.post('/api/admin/operator-access/revoke-live-authority', {
      userId, reason,
    });
    return r.data;
  },

  async grant(
    userId: string,
    mode: 'paper' | 'shadow' | 'live',
    consoleAccess?: boolean,
  ) {
    const r = await adminClient.post('/api/admin/operator-access/grant', {
      userId, mode, consoleAccess,
    });
    return r.data;
  },

  async revoke(userId: string, reason?: string) {
    const r = await adminClient.post('/api/admin/operator-access/revoke', {
      userId, reason,
    });
    return r.data;
  },

  // ── Billing (TIER-4B) ────────────────────────────────────────────
  // Billing endpoints are admin-scoped and append-only.  No mutation
  // method here can ever touch liveAuthority / consoleAccess /
  // capabilityOverrides — those are governance, not finance.

  async billingProducts() {
    const r = await adminClient.get('/api/billing/products');
    return r.data;
  },

  async billingListInvoices(filters: {
    userId?: string;
    status?: 'pending' | 'paid' | 'failed' | 'refunded';
    limit?: number;
  } = {}) {
    const params: Record<string, any> = { limit: filters.limit ?? 100 };
    if (filters.userId) params.userId = filters.userId;
    if (filters.status) params.status = filters.status;
    const r = await adminClient.get('/api/billing/invoices', { params });
    return r.data;
  },

  async billingAuditTimeline(userId: string, limit = 100) {
    const r = await adminClient.get('/api/billing/audit-timeline', {
      params: { userId, limit },
    });
    return r.data;
  },

  async billingConfirmInvoice(invoiceId: string, paymentReference?: string) {
    const r = await adminClient.post('/api/billing/invoices/confirm', {
      invoiceId, paymentReference,
    });
    return r.data;
  },

  async billingFailInvoice(invoiceId: string, paymentReference?: string) {
    const r = await adminClient.post('/api/billing/invoices/fail', {
      invoiceId, paymentReference,
    });
    return r.data;
  },

  async billingRefundInvoice(invoiceId: string, reason: string) {
    const r = await adminClient.post('/api/billing/invoices/refund', {
      invoiceId, reason,
    });
    return r.data;
  },

  async billingCreateInvoice(userId: string, productCode: 'PRO' | 'TRADER') {
    const r = await adminClient.post('/api/billing/invoices', {
      userId, productCode,
    });
    return r.data;
  },

  // ── Reconciliation (TIER-4B.2) ───────────────────────────────────
  // Observability layer: detect commercial inconsistencies, surface
  // findings as IMMUTABLE records, attest via separate append-only
  // events.  NEVER auto-heals.  NEVER mutates billing/governance state.

  async reconciliationSummary() {
    const r = await adminClient.get('/api/admin/billing/reconciliation/summary');
    return r.data;
  },

  async reconciliationScan() {
    const r = await adminClient.post('/api/admin/billing/reconciliation/scan');
    return r.data;
  },

  async reconciliationListFindings(filters: {
    findingType?: string;
    severity?: 'info' | 'elevated' | 'critical';
    status?: 'open' | 'acknowledged' | 'resolved_later';
    userId?: string;
    invoiceId?: string;
    limit?: number;
  } = {}) {
    const params: Record<string, any> = { limit: filters.limit ?? 100 };
    if (filters.findingType) params.findingType = filters.findingType;
    if (filters.severity)    params.severity    = filters.severity;
    if (filters.status)      params.status      = filters.status;
    if (filters.userId)      params.userId      = filters.userId;
    if (filters.invoiceId)   params.invoiceId   = filters.invoiceId;
    const r = await adminClient.get('/api/admin/billing/reconciliation/findings', { params });
    return r.data;
  },

  async reconciliationGetFinding(findingId: string) {
    const r = await adminClient.get(`/api/admin/billing/reconciliation/findings/${encodeURIComponent(findingId)}`);
    return r.data;
  },

  async reconciliationAttest(
    findingId: string,
    action: 'acknowledge' | 'mark_resolved_later',
    reason?: string,
    note?: string,
  ) {
    const r = await adminClient.post(
      `/api/admin/billing/reconciliation/findings/${encodeURIComponent(findingId)}/attest`,
      { action, reason, note },
    );
    return r.data;
  },

  async reconciliationScans(limit = 20) {
    const r = await adminClient.get('/api/admin/billing/reconciliation/scans', {
      params: { limit },
    });
    return r.data;
  },

  // ── Analytics (TIER-4B.3) ────────────────────────────────────────
  // Derived read-only business intelligence.  Never source of truth.
  async billingAnalyticsSummary(window: '7d' | '30d' | '90d' = '30d') {
    const r = await adminClient.get('/api/admin/billing/analytics/summary', {
      params: { window },
    });
    return r.data;
  },

  // ── Attribution (T11.1 / T11.2) ──────────────────────────────────
  // Epistemic observatory.  Read-only, forward-only, immutable.
  // Counterfactual snapshots only — never on-the-fly reconstruction.
  async attributionSummary(window: '7d' | '30d' | '90d' | 'all' = '30d') {
    const r = await adminClient.get('/api/admin/attribution/summary', {
      params: { window },
    });
    return r.data;
  },

  async attributionLostOpportunity(
    window: '7d' | '30d' | '90d' | 'all' = '30d',
    limit = 50,
  ) {
    const r = await adminClient.get('/api/admin/attribution/lost-opportunity', {
      params: { window, limit },
    });
    return r.data;
  },

  async attributionPipelineVersion() {
    const r = await adminClient.get('/api/admin/attribution/pipeline-version');
    return r.data;
  },

  async attributionPerAsset(
    symbol: string,
    window: '7d' | '30d' | '90d' | 'all' = '30d',
  ) {
    const r = await adminClient.get('/api/admin/attribution/per-asset', {
      params: { symbol, window },
    });
    return r.data;
  },

  // ── T11.2B drilldowns (investigative, collapsible by default) ────
  async attributionAssets(window: '7d' | '30d' | '90d' | 'all' = '30d') {
    const r = await adminClient.get('/api/admin/attribution/assets', { params: { window } });
    return r.data;
  },

  async attributionGateRuleBreakdown(window: '7d' | '30d' | '90d' | 'all' = '30d') {
    const r = await adminClient.get('/api/admin/attribution/gate-rule-breakdown', { params: { window } });
    return r.data;
  },

  async attributionConfidenceDistribution(window: '7d' | '30d' | '90d' | 'all' = '30d') {
    const r = await adminClient.get('/api/admin/attribution/confidence-distribution', { params: { window } });
    return r.data;
  },

  async attributionExposureHistograms(window: '7d' | '30d' | '90d' | 'all' = '30d') {
    const r = await adminClient.get('/api/admin/attribution/exposure-histograms', { params: { window } });
    return r.data;
  },
};
