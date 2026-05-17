/**
 * OnChain V2 — Bridge Module Index
 * ==================================
 * 
 * Bridge Intelligence layer for L1↔L2 migration tracking.
 */

// Types
export type {
  BridgeFamily,
  BridgeDirection,
  WatchSide,
  ContractRole,
  BridgeTrackId,
  BridgeTrack,
  ResolvedContract,
  TrackHealth,
  BridgeStatus,
  BridgeHealthSummary,
  BridgeHealthResponse,
  BridgeEvent,
  BridgeNetMigration,
} from './bridge.types.js';

// Registry
export {
  BRIDGE_TRACKS,
  getBridgeTracks,
  getTracksForBridge,
  getTracksForChain,
  getSupportedBridges,
  getAllContractRoles,
  getL2ChainId,
} from './bridge.registry.js';

// Resolver
export {
  STATIC_BRIDGE_ADDRESSES,
  resolveContracts,
  resolveContract,
  getMissingRoles,
  allContractsResolved,
} from './bridge.resolver.js';
export type { BridgeResolverDeps } from './bridge.resolver.js';

// Health Service
export {
  BRIDGE_ENABLED,
  getBridgeHealth,
  bridgeHealthService,
} from './bridge.health.service.js';
export type { ChainRegistryLike, BridgeHealthDeps } from './bridge.health.service.js';

// Model
export { BridgeEventModel } from './bridge.model.js';
export type { IBridgeEvent } from './bridge.model.js';

// Decoders
export {
  decodeOpBridgeEvent,
  decodeArbBridgeEvent,
  getBridgeTopics,
  isStablecoin,
  STABLECOIN_ADDRESSES,
  OP_TOPICS,
  ARB_TOPICS,
} from './bridge.decoders.js';
export type { DecodedBridgeEvent } from './bridge.decoders.js';

// Indexer
export { bridgeIndexer, BridgeIndexer } from './bridge.indexer.js';

// Scheduler
export { bridgeScheduler } from './bridge.scheduler.js';

// Aggregation
export {
  BridgeAggregateModel,
  bridgeAggregationService,
  startBridgeAggJob,
  stopBridgeAggJob,
  bridgeAggJobStatus,
  bridgeAggRoutes,
} from './aggregation/index.js';
export type {
  BridgeAggWindow,
  BridgeMetrics,
  BridgeScore,
} from './aggregation/index.js';

// Routes
export { bridgeFastifyRoutes } from './bridge.routes.js';

console.log('[OnChain V2] Bridge Module loaded');
