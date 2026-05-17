/**
 * broker-bridge-api.ts — typed client for /api/broker/*
 *
 * Mirrors backend/services/broker_bridge.py (Sprint T10.1 — Broker Readiness
 * Bridge). NO real orders are ever placed today; this client is read-only +
 * always-refused live submit.
 */
import { api } from './api-client';

export type BrokerMode = 'off' | 'shadow' | 'live';

export interface BrokerConfig {
  liveMode: BrokerMode;
  provider: string;
  apiKeySet: boolean;
  apiSecretSet: boolean;
  riskAckSigned: boolean;
}

export interface BrokerStatus {
  ok: boolean;
  asOf: string;
  adapter: string;
  configured: boolean;
  connected: boolean;
  capability: 'unconfigured' | 'readonly_verified' | 'degraded' | 'trading_permissions_detected';
  mode: BrokerMode;
  config: BrokerConfig;
  liveSubmitEnabled: boolean;
  lastSuccessfulHeartbeat?: string | null;
  lastError?: string | null;
  version: string;
}

export interface BrokerMarket {
  symbol: string;
  pair: string;
  minNotionalUsd: number;
  minQty: number;
  tickSize: number;
  tradable: boolean;
}

export interface PreflightCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface PreflightResult {
  ok: boolean;
  symbol: string;
  action: string;
  sizeUsd: number;
  marketSupported: boolean;
  minNotionalOk: boolean;
  sizeOk: boolean;
  sideOk: boolean;
  marketInfo: Partial<BrokerMarket> | null;
  checks: PreflightCheck[];
  refusedReasons: string[];
  asOf: string;
}

export interface GateCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export type AuditFinalStatus =
  | 'refused'
  | 'refused_t10_1_safe_mode'
  | 'simulated'  // future
  | 'submitted' // future
  | 'failed'    // future
  | 'cancelled' // future
  ;

export interface AuditRow {
  auditId: string;
  attemptAt: string;
  mode: BrokerMode;
  symbol: string;
  action: string;
  requestedSizeUsd: number;
  verdictSnapshot: {
    action?: string;
    confidence?: number;
    risk?: string;
    alignmentScore?: number | null;
  };
  sizingSnapshot: {
    final?: number | null;
    lifetimeWeight?: number;
    regimeWeight?: number;
    exposureWeight?: number;
    uncertaintyPenalty?: number;
  };
  gateSnapshot: {
    permission?: 'allowed' | 'blocked';
    blockReason?: string | null;
    drawdownPct?: number;
    cooldownActive?: boolean;
  };
  preflight: PreflightResult;
  gateChecks: GateCheck[];
  refusedReasons: string[];
  finalStatus: AuditFinalStatus;
  brokerOrderId: string | null;
}

export interface LiveSubmitResponse {
  ok: false;
  finalStatus: AuditFinalStatus;
  refusedReasons: string[];
  auditId: string;
  preflight: PreflightResult;
  gateChecks: GateCheck[];
  verdictSnapshot: AuditRow['verdictSnapshot'];
  sizingSnapshot: AuditRow['sizingSnapshot'];
  gateSnapshot: AuditRow['gateSnapshot'];
  asOf: string;
}

export const brokerBridgeApi = {
  async getStatus(): Promise<BrokerStatus> {
    const r = await api.get<BrokerStatus>('/api/broker/status');
    return r.data;
  },
  async getBalances(): Promise<{
    ok: boolean;
    connected: boolean;
    balances: Array<{ asset: string; free: number; locked?: number }>;
    note?: string;
  }> {
    const r = await api.get('/api/broker/balances');
    return r.data;
  },
  async getMarkets(): Promise<{ ok: boolean; count: number; markets: BrokerMarket[] }> {
    const r = await api.get('/api/broker/markets');
    return r.data;
  },
  async preflight(payload: { symbol: string; action: string; sizeUsd: number }): Promise<PreflightResult> {
    const r = await api.post<PreflightResult>('/api/broker/preflight', payload);
    return r.data;
  },
  /**
   * T10.1 invariant: backend ALWAYS refuses. Used only to demonstrate the
   * gate flow in the operator UI, never to actually place an order.
   */
  async dryRunLiveSubmit(payload: { symbol: string; action: string; sizeUsd: number }): Promise<LiveSubmitResponse> {
    const r = await api.post<LiveSubmitResponse>('/api/broker/live/submit', payload);
    return r.data;
  },
  async getAudit(limit = 50): Promise<{ ok: boolean; count: number; audit: AuditRow[] }> {
    const r = await api.get(`/api/broker/audit?limit=${limit}`);
    return r.data;
  },
};

/**
 * Group the 11 gate checks into operational categories for the UI.
 * The grouping is UI-only; backend treats all 11 as a flat set.
 */
export const GATE_GROUPS: Record<string, string[]> = {
  CONFIG: [
    'live_mode_enabled',
    'broker_configured',
    'broker_connected',
    'exchange_capability_verified',
    'user_risk_ack_signed',
  ],
  MARKET: [
    'preflight_passed',
    'paper_scheduler_healthy',
  ],
  RISK: [
    'portfolio_gate_allowed',
    'drawdown_breaker_off',
    'calibration_sample_sufficient',
  ],
  EXECUTION: [
    'verdict_directional',
    'sizing_final_positive',
  ],
};

export const GATE_LABELS: Record<string, string> = {
  live_mode_enabled: 'live mode enabled',
  broker_configured: 'broker configured',
  broker_connected: 'broker connected',
  exchange_capability_verified: 'exchange capability verified',
  user_risk_ack_signed: 'risk acknowledgement signed',
  preflight_passed: 'preflight validation passed',
  paper_scheduler_healthy: 'paper scheduler healthy',
  portfolio_gate_allowed: 'portfolio gate allowed',
  drawdown_breaker_off: 'drawdown breaker off',
  calibration_sample_sufficient: 'calibration sample sufficient',
  verdict_directional: 'verdict is directional',
  sizing_final_positive: 'sizing final positive',
};
