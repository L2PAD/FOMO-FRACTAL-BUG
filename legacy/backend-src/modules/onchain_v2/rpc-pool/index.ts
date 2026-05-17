/**
 * OnChain V2 — RPC Pool Index
 * ============================
 */

export { RpcPoolService, rpcPool } from './pool.service.js';
export { rpcAdminRoutes } from './admin.routes.js';
export {
  RpcConfigModel,
  RpcHealthSnapshotModel,
} from './models.js';

export type {
  RpcEndpoint,
  RpcEndpointHealth,
  RpcChainId,
  RpcProvider,
  IRpcConfigDoc,
  IRpcHealthSnapshotDoc,
} from './models.js';

console.log('[OnChain V2] RPC Pool module loaded');
