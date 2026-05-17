/**
 * OnChain V2 — Assets Module Index
 * ==================================
 * 
 * PHASE 4: Assets Tab
 */

// Services
export { assetsProfileService } from './assets.profile.service';
export { assetsListService } from './assets.list.service';
export { computeLiquidityRiskScore, type LiquidityRiskInput, type LiquidityRiskOutput } from './liquidityRisk.service';

// Routes
export { assetsRoutes } from './assets.routes';

console.log('[OnChain V2] Assets Module loaded');
