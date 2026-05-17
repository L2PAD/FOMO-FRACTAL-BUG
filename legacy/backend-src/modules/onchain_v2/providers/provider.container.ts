/**
 * OnChain V2 — Provider Container (Singleton)
 * ============================================
 * 
 * Single point of access for OnChain provider.
 * Ensures provider is created once and reused.
 * 
 * USAGE:
 * - getOnchainProvider() - get singleton instance
 * - resetOnchainProvider() - reset for testing/admin refresh
 */

import type { IOnchainProvider, OnchainProviderConfig } from './provider.interface.js';
import { getProviderConfig } from './provider.interface.js';
import { MockProvider } from './mock.provider.js';
import { RpcProvider } from './rpc.provider.js';

// Singleton instance
let providerInstance: IOnchainProvider | null = null;
let providerConfig: OnchainProviderConfig | null = null;

/**
 * Create provider based on config (internal)
 */
function createProvider(config: OnchainProviderConfig): IOnchainProvider {
  switch (config.mode) {
    case 'rpc':
      console.log('[OnChain V2] Container: Creating RPC Provider');
      return new RpcProvider(config);
      
    case 'api':
      console.log('[OnChain V2] Container: API Provider not implemented, using Mock');
      return new MockProvider();
      
    case 'mock':
    default:
      console.log('[OnChain V2] Container: Creating Mock Provider');
      return new MockProvider();
  }
}

/**
 * Get singleton provider instance
 * Creates provider on first call, returns cached instance after
 */
export function getOnchainProvider(): IOnchainProvider {
  if (!providerInstance) {
    providerConfig = getProviderConfig();
    providerInstance = createProvider(providerConfig);
    console.log(`[OnChain V2] Container: Provider initialized (mode=${providerConfig.mode})`);
  }
  return providerInstance;
}

/**
 * Get current provider config (without creating provider)
 */
export function getActiveProviderConfig(): OnchainProviderConfig {
  if (!providerConfig) {
    providerConfig = getProviderConfig();
  }
  return providerConfig;
}

/**
 * Reset provider instance
 * Used for testing or admin-triggered refresh
 */
export function resetOnchainProvider(): void {
  if (providerInstance) {
    console.log('[OnChain V2] Container: Provider reset');
  }
  providerInstance = null;
  providerConfig = null;
}

/**
 * Initialize provider (call at startup)
 */
export async function initializeProvider(): Promise<IOnchainProvider> {
  const provider = getOnchainProvider();
  await provider.initialize();
  return provider;
}

/**
 * Check if provider is initialized
 */
export function isProviderInitialized(): boolean {
  return providerInstance !== null;
}

console.log('[OnChain V2] Provider Container loaded');
