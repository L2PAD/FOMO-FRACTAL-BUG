/**
 * LiquidityScore Module Index
 * ============================
 * 
 * 🔒 FROZEN v1.0.0 — 2026-02-23
 * 
 * LARE (Liquidity & Alt Rotation Engine)
 * Alt-first Liquidity & Regime Classification
 */

// Version Constants (FROZEN)
export {
  LARE_VERSION,
  LARE_FROZEN,
  LARE_FROZEN_DATE,
} from './contracts';

// Contracts & Types (FROZEN)
export {
  LiquidityRegime,
  FlagSeverity,
  GuardrailAction,
  FLAG_CODES,
  LIQUIDITY_THRESHOLDS,
} from './contracts';

export type {
  LiquidityFlag,
  LiquidityInputs,
  LiquidityGovernance,
  LiquidityLatest,
  LiquiditySeriesPoint,
  LiquiditySeries,
  LiquidityFeatures,
  LiquidityEngineResult,
  MarketSeriesInput,
} from './contracts';

// Model
export { LiquiditySeriesModel, bucket10m } from './liquidity.model';
export type { ILiquiditySeries } from './liquidity.model';

// Engine
export { computeLiquidityScore } from './liquidity.engine';
export type { 
  MarketSeriesHistory, 
  MarketSeriesLatest,
  FlowDataInput,
  FlowHistories,
} from './liquidity.engine';

// Flow Service (Phase 2.2)
export { 
  getDexFlow, 
  getExchangeFlow, 
  getFlowAggregation,
  getFlowHistories,
} from './flow.service';
export type { 
  DexFlowData, 
  ExchangeFlowData, 
  FlowAggregation,
} from './flow.service';

// Governance
export { applyGovernance } from './liquidity.governance';
export type { GovernanceInput, GovernanceResult } from './liquidity.governance';

// Service
export {
  getLatestLiquidity,
  getLiquiditySeries,
  getLiquidityHealth,
  tickLiquidity,
} from './liquidity.service';

// Job
export {
  startLiquidityJob,
  stopLiquidityJob,
  forceRunLiquidityJob,
  getLiquidityJobStatus,
} from './liquidity.job';

// Routes
export { liquidityRoutes } from './liquidity.routes';

console.log('[Liquidity] Module index loaded');
