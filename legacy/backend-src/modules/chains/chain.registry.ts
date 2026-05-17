/**
 * Chain Registry — Phase G0.1
 * ==============================
 * Runtime access to chain configs with memory cache.
 * All services/jobs import from here.
 */

import { ChainModel } from './chain.model';
import type { ChainConfig, ChainKey } from './chain.contracts';

let cache: ChainConfig[] = [];
let cacheTs = 0;
const CACHE_TTL = 30_000; // 30 sec

async function refresh(): Promise<void> {
  const docs = await ChainModel.find({}, { _id: 0 }).sort({ priority: 1 }).lean();
  cache = docs.map((d: any) => ({
    chainId: d.chainId,
    key: d.key,
    name: d.name,
    rpcUrl: d.rpcUrl || '',
    explorerUrl: d.explorerUrl || '',
    nativeSymbol: d.nativeSymbol,
    enabled: !!d.enabled,
    priority: d.priority ?? 100,
  }));
  cacheTs = Date.now();
}

async function ensureCache(): Promise<void> {
  if (Date.now() - cacheTs > CACHE_TTL || cache.length === 0) {
    await refresh();
  }
}

export const ChainRegistry = {
  /** All chains, sorted by priority */
  async getAll(): Promise<ChainConfig[]> {
    await ensureCache();
    return cache;
  },

  /** Only enabled chains */
  async getEnabled(): Promise<ChainConfig[]> {
    await ensureCache();
    return cache.filter(c => c.enabled);
  },

  /** Get by key. Throws if not found. */
  async getByKey(key: ChainKey): Promise<ChainConfig> {
    await ensureCache();
    const chain = cache.find(c => c.key === key);
    if (!chain) throw new Error(`[ChainRegistry] Chain not found: ${key}`);
    return chain;
  },

  /** Get by chainId. Throws if not found. */
  async getByChainId(chainId: number): Promise<ChainConfig> {
    await ensureCache();
    const chain = cache.find(c => c.chainId === chainId);
    if (!chain) throw new Error(`[ChainRegistry] Chain not found: chainId=${chainId}`);
    return chain;
  },

  /** Assert chain is enabled. Throws CHAIN_DISABLED if not. */
  async assertEnabled(key: ChainKey): Promise<ChainConfig> {
    const chain = await this.getByKey(key);
    if (!chain.enabled) {
      throw new Error(`CHAIN_DISABLED: ${key} (${chain.name}) is not enabled`);
    }
    return chain;
  },

  /** Force cache refresh */
  async invalidate(): Promise<void> {
    cacheTs = 0;
    await refresh();
  },
};
