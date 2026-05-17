/**
 * OnChain V2 — Provider Factory
 * ==============================
 * 
 * Runtime switch for on-chain data providers.
 * Uses singleton container for provider management.
 * 
 * CONFIGURATION:
 * - ONCHAIN_PROVIDER=mock (default)
 * - ONCHAIN_PROVIDER=rpc
 */

// Re-export types
export type { IOnchainProvider, OnchainProviderConfig } from './provider.interface.js';
export { getProviderConfig } from './provider.interface.js';
export { MockProvider } from './mock.provider.js';
export { RpcProvider } from './rpc.provider.js';

// Re-export container functions (main API)
export {
  getOnchainProvider,
  resetOnchainProvider,
  initializeProvider as initializeOnchainProvider,
  isProviderInitialized,
  getActiveProviderConfig,
} from './provider.container.js';

console.log('[OnChain V2] Provider Factory loaded');
