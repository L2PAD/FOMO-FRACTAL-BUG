/**
 * OnChain V2 Module
 * ==================
 * 
 * ISOLATION BOUNDARY:
 * - This module is completely self-contained
 * - NO dependencies on Sentiment, Exchange, or MetaBrain
 * - Only allowed external dependency: chain_adapters (for RPC)
 * 
 * GOLDEN RULES:
 * - OnChain does NOT know about Sentiment
 * - OnChain does NOT know about Exchange Verdict  
 * - OnChain does NOT know about MetaBrain
 * - OnChain measures and stores — nothing more
 * - NO_DATA is valid, not an error
 * 
 * FEATURE FLAG:
 * - FEATURES.onchain_v2 controls activation
 * - Default: OFF (mock provider)
 * 
 * PROVIDER MODES:
 * - mock: Deterministic mock data (default)
 * - rpc: Real blockchain RPC data
 * - api: External API data (not implemented)
 */

import { FastifyInstance } from 'fastify';

// Core exports
export * from './core/index.js';

// Provider exports
export * from './providers/index.js';

// Routes
export { onchainV2Routes } from './routes/index.js';

// ═══════════════════════════════════════════════════════════════
// MODULE INITIALIZATION
// ═══════════════════════════════════════════════════════════════

export interface OnchainV2ModuleConfig {
  enabled: boolean;
  providerMode: 'mock' | 'rpc' | 'api';
}

/**
 * Initialize OnChain V2 module
 */
export async function initializeOnchainV2Module(
  fastify: FastifyInstance,
  config?: Partial<OnchainV2ModuleConfig>
): Promise<void> {
  const moduleConfig: OnchainV2ModuleConfig = {
    enabled: config?.enabled ?? false,
    providerMode: config?.providerMode ?? 'mock',
  };
  
  if (!moduleConfig.enabled) {
    console.log('[OnChain V2] Module disabled');
    return;
  }
  
  // Initialize provider
  const { initializeOnchainProvider } = await import('./providers/index.js');
  await initializeOnchainProvider();
  
  // Register routes
  const { onchainV2Routes } = await import('./routes/index.js');
  await fastify.register(onchainV2Routes, { prefix: '/onchain-v2' });
  
  console.log(`[OnChain V2] Module initialized (mode: ${moduleConfig.providerMode})`);
}

// Module metadata
export const ONCHAIN_V2_VERSION = '2.0.0';
export const ONCHAIN_V2_MODULE_NAME = 'onchain_v2';

console.log('[OnChain V2] Module loaded');
