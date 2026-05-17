/**
 * OnChain V2 — Governance Index
 * 
 * 🔒 MODULE VERSION: v1.0.0 (frozen 2026-02-22)
 */

// Frozen Constants (v1.0.0)
export * from './governance.constants.js';

export * from './contracts.js';
export * from './models.js';
export { OnchainGovernanceService, governanceService } from './governance.service.js';
export { onchainV2GovernanceRoutes } from './governance.routes.js';

// Rolling Stats (O9.1)
export * from './rolling.model.js';
export { RollingStatsService, rollingStatsService } from './rolling.service.js';
export { rollingRoutes } from './rolling.routes.js';

// Drift / PSI (O9.2)
export * from './baseline.model.js';
export { DriftService, driftService, type DriftLevel } from './drift.service.js';
export { driftRoutes } from './drift.routes.js';

// Final Output (O9.5)
export * from './final.contracts.js';
export { FinalOutputService, finalOutputService } from './final.service.js';
export { finalRoutes } from './final.routes.js';
