/**
 * OnChain V2 — Core Index
 * ========================
 * 
 * Exports all core module components.
 */

// Contracts
export * from './contracts.js';

// Metrics
export { OnchainMetricsEngine, metricsEngine } from './metrics/index.js';

// Snapshot
export { OnchainSnapshotService, snapshotService } from './snapshot/index.js';

// Persistence
export * from './persistence/index.js';
