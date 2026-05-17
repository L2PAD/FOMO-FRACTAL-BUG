/**
 * OnChain V2 — RPC Pool Service
 * ===============================
 * 
 * Multi-endpoint RPC pool with:
 * - Weighted round-robin selection
 * - Circuit breaker per endpoint
 * - Automatic failover on errors
 * - Config from MongoDB (admin-managed)
 */

import {
  RpcConfigModel,
  RpcHealthSnapshotModel,
  IRpcConfigDoc,
  RpcEndpoint,
  RpcEndpointHealth,
  RpcChainId,
} from './models.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface RpcResponse<T> {
  jsonrpc: string;
  id: number;
  result?: T;
  error?: { code: number; message: string };
}

interface EndpointState {
  endpoint: RpcEndpoint;
  health: RpcEndpointHealth;
}

// ═══════════════════════════════════════════════════════════════
// RPC POOL SERVICE
// ═══════════════════════════════════════════════════════════════

export class RpcPoolService {
  private config: IRpcConfigDoc | null = null;
  private configLoadedAt = 0;
  private endpointStates: Map<string, EndpointState> = new Map();
  private requestId = 0;
  private roundRobinIndex = 0;
  
  // Default settings (used if no config in DB)
  private readonly defaultSettings = {
    maxRetries: 3,
    retryDelayMs: 500,
    circuitBreakerThreshold: 5,
    circuitBreakerCooldownMs: 60000,
    healthCheckIntervalMs: 30000,
    configCacheTtlMs: 30000,
  };
  
  /**
   * Load config from MongoDB (cached)
   */
  async loadConfig(): Promise<IRpcConfigDoc> {
    const now = Date.now();
    const ttl = this.config?.settings?.configCacheTtlMs || this.defaultSettings.configCacheTtlMs;
    
    if (this.config && (now - this.configLoadedAt) < ttl) {
      return this.config;
    }
    
    let doc = await RpcConfigModel.findById('active').lean();
    
    if (!doc) {
      // Create default config from ENV (bootstrap)
      const newDoc = await this.createDefaultConfig();
      doc = newDoc.toObject();
    }
    
    this.config = doc as IRpcConfigDoc;
    this.configLoadedAt = now;
    
    // Initialize endpoint states
    for (const ep of doc.endpoints) {
      if (!this.endpointStates.has(ep.id)) {
        this.endpointStates.set(ep.id, {
          endpoint: ep,
          health: {
            id: ep.id,
            healthy: true,
            latencyMs: 0,
            lastSuccess: 0,
            successCount: 0,
            failureCount: 0,
          },
        });
      }
    }
    
    return doc;
  }
  
  /**
   * Create default config from environment variables
   */
  private async createDefaultConfig(): Promise<IRpcConfigDoc> {
    const endpoints: RpcEndpoint[] = [];
    
    // Bootstrap from ENV
    const envMappings: Array<{ env: string; chainId: RpcChainId; chainName: string }> = [
      { env: 'ETHEREUM_RPC_URL', chainId: 1, chainName: 'ethereum' },
      { env: 'ETH_RPC_URL', chainId: 1, chainName: 'ethereum' },
      { env: 'ARB_RPC_URL', chainId: 42161, chainName: 'arbitrum' },
      { env: 'OP_RPC_URL', chainId: 10, chainName: 'optimism' },
      { env: 'BASE_RPC_URL', chainId: 8453, chainName: 'base' },
      { env: 'POLYGON_RPC_URL', chainId: 137, chainName: 'polygon' },
    ];
    
    for (const mapping of envMappings) {
      const url = process.env[mapping.env];
      if (url) {
        const provider = this.detectProvider(url);
        endpoints.push({
          id: `${mapping.chainName}-${provider}-env`,
          url,
          provider,
          chainId: mapping.chainId,
          chainName: mapping.chainName,
          enabled: true,
          weight: 5,
        });
      }
    }
    
    const doc = new RpcConfigModel({
      _id: 'active',
      version: 1,
      updatedAt: Date.now(),
      updatedBy: 'SYSTEM_BOOTSTRAP',
      endpoints,
      settings: this.defaultSettings,
    });
    
    await doc.save();
    console.log(`[RpcPool] Created default config with ${endpoints.length} endpoints from ENV`);
    
    return doc;
  }
  
  /**
   * Detect provider from URL
   */
  private detectProvider(url: string): RpcEndpoint['provider'] {
    if (url.includes('infura.io')) return 'infura';
    if (url.includes('ankr.com')) return 'ankr';
    if (url.includes('alchemy.com')) return 'alchemy';
    if (url.includes('quiknode.pro') || url.includes('quicknode')) return 'quicknode';
    if (url.includes('llamarpc.com')) return 'llama';
    return 'custom';
  }
  
