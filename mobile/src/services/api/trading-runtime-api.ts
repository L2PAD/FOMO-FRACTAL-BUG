/**
 * trading-runtime-api.ts — typed client for /api/trading/*
 *
 * Talks to the native Trading Runtime (Sprint T1) — NOT the retired side-car.
 * See backend/services/trading_runtime.py for the contract.
 */
import { api } from './api-client';

export type TradingAction = 'WAIT' | 'LONG' | 'SHORT';
export type TradingRisk = 'LOW' | 'MED' | 'HIGH' | 'N/A';

export interface TradingVerdict {
  symbol: string;
  action: TradingAction;
  entry: number | null;
  stop: number | null;
  target: number | null;
  rr: number | null;
  risk: TradingRisk;
  sizeUsd: number | null;
  confidence: number;
  reasons: string[];
  blockedBy: string[];
  alignment: {
    ta: TradingAction;
    sentiment: TradingAction;
    fractal: TradingAction;
    longVotes: number;
    shortVotes: number;
    waitVotes: number;
    score: number;
  };
  currentPrice: number | null;
  support: number | null;
  resistance: number | null;
  moduleConfidence: {
    ta: number;
    sentiment: number;
    fractal: number;
  };
  // T4 — calibration overlay (epistemic transparency layer)
  calibration?: {
    sample: number;
    wins?: number;
    losses?: number;
    winRate: number | null;
    targetRate: number | null;
    stopRate?: number | null;
    avgPnlPct?: number | null;
    avgBarsHeld?: number | null;
    reliability: 'weak_sample' | 'emerging' | 'usable' | 'strong';
    alignmentBucket: string;
    risk?: string;
    appliedAdjustment:
      | 'observe_only' | 'warn_only'
      | 'soft_adjust' | 'soft_pass'
      | 'strong_pass' | 'strong_soft_adjust' | 'hard_gate_wait'
      | 'regime_hard_gate' | 'regime_degradation_soft_adjust'
      | 'none_wait_verdict' | 'pending';
    regimeSignal?:
      | 'no_recent_sample' | 'recent_sample_emerging'
      | 'current_regime_compatible' | 'current_regime_mixed'
      | 'current_regime_weak' | 'actively_hostile' | 'degrading';
    recent30d?: {
      sample: number;
      wins?: number;
      losses?: number;
      winRate: number | null;
      targetRate: number | null;
      reliability: string;
    };
    note?: string;
  };
  // T8 — Adaptive Capital Restraint Layer (sizing breakdown)
  sizing?: {
    baseRiskPct: number;
    baseRiskUsd: number;
    baseSize: number;
    lifetimeWeight: number;
    regimeWeight: number;
    exposureWeight: number;
    uncertaintyPenalty: number;
    final: number;
    components: {
      openCount: number;
      openCountWeight: number;
      notionalExposureUsd: number;
      notionalRatio: number;
      notionalWeight: number;
      lifetimeSample: number;
      lifetimeWinRate: number | null;
      regimeSample: number;
      regimeWinRate: number | null;
    };
    labels: {
      lifetime: string;
      regime: string;
      exposure: string;
      uncertainty: string;
    };
    explanation: string;
    forcedZeroReason:
      | 'verdict_is_wait' | 'no_structural_base_size'
      | 'book_saturated' | 'size_below_min_deployable'
      | 'portfolio_gate_blocked'
      | null;
    version: string;
  };
  // T9 — Portfolio Exposure Control + Drawdown Circuit Breaker
  portfolioGate?: {
    permission: 'allowed' | 'blocked';
    finalPermission: 'allowed' | 'blocked';
    blockReason:
      | 'max_open_positions'
      | 'max_total_notional'
      | 'max_per_symbol_exposure'
      | 'max_same_side_exposure'
      | 'max_correlated_exposure'
      | 'daily_drawdown_circuit_breaker'
      | 'loss_streak_cooldown'
      | null;
    reasons: string[];
    caps: {
      openPositions: { current: number; prospective: number; max: number; ratio: number };
      totalNotional: { currentUsd: number; prospectiveUsd: number; equityUsd: number; ratio: number; max: number };
      perSymbol: { symbol: string; currentUsd: number; prospectiveUsd: number; ratio: number; max: number };
      sameSide: { side: 'LONG' | 'SHORT' | null; currentUsd: number; prospectiveUsd: number; ratio: number; max: number };
    };
    correlation: {
      cluster: string | null;
      clusterMembers: string[];
      sameSideCountInCluster: number;
      currentClusterUsd: number;
      prospectiveClusterUsd: number;
      ratio: number;
      max: number;
    };
    drawdown: {
      realizedTodayUsd: number;
      unrealizedUsd: number;
      drawdownUsd: number;
      drawdownPct: number;
      thresholdPct: number;
      breakerActive: boolean;
      baselineUsd: number;
    };
    cooldown: {
      recentLossStreak: number;
      threshold: number;
      cooldownActive: boolean;
      cooldownUntil: string | null;
      cooldownHours: number;
    };
    thresholds: Record<string, number>;
    version: string;
  };
  actionBeforeCalibration?: TradingAction;
  actionBeforeSizing?: TradingAction;
  actionBeforePortfolioGate?: TradingAction;
  riskBeforeCalibration?: TradingRisk;
  asOf: string;
  source: string;
}

