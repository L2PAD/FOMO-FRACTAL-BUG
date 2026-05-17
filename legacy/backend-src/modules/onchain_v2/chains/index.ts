/**
 * OnChain V2 — Chains Module Index
 * ==================================
 * 
 * Multi-chain foundation layer.
 */

// Constants
export {
  SUPPORTED_CHAINS,
  CHAIN_IDS,
  MULTICHAIN_ENABLED,
  getActiveChains,
  getActiveChainIds,
} from './chain.constants.js';
export type { SupportedChainId } from './chain.constants.js';

// Types
export type {
  ChainMeta,
  ChainHealth,
  ChainsSummary,
  IngestionStatus,
  ChainRpcHealth,
} from './chain.types.js';

// Registry
export { ChainRegistry, chainRegistry } from './chain.registry.js';

// Health Service
export { ChainHealthService, chainHealthService } from './chain.health.service.js';

// Routes
export { chainsFastifyRoutes } from './chain.fastify.routes.js';

console.log('[OnChain V2] Chains Module loaded');
