/**
 * OnChain V2 — Bridge Aggregation Module Index
 * ==============================================
 */

// Model
export {
  BridgeAggregateModel,
} from './bridge_agg.model.js';
export type {
  BridgeAggWindow,
  BridgeMetrics,
  BridgeByBridge,
  BridgeScore,
  IBridgeAggregate,
} from './bridge_agg.model.js';

// Engine
export {
  computeBridgeScore,
} from './bridge_agg.engine.js';
export type {
  BridgeScoreInput,
  BridgeScoreOutput,
} from './bridge_agg.engine.js';

// Service
export {
  BridgeAggregationService,
  bridgeAggregationService,
} from './bridge_agg.service.js';

// Job
export {
  startBridgeAggJob,
  stopBridgeAggJob,
  bridgeAggJobStatus,
  forceBridgeAggTick,
} from './bridge_agg.job.js';

// Routes
export { bridgeAggRoutes } from './bridge_agg.routes.js';

console.log('[OnChain V2] Bridge Aggregation Module loaded');
