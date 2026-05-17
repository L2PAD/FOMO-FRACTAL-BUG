/**
 * OnChain V2 — Stablecoin Module Index
 * =====================================
 * 
 * BLOCK 5: Stablecoin Mint/Burn Watcher
 * 
 * Tracks stablecoin supply expansion/contraction as a macro signal.
 * Covers USDT, USDC, DAI across ETH, ARB, OP, BASE.
 */

// Registry
export { 
  STABLECOIN_REGISTRY,
  STABLE_MINTBURN_ENABLED,
  getStablecoinsForChain,
  getStablecoinByAddress,
  isStablecoin,
  getStablecoinChainIds,
  type StablecoinConfig,
} from './stable_registry.js';

// Models
export { 
  StableMintBurnModel,
  type IStableMintBurn,
  type StableToken,
  type MintBurnDirection,
} from './stable_mintburn.model.js';

export {
  StableAggregateModel,
  type IStableAggregate,
  type StableAggWindow,
  type StableMetrics,
  type StableScore,
} from './stable_aggregate.model.js';

// Decoder
export {
  decodeMintBurn,
  normalizeAmount,
  isTransferLog,
  TRANSFER_TOPIC,
  type DecodedMintBurn,
} from './stable_decoder.js';

// Indexer
export { 
  StableMintBurnIndexer,
  stableMintBurnIndexer,
} from './stable_indexer.js';

// Aggregation Service
export { 
  StableAggregationService,
  stableAggregationService,
} from './stable_aggregation.service.js';

// Routes
export { stableRoutes } from './stable.routes.js';

// Jobs
export { 
  startStableJobs, 
  stopStableJobs,
  isStableJobsRunning,
} from './stable.jobs.js';

console.log('[OnChain V2] Stablecoin module index loaded');
