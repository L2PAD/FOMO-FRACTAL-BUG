/**
 * OnChain V2 — Liquidity Module Index
 * =====================================
 * 
 * STEP 4.1: TVL/Liquidity Scoring Integration
 */

// Types
export * from './liquidity.types';

// Providers
export { uniswapSubgraphProvider } from './uniswapSubgraph.provider';
export { defiLlamaProvider } from './defillama.provider';

// Service
export { poolLiquidityService, PoolLiquidityService } from './poolLiquidity.service';

// Job
export {
  startPoolLiquidityJob,
  stopPoolLiquidityJob,
  forceRunPoolLiquidityJob,
  getPoolLiquidityJobStatus,
} from './poolLiquidity.job';

// Routes
export { liquidityRoutes } from './liquidity.routes';

console.log('[OnChain V2] Liquidity Module loaded');
