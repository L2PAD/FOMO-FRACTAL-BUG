/**
 * OnChain V2 — Chain Registry
 * =============================
 * 
 * Single source of truth for supported chains.
 * All modules use this registry to get chain info.
 */

import { 
  SUPPORTED_CHAINS, 
  SupportedChainId,
  MULTICHAIN_ENABLED,
  getActiveChains,
  getActiveChainIds,
} from './chain.constants.js';
import type { ChainMeta } from './chain.types.js';

// ═══════════════════════════════════════════════════════════════
// CHAIN REGISTRY
// ═══════════════════════════════════════════════════════════════

export class ChainRegistry {
  private readonly map = new Map<number, ChainMeta>();

  constructor() {
    for (const chain of SUPPORTED_CHAINS) {
      this.map.set(chain.chainId, chain);
    }
  }

  /**
   * Get all supported chains
   */
  listAll(): ChainMeta[] {
    return Array.from(this.map.values());
  }

  /**
   * Get active chains (respects feature flag)
   */
  listActive(): ChainMeta[] {
    return getActiveChains();
  }

  /**
   * Get active chain IDs
   */
  getActiveIds(): SupportedChainId[] {
    return getActiveChainIds();
  }

  /**
   * Get chain by ID (throws if not supported)
   */
  get(chainId: number): ChainMeta {
    const chain = this.map.get(chainId);
    if (!chain) {
      throw new Error(`Unsupported chainId=${chainId}`);
    }
    return chain;
  }

  /**
   * Get chain by ID (returns null if not found)
   */
  tryGet(chainId: number): ChainMeta | null {
    return this.map.get(chainId) || null;
  }

  /**
   * Check if chain is supported
   */
  isSupported(chainId: number): chainId is SupportedChainId {
    return this.map.has(chainId);
  }

  /**
   * Check if chain is active (supported + feature flag)
   */
  isActive(chainId: number): boolean {
    if (!this.isSupported(chainId)) return false;
    if (!MULTICHAIN_ENABLED && chainId !== 1) return false;
    return true;
  }

  /**
   * Get short name for chain
   */
  getShort(chainId: number): string {
    const chain = this.tryGet(chainId);
    return chain?.short || `Chain#${chainId}`;
  }

  /**
   * Get explorer URL for transaction
   */
  getTxUrl(chainId: number, txHash: string): string {
    const chain = this.tryGet(chainId);
    if (!chain) return '';
    return `${chain.explorer}/tx/${txHash}`;
  }

  /**
   * Get explorer URL for address
   */
  getAddressUrl(chainId: number, address: string): string {
    const chain = this.tryGet(chainId);
    if (!chain) return '';
    return `${chain.explorer}/address/${address}`;
  }

  /**
   * Check if multi-chain is enabled
   */
  isMultiChainEnabled(): boolean {
    return MULTICHAIN_ENABLED;
  }
}

// Singleton instance
export const chainRegistry = new ChainRegistry();

console.log('[OnChain V2] Chain Registry loaded');