export interface PaperAccount {
  accountId: string;
  startingBalanceUsd: number;
  balanceUsd: number;
  equityUsd: number;
  realizedPnlUsd: number;
  unrealizedPnlUsd: number;
  openPositions: number;
  totalTrades: number;
  wins: number;
  losses: number;
  createdAt: string;
}

export interface PaperPosition {
  positionId: string;
  orderId: string;
  accountId: string;
  symbol: string;
  side: 'LONG' | 'SHORT';
  entryPrice: number;
  stopPrice: number;
  targetPrice: number;
  sizeUsd: number;
  status: 'OPEN' | 'CLOSED';
  openedAt: string;
  closedAt: string | null;
  closePrice: number | null;
  realizedPnlUsd: number;
  realizedPnlPct: number;
  closeReason: string | null;
  currentPrice?: number;
  unrealizedPnlUsd?: number;
  unrealizedPnlPct?: number;
}

export interface PaperEvent {
  ts: string;
  type: 'ORDER_FILLED' | 'POSITION_CLOSED';
  positionId?: string;
  orderId?: string;
  symbol: string;
  side: 'LONG' | 'SHORT';
  entry?: number;
  exit?: number;
  sizeUsd?: number;
  pnlUsd?: number;
  pnlPct?: number;
  reason?: string;
}

export interface SubmitResult {
  ok: boolean;
  error?: string;
  detail?: string;
  orderId?: string;
  positionId?: string;
  symbol?: string;
  side?: 'LONG' | 'SHORT';
  entry?: number;
  stop?: number;
  target?: number;
  sizeUsd?: number;
  verdict?: TradingVerdict;
}

export interface CloseResult {
  ok: boolean;
  error?: string;
  positionId?: string;
  closePrice?: number;
  pnlUsd?: number;
  pnlPct?: number;
  reason?: string;
}

export const tradingRuntimeApi = {
  async status() {
    const r = await api.get('/api/trading/runtime/status');
    return r.data;
  },
  async verdict(symbol: string): Promise<TradingVerdict> {
    const r = await api.get(`/api/trading/verdict/${symbol.toUpperCase()}`);
    return r.data as TradingVerdict;
  },
  async opportunities(symbols: string[] = ['BTC', 'ETH', 'SOL']) {
    const r = await api.get(`/api/trading/opportunities?symbols=${symbols.join(',')}`);
    return r.data;
  },
  async account(): Promise<PaperAccount> {
    const r = await api.get('/api/trading/paper/account');
    return r.data as PaperAccount;
  },
  async positions(status: 'OPEN' | 'CLOSED' | 'ALL' = 'OPEN'): Promise<{ ok: boolean; count: number; positions: PaperPosition[] }> {
    const r = await api.get(`/api/trading/paper/positions?status=${status}`);
    return r.data;
  },
  async events(limit = 50): Promise<{ ok: boolean; count: number; events: PaperEvent[] }> {
    const r = await api.get(`/api/trading/paper/events?limit=${limit}`);
    return r.data;
  },
  async submit(symbol: string, opts?: { action?: 'LONG' | 'SHORT'; sizeUsd?: number }): Promise<SubmitResult> {
    const body: any = { symbol };
    if (opts?.action) body.action = opts.action;
    if (opts?.sizeUsd) body.sizeUsd = opts.sizeUsd;
    const r = await api.post('/api/trading/paper/submit', body);
    return r.data as SubmitResult;
  },
  async close(positionId: string, reason = 'manual'): Promise<CloseResult> {
    const r = await api.post('/api/trading/paper/close', { positionId, reason });
    return r.data as CloseResult;
  },
  async evaluateHits(): Promise<{ ok: boolean; closed: any[]; count: number }> {
    const r = await api.post('/api/trading/paper/evaluate-hits', {});
    return r.data;
  },
};