  /**
   * Get enabled endpoints for a chain
   */
  async getEndpointsForChain(chainId: number): Promise<RpcEndpoint[]> {
    const config = await this.loadConfig();
    const now = Date.now();
    const targetChainId = Number(chainId);
    
    return config.endpoints.filter(ep => {
      if (!ep.enabled) return false;
      if (Number(ep.chainId) !== targetChainId) return false;
      
      // Check circuit breaker
      const state = this.endpointStates.get(ep.id);
      if (state?.health.disabledUntil && state.health.disabledUntil > now) {
        return false;
      }
      
      return true;
    });
  }
  
  /**
   * Select next endpoint (weighted round-robin)
   */
  async selectEndpoint(chainId: RpcChainId): Promise<RpcEndpoint | null> {
    const endpoints = await this.getEndpointsForChain(chainId);
    
    if (endpoints.length === 0) return null;
    if (endpoints.length === 1) return endpoints[0];
    
    // Build weighted pool
    const pool: RpcEndpoint[] = [];
    for (const ep of endpoints) {
      for (let i = 0; i < ep.weight; i++) {
        pool.push(ep);
      }
    }
    
    // Round-robin through weighted pool
    this.roundRobinIndex = (this.roundRobinIndex + 1) % pool.length;
    return pool[this.roundRobinIndex];
  }
  
  /**
   * Make RPC call with failover
   */
  async call<T>(
    chainId: RpcChainId,
    method: string,
    params: unknown[]
  ): Promise<T> {
    const config = await this.loadConfig();
    const settings = config.settings;
    const endpoints = await this.getEndpointsForChain(chainId);
    
    if (endpoints.length === 0) {
      throw new Error(`No RPC endpoints available for chainId ${chainId}`);
    }
    
    let lastError: Error | null = null;
    const triedEndpoints = new Set<string>();
    
    for (let attempt = 0; attempt < settings.maxRetries; attempt++) {
      // Select endpoint (prefer untried ones)
      let endpoint = await this.selectEndpoint(chainId);
      
      // Try to find an untried endpoint
      for (const ep of endpoints) {
        if (!triedEndpoints.has(ep.id)) {
          endpoint = ep;
          break;
        }
      }
      
      if (!endpoint) {
        // All endpoints tried, pick any
        endpoint = endpoints[0];
      }
      
      triedEndpoints.add(endpoint.id);
      
      try {
        const result = await this.executeCall<T>(endpoint, method, params);
        this.recordSuccess(endpoint.id);
        return result;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        this.recordFailure(endpoint.id, lastError.message);
        
        // Wait before retry
        if (attempt < settings.maxRetries - 1) {
          await this.sleep(settings.retryDelayMs * (attempt + 1));
        }
      }
    }
    
    throw lastError || new Error('RPC call failed after all retries');
  }
  
  /**
   * Execute single RPC call
   */
  private async executeCall<T>(
    endpoint: RpcEndpoint,
    method: string,
    params: unknown[]
  ): Promise<T> {
    this.requestId++;
    const start = Date.now();
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    
    try {
      const response = await fetch(endpoint.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: this.requestId,
          method,
          params,
        }),
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const json = (await response.json()) as RpcResponse<T>;
      
      if (json.error) {
        throw new Error(`RPC Error: ${json.error.message} (code ${json.error.code})`);
      }
      
      // Update latency
      const state = this.endpointStates.get(endpoint.id);
      if (state) {
        state.health.latencyMs = Date.now() - start;
      }
      
      return json.result as T;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }
  
  /**
   * Record successful call
   */
  private recordSuccess(endpointId: string): void {
    const state = this.endpointStates.get(endpointId);
    if (state) {
      state.health.healthy = true;
      state.health.lastSuccess = Date.now();
      state.health.successCount++;
      state.health.failureCount = 0; // Reset consecutive failures
      state.health.disabledUntil = undefined;
    }
  }
  
  /**
   * Record failed call (with circuit breaker)
   */
  private recordFailure(endpointId: string, error: string): void {
    const state = this.endpointStates.get(endpointId);
    if (!state) return;
    
    state.health.failureCount++;
    state.health.lastError = error;
    state.health.lastErrorAt = Date.now();
    
    // Circuit breaker: disable after threshold failures
    const config = this.config;
    const threshold = config?.settings?.circuitBreakerThreshold || this.defaultSettings.circuitBreakerThreshold;
    const cooldown = config?.settings?.circuitBreakerCooldownMs || this.defaultSettings.circuitBreakerCooldownMs;
    
    if (state.health.failureCount >= threshold) {
      state.health.healthy = false;
      state.health.disabledUntil = Date.now() + cooldown;
      console.warn(`[RpcPool] Circuit breaker: disabled ${endpointId} for ${cooldown}ms`);
    }
  }
  
