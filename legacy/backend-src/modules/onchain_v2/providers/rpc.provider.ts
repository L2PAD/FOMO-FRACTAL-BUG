/**
 * OnChain V2 — RPC Provider (Pool-Enabled)
 * ==========================================
 * 
 * Real blockchain RPC provider using multi-endpoint pool.
 * 
 * FEATURES:
 * - Multi-endpoint pool with failover
 * - Circuit breaker per endpoint
 * - Admin-managed config from MongoDB
 * - Weighted round-robin selection
 * 
 * ADMIN CONFIG:
 * - GET /api/v10/onchain-v2/admin/rpc → current config
 * - PUT /api/v10/onchain-v2/admin/rpc → update config
 * - POST /api/v10/onchain-v2/admin/rpc/test → health check
 */

import {
  OnchainSnapshot,
  OnchainWindow,
  OnchainChain,
  OnchainSourceType,
  OnchainProviderHealth,
  SOURCE_QUALITY,
} from '../core/contracts.js';

import { IOnchainProvider, OnchainProviderConfig, getProviderConfig } from './provider.interface.js';
import { rpcPool, RpcChainId } from '../rpc-pool/index.js';

// ═══════════════════════════════════════════════════════════════
// CHAIN MAPPING
// ═══════════════════════════════════════════════════════════════

const CHAIN_TO_ID: Record<OnchainChain, RpcChainId | null> = {
  ethereum: 1,
  arbitrum: 42161,
  optimism: 10,
  base: 8453,
  polygon: 137,
  bitcoin: null,  // No RPC for Bitcoin
  solana: null,   // Different RPC format
};

const ID_TO_CHAIN: Record<RpcChainId, OnchainChain> = {
  1: 'ethereum',
  42161: 'arbitrum',
  10: 'optimism',
  8453: 'base',
  137: 'polygon',
};

// ═══════════════════════════════════════════════════════════════
// RPC PROVIDER IMPLEMENTATION (using RPC Pool)
// ═══════════════════════════════════════════════════════════════

export class RpcProvider implements IOnchainProvider {
  readonly providerId = 'rpc_onchain_v2';
  readonly providerName = 'RPC OnChain Provider V2 (Pool)';
  readonly providerMode: OnchainSourceType = 'rpc';
  
  private config: OnchainProviderConfig;
  private initialized = false;
  private lastHealthCheck = 0;
  private healthCache: OnchainProviderHealth | null = null;
  private supportedChains: OnchainChain[] = [];
  
  constructor(config?: OnchainProviderConfig) {
    this.config = config || getProviderConfig();
  }
  
  async initialize(): Promise<void> {
    if (this.initialized) return;
    
    // Load RPC pool config (initializes from ENV if no DB config)
    const poolConfig = await rpcPool.loadConfig();
    
    // Determine supported chains from pool config
    const chainIds = new Set<RpcChainId>();
    for (const ep of poolConfig.endpoints) {
      if (ep.enabled) {
        chainIds.add(ep.chainId);
      }
    }
    
    this.supportedChains = Array.from(chainIds)
      .map(id => ID_TO_CHAIN[id])
      .filter(Boolean);
    
    this.initialized = true;
    console.log(`[RpcProvider] Pool initialized with ${poolConfig.endpoints.length} endpoints, ${this.supportedChains.length} chains`);
  }
  
  async getSnapshot(
    symbol: string,
    t0: number,
    window: OnchainWindow
  ): Promise<OnchainSnapshot> {
    // Determine chain from symbol
    const chain = this.getChainForSymbol(symbol);
    const chainId = CHAIN_TO_ID[chain];
    
    if (!chainId) {
      // Return empty snapshot if chain not supported
      return this.createEmptySnapshot(symbol, chain, t0, window);
    }
    
    try {
      // Get block number via pool (with failover)
      const blockNumber = await rpcPool.getBlockNumber(chainId);
      
      // TODO: Fetch real data from indexed logs once ERC20 indexer is running
      // For now, return basic snapshot with block number
      
      return {
        symbol,
        chain,
        t0,
        snapshotTimestamp: Date.now(),
        window,
        
        exchangeInflowUsd: 0,
        exchangeOutflowUsd: 0,
        exchangeNetUsd: 0,
        
        netInflowUsd: 0,
        netOutflowUsd: 0,
        netFlowUsd: 0,
        
        activeAddresses: 0,
        txCount: 0,
        feesUsd: 0,
        
        largeTransfersCount: 0,
        largeTransfersVolumeUsd: 0,
        
        source: 'rpc',
        sourceProvider: this.providerId,
        sourceQuality: SOURCE_QUALITY.rpc,
        missingFields: [
          'exchangeInflowUsd', 'exchangeOutflowUsd',
          'netInflowUsd', 'netOutflowUsd',
          'activeAddresses', 'txCount', 'feesUsd',
          'largeTransfersCount', 'largeTransfersVolumeUsd',
        ],
        rawDataPoints: {
          latestBlock: blockNumber,
        },
      };
    } catch (error) {
      console.error(`[RpcProvider] Error fetching snapshot for ${symbol}:`, error);
      return this.createEmptySnapshot(symbol, chain, t0, window);
    }
  }
  
