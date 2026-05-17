/**
 * OnChain V2 — DEX Ingestion Module Index
 * ========================================
 */

export * from './models.js';
export * from './uniswap_v3_decoder.js';
export * from './dex_ingestion.service.js';
export * from './dex_sync.job.js';
export * from './pools.registry.js';
export * from './poolMeta.resolver.js';
export * from './dexBackfill.service.js';
export { dexRoutes } from './routes.js';

console.log('[OnChain V2] DEX Ingestion module loaded');
