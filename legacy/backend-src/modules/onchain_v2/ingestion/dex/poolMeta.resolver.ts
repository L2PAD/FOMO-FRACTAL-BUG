/**
 * OnChain V2 — Pool Meta Resolver
 * =================================
 * 
 * PHASE 3.5.5: Resolves and caches pool metadata (token0/token1)
 * from RPC when not available in database.
 */

import { DexPoolModel, type IDexPool } from './models.js';
import { rpcPool } from '../../rpc-pool/pool.service.js';
import type { RpcChainId } from '../../rpc-pool/models.js';

// ═══════════════════════════════════════════════════════════════
// WELL-KNOWN POOLS (for fast startup)
// ═══════════════════════════════════════════════════════════════

const KNOWN_POOLS: Record<string, { token0: string; token1: string; fee: number }> = {
  // Ethereum Mainnet
  '0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640': { // WETH/USDC 0.05%
    token0: '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', // USDC
    token1: '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', // WETH
    fee: 500,
  },
  '0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8': { // WETH/USDC 0.3%
    token0: '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', // USDC
    token1: '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', // WETH
    fee: 3000,
  },
  '0x11b815efb8f581194ae79006d24e0d814b7697f6': { // WETH/USDT 0.05%
    token0: '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', // WETH
    token1: '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT
    fee: 500,
  },
  '0xcbcdf9626bc03e24f779434178a73a0b4bad62ed': { // WBTC/WETH 0.3%
    token0: '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599', // WBTC
    token1: '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', // WETH
    fee: 3000,
  },
  '0x4e68ccd3e89f51c3074ca5072bbac773960dfa36': { // WETH/USDT 0.3%
    token0: '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', // WETH
    token1: '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT
    fee: 3000,
  },
  '0x7858e59e0c01ea06df3af3d20ac7b0003275d4bf': { // USDC/USDT 0.01%
    token0: '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', // USDC
    token1: '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT
    fee: 100,
  },
};

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface PoolMeta {
  token0: string;
  token1: string;
  fee?: number;
  source: 'db' | 'rpc' | 'known';
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

class PoolMetaResolverService {
  private cache = new Map<string, PoolMeta>();
  private resolving = new Map<string, Promise<PoolMeta>>();
  
  private key(chainId: number, poolAddress: string): string {
    return `${chainId}:${poolAddress.toLowerCase()}`;
  }
  
  /**
   * Get pool metadata (from cache, DB, known list, or RPC)
   */
  async get(chainId: RpcChainId, poolAddress: string): Promise<PoolMeta | null> {
    const addr = poolAddress.toLowerCase();
    const k = this.key(chainId, addr);
    
    // Check cache
    if (this.cache.has(k)) {
      return this.cache.get(k)!;
    }
    
    // Check if already resolving (debounce concurrent calls)
    if (this.resolving.has(k)) {
      return this.resolving.get(k)!;
    }
    
    // Start resolution
    const promise = this.resolve(chainId, addr);
    this.resolving.set(k, promise);
    
    try {
      const result = await promise;
      return result;
    } finally {
      this.resolving.delete(k);
    }
  }
  
  /**
   * Resolve pool metadata
   */
  private async resolve(chainId: RpcChainId, poolAddress: string): Promise<PoolMeta | null> {
    const addr = poolAddress.toLowerCase();
    const k = this.key(chainId, addr);
    
    // 1. Check well-known pools
    if (chainId === 1 && KNOWN_POOLS[addr]) {
      const known = KNOWN_POOLS[addr];
      const meta: PoolMeta = {
        token0: known.token0.toLowerCase(),
        token1: known.token1.toLowerCase(),
        fee: known.fee,
        source: 'known',
      };
      this.cache.set(k, meta);
      
      // Also save to DB
      await this.saveToDb(chainId, addr, meta);
      
      return meta;
    }
    
    // 2. Check DB
    const dbPool = await DexPoolModel.findOne({ 
      chainId, 
      address: addr 
    }).lean();
    
    if (dbPool?.token0 && dbPool?.token1) {
      const meta: PoolMeta = {
        token0: dbPool.token0.toLowerCase(),
        token1: dbPool.token1.toLowerCase(),
        fee: dbPool.fee,
        source: 'db',
      };
      this.cache.set(k, meta);
      return meta;
    }
    
    // 3. Fetch from RPC using raw calls
    try {
      // token0() selector = 0x0dfe1681
      const token0Hex = await rpcPool.call<string>(chainId, 'eth_call', [
        { to: addr, data: '0x0dfe1681' }, 'latest'
      ]);
      // token1() selector = 0xd21220a7
      const token1Hex = await rpcPool.call<string>(chainId, 'eth_call', [
        { to: addr, data: '0xd21220a7' }, 'latest'
      ]);
      // fee() selector = 0xddca3f43
      let feeHex: string | null = null;
      try {
        feeHex = await rpcPool.call<string>(chainId, 'eth_call', [
          { to: addr, data: '0xddca3f43' }, 'latest'
        ]);
      } catch {
        // fee() may not exist on some pools
      }
      
      const token0 = ('0x' + token0Hex.slice(-40)).toLowerCase();
      const token1 = ('0x' + token1Hex.slice(-40)).toLowerCase();
      const fee = feeHex ? parseInt(feeHex, 16) : undefined;
      
      const meta: PoolMeta = { token0, token1, fee, source: 'rpc' };
      this.cache.set(k, meta);
      
      // Save to DB
      await this.saveToDb(chainId, addr, meta);
      
      return meta;
    } catch (error) {
      console.error(`[PoolMetaResolver] RPC error for ${addr}:`, error);
      return null;
    }
  }
  
  /**
   * Save pool metadata to database
   */
  private async saveToDb(chainId: RpcChainId, poolAddress: string, meta: PoolMeta) {
    try {
      await DexPoolModel.updateOne(
        { chainId, address: poolAddress },
        {
          $set: {
            token0: meta.token0,
            token1: meta.token1,
            fee: meta.fee,
            updatedAt: Date.now(),
          },
          $setOnInsert: {
            chainId,
            address: poolAddress,
            protocol: 'uniswap_v3',
            enabled: true,
            priority: 0,
            totalSwapsIndexed: 0,
            addedAt: Date.now(),
          },
        },
        { upsert: true }
      );
    } catch (error) {
      console.error(`[PoolMetaResolver] DB save error:`, error);
    }
  }
  
  /**
   * Batch resolve multiple pools
   */
  async getBatch(chainId: RpcChainId, poolAddresses: string[]): Promise<Map<string, PoolMeta | null>> {
    const result = new Map<string, PoolMeta | null>();
    
    // Resolve in batches of 10 to avoid overwhelming RPC
    const batchSize = 10;
    for (let i = 0; i < poolAddresses.length; i += batchSize) {
      const batch = poolAddresses.slice(i, i + batchSize);
      const promises = batch.map(addr => this.get(chainId, addr));
      const results = await Promise.all(promises);
      
      batch.forEach((addr, idx) => {
        result.set(addr.toLowerCase(), results[idx]);
      });
    }
    
    return result;
  }
  
  /**
   * Get resolver stats
   */
  getStats() {
    return {
      cacheSize: this.cache.size,
      knownPools: Object.keys(KNOWN_POOLS).length,
      resolvingCount: this.resolving.size,
    };
  }
  
  /**
   * Clear cache
   */
  clearCache() {
    this.cache.clear();
  }
}

// Singleton
export const poolMetaResolver = new PoolMetaResolverService();

console.log('[OnChain V2] Pool Meta Resolver loaded');
