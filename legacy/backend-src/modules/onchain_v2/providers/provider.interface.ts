/**
 * OnChain V2 — Provider Interface
 * ================================
 * 
 * Abstract interface for on-chain data providers.
 * 
 * IMPLEMENTATIONS:
 * - MockProvider: Deterministic mock data for development/testing
 * - RpcProvider: Real RPC data from blockchain nodes
 * 
 * RUNTIME SWITCH:
 * - ONCHAIN_PROVIDER=mock (default)
 * - ONCHAIN_PROVIDER=rpc
 */

import {
  OnchainSnapshot,
  OnchainWindow,
  OnchainChain,
  OnchainSourceType,
  OnchainProviderHealth,
} from '../core/contracts.js';

// ═══════════════════════════════════════════════════════════════
// PROVIDER INTERFACE
// ═══════════════════════════════════════════════════════════════

export interface IOnchainProvider {
  /**
   * Provider identification
   */
  readonly providerId: string;
  readonly providerName: string;
  readonly providerMode: OnchainSourceType;
  
  /**
   * Initialize the provider
   */
  initialize(): Promise<void>;
  
  /**
   * Get snapshot for a symbol at specific time
   */
  getSnapshot(
    symbol: string,
    t0: number,
    window: OnchainWindow
  ): Promise<OnchainSnapshot>;
  
  /**
   * Get latest block number (for RPC providers)
   */
  getLatestBlock(chain: OnchainChain): Promise<number>;
  
  /**
   * Get provider health status
   */
  getHealth(): Promise<OnchainProviderHealth>;
  
  /**
   * Check if provider supports a specific chain
   */
  supportsChain(chain: OnchainChain): boolean;
  
  /**
   * Get supported chains
   */
  getSupportedChains(): OnchainChain[];
}

// ═══════════════════════════════════════════════════════════════
// PROVIDER CONFIG
// ═══════════════════════════════════════════════════════════════

export interface OnchainProviderConfig {
  mode: OnchainSourceType;
  
  // RPC config (only used when mode='rpc')
  rpc?: {
    ethereum?: string;
    arbitrum?: string;
    optimism?: string;
    base?: string;
    polygon?: string;
  };
  
  // API config (only used when mode='api')
  api?: {
    endpoint?: string;
    apiKey?: string;
  };
  
  // Cache settings
  cacheTtlMs?: number;
  
  // Timeout settings
  timeoutMs?: number;
}

/**
 * Get provider config from environment
 */
export function getProviderConfig(): OnchainProviderConfig {
  const mode = (process.env.ONCHAIN_PROVIDER || 'mock') as OnchainSourceType;
  
  return {
    mode,
    rpc: {
      ethereum: process.env.ETHEREUM_RPC_URL || process.env.ETH_RPC_URL || process.env.INFURA_URL,
      arbitrum: process.env.ARB_RPC_URL,
      optimism: process.env.OP_RPC_URL,
      base: process.env.BASE_RPC_URL,
      polygon: process.env.POLYGON_RPC_URL,
    },
    api: {
      endpoint: process.env.ONCHAIN_API_ENDPOINT,
      apiKey: process.env.ONCHAIN_API_KEY,
    },
    cacheTtlMs: parseInt(process.env.ONCHAIN_CACHE_TTL_MS || '60000'),
    timeoutMs: parseInt(process.env.ONCHAIN_TIMEOUT_MS || '30000'),
  };
}

console.log('[OnChain V2] Provider Interface loaded');
