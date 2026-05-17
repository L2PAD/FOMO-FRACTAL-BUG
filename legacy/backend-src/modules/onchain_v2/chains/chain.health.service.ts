/**
 * OnChain V2 — Chain Health Service
 * ===================================
 * 
 * Monitors health of all supported chains:
 * - RPC endpoint health
 * - Block sync status
 * - Ingestion progress
 */

import { chainRegistry } from './chain.registry.js';
import { rpcPool } from '../rpc-pool/index.js';
import { SyncStateModel } from '../ingestion/erc20/models.js';
import type { 
  ChainHealth, 
  ChainsSummary, 
  IngestionStatus,
} from './chain.types.js';

// ═══════════════════════════════════════════════════════════════
// CHAIN HEALTH SERVICE
// ═══════════════════════════════════════════════════════════════

export class ChainHealthService {
  private healthCache: Map<number, ChainHealth> = new Map();
  private lastFullCheck = 0;
  private readonly cacheTtlMs = 15000; // 15 seconds

  /**
   * Get health for single chain
   */
  async getChainHealth(chainId: number): Promise<ChainHealth> {
    const chain = chainRegistry.get(chainId);
    const now = Date.now();
    
    // Check cache
    const cached = this.healthCache.get(chainId);
    if (cached && (now - cached.lastHealthCheck) < this.cacheTtlMs) {
      return cached;
    }

    let latestBlock = 0;
    let rpcHealthy = false;
    let rpcAvgLatency = 0;
    let rpcActive = 0;
    let rpcTotal = 0;
    let error: string | undefined;

    try {
      // Get RPC health
      const rpcStatus = await rpcPool.getHealthStatus();
      const chainEndpoints = rpcStatus.endpoints.filter(e => {
        // Match by endpoint ID pattern (e.g., 'ethereum-infura-env')
        return e.id.toLowerCase().includes(chain.short.toLowerCase()) ||
               e.id.includes(`-${chainId}-`);
      });
      
      rpcTotal = chainEndpoints.length;
      rpcActive = chainEndpoints.filter(e => e.healthy).length;
      rpcHealthy = rpcActive > 0;
      
      const latencies = chainEndpoints.filter(e => e.latencyMs > 0).map(e => e.latencyMs);
      rpcAvgLatency = latencies.length > 0 
        ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
        : 0;

      // Get latest block from RPC
      if (rpcHealthy) {
        const blockHex = await rpcPool.call<string>(chainId, 'eth_blockNumber', []);
        latestBlock = parseInt(blockHex, 16);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }

    // Get ingestion status
    const erc20Status = await this.getIngestionStatus(chainId, 'erc20', latestBlock);
    const dexStatus = await this.getIngestionStatus(chainId, 'dex', latestBlock);

    // Calculate total blocks behind
    const syncedBlock = Math.max(erc20Status.lastBlock, dexStatus.lastBlock);
    const blocksBehind = latestBlock > 0 ? Math.max(0, latestBlock - syncedBlock) : 0;

    const health: ChainHealth = {
      chainId,
      chain: chain.short,
      name: chain.name,
      ok: rpcHealthy && blocksBehind < 1000,
      
      latestBlock,
      syncedBlock,
      blocksBehind,
      
      rpcHealthy,
      rpcEndpointsActive: rpcActive,
      rpcEndpointsTotal: rpcTotal,
      rpcAvgLatencyMs: rpcAvgLatency,
      
      erc20Status,
      dexStatus,
      
      lastHealthCheck: now,
      error,
    };

    // Update cache
    this.healthCache.set(chainId, health);
    
    return health;
  }

  /**
   * Get health for all active chains
   */
  async getAllChainsHealth(): Promise<ChainsSummary> {
    const activeChains = chainRegistry.listActive();
    const now = Date.now();
    
    const chains: ChainHealth[] = [];
    let healthyCount = 0;
    let totalBehind = 0;
    let totalLatency = 0;
    let latencyCount = 0;

    for (const chain of activeChains) {
      try {
        const health = await this.getChainHealth(chain.chainId);
        chains.push(health);
        
        if (health.ok) healthyCount++;
        totalBehind += health.blocksBehind;
        
        if (health.rpcAvgLatencyMs > 0) {
          totalLatency += health.rpcAvgLatencyMs;
          latencyCount++;
        }
      } catch (e) {
        chains.push({
          chainId: chain.chainId,
          chain: chain.short,
          name: chain.name,
          ok: false,
          latestBlock: 0,
          syncedBlock: 0,
          blocksBehind: 0,
          rpcHealthy: false,
          rpcEndpointsActive: 0,
          rpcEndpointsTotal: 0,
          rpcAvgLatencyMs: 0,
          erc20Status: this.emptyIngestionStatus(),
          dexStatus: this.emptyIngestionStatus(),
          lastHealthCheck: now,
          error: e instanceof Error ? e.message : String(e),
        });
      }
    }

    this.lastFullCheck = now;

    return {
      ok: healthyCount === activeChains.length,
      multiChainEnabled: chainRegistry.isMultiChainEnabled(),
      activeChains: activeChains.length,
      healthyChains: healthyCount,
      totalBlocksBehind: totalBehind,
      avgRpcLatency: latencyCount > 0 ? Math.round(totalLatency / latencyCount) : 0,
      chains,
      lastUpdated: now,
    };
  }

  /**
   * Get ingestion status for a scope
   */
  private async getIngestionStatus(
    chainId: number, 
    scope: 'erc20' | 'dex',
    latestBlock: number
  ): Promise<IngestionStatus> {
    const stateKey = `${scope}_${chainId}`;
    const state = await SyncStateModel.findOne({ key: stateKey }).lean();

    if (!state) {
      return this.emptyIngestionStatus();
    }

    return {
      enabled: true,
      lastBlock: state.lastBlock,
      blocksBehind: latestBlock > 0 ? Math.max(0, latestBlock - state.lastBlock) : 0,
      status: state.status,
      lastSyncAt: state.lastSyncAt,
      totalIndexed: state.totalLogsIndexed,
      lastError: state.lastError,
    };
  }

  /**
   * Empty ingestion status
   */
  private emptyIngestionStatus(): IngestionStatus {
    return {
      enabled: false,
      lastBlock: 0,
      blocksBehind: 0,
      status: 'idle',
      lastSyncAt: 0,
      totalIndexed: 0,
    };
  }

  /**
   * Run health check on all endpoints (active)
   */
  async runHealthCheck(): Promise<void> {
    await rpcPool.runHealthCheck();
    // Refresh chain health cache
    for (const chain of chainRegistry.listActive()) {
      this.healthCache.delete(chain.chainId);
    }
  }

  /**
   * Clear cache
   */
  clearCache(): void {
    this.healthCache.clear();
    this.lastFullCheck = 0;
  }
}

// Singleton instance
export const chainHealthService = new ChainHealthService();

console.log('[OnChain V2] Chain Health Service loaded');