  async getLatestBlock(chain: OnchainChain): Promise<number> {
    const chainId = CHAIN_TO_ID[chain];
    
    if (!chainId) {
      throw new Error(`Unsupported chain: ${chain}`);
    }
    
    return rpcPool.getBlockNumber(chainId);
  }
  
  async getHealth(): Promise<OnchainProviderHealth> {
    // Cache health check for 30 seconds
    if (this.healthCache && Date.now() - this.lastHealthCheck < 30_000) {
      return this.healthCache;
    }
    
    // Get health from pool
    const poolHealth = await rpcPool.getHealthStatus();
    
    // Map chain IDs to chain names
    const healthyChains: OnchainChain[] = [];
    for (const ep of poolHealth.endpoints) {
      if (ep.healthy) {
        const chainName = this.supportedChains.find(c => {
          const id = CHAIN_TO_ID[c];
          return id !== null;
        });
        if (chainName && !healthyChains.includes(chainName)) {
          healthyChains.push(chainName);
        }
      }
    }
    
    const status = poolHealth.overallHealthy 
      ? (poolHealth.healthyCount === poolHealth.totalCount ? 'UP' : 'DEGRADED')
      : 'DOWN';
    
    this.healthCache = {
      providerId: this.providerId,
      providerName: this.providerName,
      providerMode: 'rpc',
      status,
      chains: this.supportedChains,
      lastSuccessAt: poolHealth.overallHealthy ? Date.now() : 0,
      successRate24h: poolHealth.totalCount > 0 
        ? poolHealth.healthyCount / poolHealth.totalCount 
        : 0,
      avgLatencyMs: poolHealth.avgLatencyMs,
      checkedAt: Date.now(),
    };
    
    this.lastHealthCheck = Date.now();
    return this.healthCache;
  }
  
  supportsChain(chain: OnchainChain): boolean {
    return this.supportedChains.includes(chain);
  }
  
  getSupportedChains(): OnchainChain[] {
    return this.supportedChains;
  }
  
  // ═══════════════════════════════════════════════════════════════
  // HELPERS
  // ═══════════════════════════════════════════════════════════════
  
  private getChainForSymbol(symbol: string): OnchainChain {
    const upperSymbol = symbol.toUpperCase();
    const mapping: Record<string, OnchainChain> = {
      BTC: 'bitcoin',
      BTCUSDT: 'bitcoin',
      ETH: 'ethereum',
      ETHUSDT: 'ethereum',
      ARB: 'arbitrum',
      ARBUSDT: 'arbitrum',
      OP: 'optimism',
      OPUSDT: 'optimism',
      MATIC: 'polygon',
      MATICUSDT: 'polygon',
      POL: 'polygon',
    };
    
    return mapping[upperSymbol] || 'ethereum';
  }
  
  private createEmptySnapshot(
    symbol: string,
    chain: OnchainChain,
    t0: number,
    window: OnchainWindow
  ): OnchainSnapshot {
    return {
      symbol,
      chain,
      t0,
      snapshotTimestamp: Date.now(),
      window,
      
      exchangeInflowUsd: 0,
      exchangeOutflowUsd: 0,
      exchangeNetUsd: 0,
      
      netInflowUsd: 0,
      netOutflowUsd: 0,
      netFlowUsd: 0,
      
      activeAddresses: 0,
      txCount: 0,
      feesUsd: 0,
      
      largeTransfersCount: 0,
      largeTransfersVolumeUsd: 0,
      
      source: 'rpc',
      sourceProvider: this.providerId,
      sourceQuality: 0,  // No data = no quality
      missingFields: [
        'exchangeInflowUsd', 'exchangeOutflowUsd',
        'netInflowUsd', 'netOutflowUsd',
        'activeAddresses', 'txCount', 'feesUsd',
        'largeTransfersCount', 'largeTransfersVolumeUsd',
      ],
    };
  }
}

console.log('[OnChain V2] RPC Provider loaded');
