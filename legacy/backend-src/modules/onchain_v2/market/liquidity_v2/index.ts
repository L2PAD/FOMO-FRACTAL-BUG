/**
 * OnChain V2 — LiquidityScore v2 Module Index
 * =============================================
 * 
 * BLOCK 7: LiquidityScore v2 (LARE v2)
 * 
 * Composite scoring from:
 * - Market liquidity indicators
 * - DEX/CEX flow imbalance
 * - L1↔L2 bridge migration
 * - Stablecoin supply expansion/contraction
 */

// Contracts (frozen)
export {
  LARE_V2_VERSION,
  LARE_V2_WEIGHTS,
  LARE_V2_REGIMES,
  LARE_V2_RISK_CAP,
  LARE_V2_CONFIDENCE,
  type LareV2Regime,
  type LareV2Window,
} from './liquidity_v2.contracts.js';

// Engine
export {
  buildLareV2,
  type LareV2Gate,
  type LareV2Output,
} from './liquidity_v2.engine.js';

// Model
export {
  LareV2Model,
  type ILareV2,
} from './liquidity_v2.model.js';

// Service
export {
  LiquidityV2Service,
  type LiquidityV2Deps,
} from './liquidity_v2.service.js';

// Job
export {
  startLiquidityV2Job,
  getLiquidityV2JobStatus,
} from './liquidity_v2.job.js';

// Routes
export {
  buildLiquidityV2Routes,
} from './liquidity_v2.routes.js';

console.log('[OnChain V2] LiquidityScore v2 module index loaded');
