/**
 * Engine Provider — Placeholder for future full indexer
 * =====================================================
 * 
 * ONCHAIN_MODE=production will use this provider.
 * Currently returns NO_DATA until the full indexer is built.
 */

import type {
  IOnchainProvider,
  OnchainSummary,
  OnchainFlows,
  OnchainWhales,
  OnchainActivity,
} from './provider.types.js';

export class EngineProvider implements IOnchainProvider {

  async getSummary(): Promise<OnchainSummary> {
    return {
      blockHeight: 0,
      gasPrice: 0,
      tps: 0,
      activeAddresses24h: 0,
      blockTime: 0,
      pendingTxCount: 0,
      provider: 'engine (not yet implemented)',
      updatedAt: Date.now(),
    };
  }

  async getFlows(): Promise<OnchainFlows> {
    return {
      exchangeInflow24h: 0,
      exchangeOutflow24h: 0,
      exchangeNetflow24h: 0,
      stablecoinInflow24h: 0,
      stablecoinOutflow24h: 0,
      stablecoinNetflow24h: 0,
      provider: 'engine (not yet implemented)',
      updatedAt: Date.now(),
    };
  }

  async getWhales(): Promise<OnchainWhales> {
    return {
      largeTransfers24h: 0,
      topTransfers: [],
      totalWhaleVolume24h: 0,
      provider: 'engine (not yet implemented)',
      updatedAt: Date.now(),
    };
  }

  async getActivity(): Promise<OnchainActivity> {
    return {
      dexVolume24h: 0,
      topPairs: [],
      newContracts24h: 0,
      totalValueLocked: 0,
      liquidityChange24h: 0,
      provider: 'engine (not yet implemented)',
      updatedAt: Date.now(),
    };
  }
}

console.log('[Onchain-Lite] Engine Provider placeholder loaded');
