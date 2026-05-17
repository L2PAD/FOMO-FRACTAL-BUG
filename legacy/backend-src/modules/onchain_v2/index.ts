/**
 * OnChain V2 — Main Index
 * ========================
 * 
 * ISOLATED MODULE - Do not import from other modules!
 */

// Module
export * from './onchain_v2.module.js';

// Re-export commonly used items
export * from './core/contracts.js';
export { getOnchainProvider, initializeOnchainProvider } from './providers/index.js';
export { snapshotService } from './core/snapshot/index.js';
export { metricsEngine } from './core/metrics/index.js';
export { onchainV2Routes } from './routes/index.js';

// Governance
export { governanceService } from './governance/index.js';
export type {
  OnchainGovPolicy,
  OnchainGovState,
  OnchainGovDecision,
} from './governance/contracts.js';
