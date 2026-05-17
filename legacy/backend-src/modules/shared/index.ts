/**
 * Shared Module Index
 * ====================
 * 
 * Common services for both Sentiment and Exchange modules:
 * - Evidence Store (F2)
 * - Module Manifest (F1)
 * - Feature Flag Lock (F6)
 * - Calibration Guard (F4)
 * - Simulation Run Registry (F5)
 */

export * from './evidence-writer.service.js';
export * from './module-manifest.service.js';
export * from './feature-flag-lock.model.js';
export * from './feature-flag-lock.service.js';
export * from './calibration.model.js';
export * from './calibration-guard.service.js';
export * from './simulation-run.model.js';
export * from './simulation-run-registry.service.js';
export { default as sharedAdminRoutes } from './shared-admin.routes.js';

console.log('[Shared] Module loaded (F1-F6)');