  /**
   * Get current health status
   */
  async getHealthStatus(): Promise<{
    configVersion: number;
    overallHealthy: boolean;
    healthyCount: number;
    totalCount: number;
    avgLatencyMs: number;
    endpoints: RpcEndpointHealth[];
  }> {
    const config = await this.loadConfig();
    const now = Date.now();
    
    const endpointHealths: RpcEndpointHealth[] = [];
    let healthyCount = 0;
    let totalLatency = 0;
    let latencyCount = 0;
    
    for (const ep of config.endpoints) {
      const state = this.endpointStates.get(ep.id);
      if (state) {
        const isDisabled = state.health.disabledUntil && state.health.disabledUntil > now;
        const health: RpcEndpointHealth = {
          ...state.health,
          healthy: ep.enabled && state.health.healthy && !isDisabled,
        };
        endpointHealths.push(health);
        
        if (health.healthy) healthyCount++;
        if (state.health.latencyMs > 0) {
          totalLatency += state.health.latencyMs;
          latencyCount++;
        }
      }
    }
    
    return {
      configVersion: config.version,
      overallHealthy: healthyCount > 0,
      healthyCount,
      totalCount: config.endpoints.filter(e => e.enabled).length,
      avgLatencyMs: latencyCount > 0 ? Math.round(totalLatency / latencyCount) : 0,
      endpoints: endpointHealths,
    };
  }
  
  /**
   * Run health check on all endpoints
   */
  async runHealthCheck(): Promise<RpcEndpointHealth[]> {
    const config = await this.loadConfig();
    const results: RpcEndpointHealth[] = [];
    
    for (const ep of config.endpoints) {
      if (!ep.enabled) continue;
      
      const start = Date.now();
      let healthy = false;
      let latencyMs = 0;
      let error: string | undefined;
      
      try {
        await this.executeCall<string>(ep, 'eth_blockNumber', []);
        healthy = true;
        latencyMs = Date.now() - start;
        this.recordSuccess(ep.id);
      } catch (e) {
        error = e instanceof Error ? e.message : String(e);
        latencyMs = Date.now() - start;
        this.recordFailure(ep.id, error);
      }
      
      const state = this.endpointStates.get(ep.id);
      if (state) {
        results.push(state.health);
      }
    }
    
    // Save snapshot
    const status = await this.getHealthStatus();
    await RpcHealthSnapshotModel.create({
      timestamp: Date.now(),
      endpoints: results,
      overallHealthy: status.overallHealthy,
      healthyCount: status.healthyCount,
      totalCount: status.totalCount,
      avgLatencyMs: status.avgLatencyMs,
    });
    
    return results;
  }
  
  /**
   * Get eth_blockNumber for chain
   */
  async getBlockNumber(chainId: RpcChainId): Promise<number> {
    const hex = await this.call<string>(chainId, 'eth_blockNumber', []);
    return parseInt(hex, 16);
  }
  
  /**
   * Get logs (for indexer)
   */
  async getLogs(
    chainId: RpcChainId,
    filter: {
      fromBlock: number | string;
      toBlock: number | string;
      address?: string | string[];
      topics?: (string | string[] | null)[];
    }
  ): Promise<Array<{
    address: string;
    topics: string[];
    data: string;
    blockNumber: string;
    transactionHash: string;
    logIndex: string;
    blockHash: string;
    transactionIndex: string;
  }>> {
    const params = [{
      fromBlock: typeof filter.fromBlock === 'number' ? '0x' + filter.fromBlock.toString(16) : filter.fromBlock,
      toBlock: typeof filter.toBlock === 'number' ? '0x' + filter.toBlock.toString(16) : filter.toBlock,
      address: filter.address,
      topics: filter.topics,
    }];
    
    return this.call(chainId, 'eth_getLogs', params);
  }
  
  /**
   * Update config (from admin)
   */
  async updateConfig(
    endpoints: RpcEndpoint[],
    updatedBy: string
  ): Promise<IRpcConfigDoc> {
    const existing = await RpcConfigModel.findById('active');
    
    const doc = existing || new RpcConfigModel({
      _id: 'active',
      settings: this.defaultSettings,
    });
    
    doc.version = (doc.version || 0) + 1;
    doc.updatedAt = Date.now();
    doc.updatedBy = updatedBy;
    doc.endpoints = endpoints;
    
    await doc.save();
    
    // Clear cache
    this.config = null;
    this.configLoadedAt = 0;
    
    console.log(`[RpcPool] Config updated to v${doc.version} by ${updatedBy}`);
    
    return doc;
  }
  
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Singleton
export const rpcPool = new RpcPoolService();

console.log('[OnChain V2] RPC Pool Service loaded');
