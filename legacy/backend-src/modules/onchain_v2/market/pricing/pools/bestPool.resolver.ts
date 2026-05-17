/**
 * OnChain V2 — Best Pool Resolver
 * =================================
 * 
 * STEP 2.2: Resolves the best stable pool for a token
 * Uses DB-based deterministic selection:
 * - status = ACTIVE
 * - isStablePair = true
 * - sorted by score DESC, confidence DESC
 */

import { DexPoolModel } from '../../../ingestion/dex/models';
import type { PoolStatus } from './poolScoring.service';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface BestPoolResult {
  pool: string;
  token0: string;
  token1: string;
  fee: number;
  stableToken: string;
  score: number;
  confidence: number;
  status: PoolStatus;
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

class BestPoolResolverService {
  private cache = new Map<string, { result: BestPoolResult | null; cachedAt: number }>();
  private cacheTtlMs = 5 * 60 * 1000; // 5 minutes
  
  private key(chainId: number, token: string): string {
    return `${chainId}:${token.toLowerCase()}`;
  }
  
  /**
   * Find the best stable pool for a token
   * Priority: ACTIVE > DEGRADED > DISABLED (any stable pair)
   */
  async resolve(chainId: number, token: string): Promise<BestPoolResult | null> {
    const tokenLower = token.toLowerCase();
    const k = this.key(chainId, tokenLower);
    const now = Date.now();
    
    // Check cache
    const cached = this.cache.get(k);
    if (cached && (now - cached.cachedAt) < this.cacheTtlMs) {
      return cached.result;
    }
    
    // Query DB: find best pool where token is one side and other is stable
    // Try status in priority order: ACTIVE > DEGRADED > any
    for (const statusFilter of [
      { status: 'ACTIVE' },
      { status: 'DEGRADED' },
      { status: { $in: ['DISABLED', 'CANDIDATE'] } },
    ]) {
      const pool = await DexPoolModel.findOne({
        chainId,
        ...statusFilter,
        isStablePair: true,
        $or: [
          { token0: tokenLower },
          { token1: tokenLower },
        ],
      })
        .sort({ score: -1, confidence: -1, volume24hUsd: -1 })
        .lean();
      
      if (pool) {
        const result = this.mapToResult(pool, tokenLower);
        this.cache.set(k, { result, cachedAt: now });
        return result;
      }
    }
    
    this.cache.set(k, { result: null, cachedAt: now });
    return null;
  }
  
  /**
   * Find best base pool (WETH/WBTC) for a token
   */
  async resolveBasePool(chainId: number, token: string): Promise<BestPoolResult | null> {
    const tokenLower = token.toLowerCase();
    
    const pool = await DexPoolModel.findOne({
      chainId,
      status: { $in: ['ACTIVE', 'DEGRADED'] },
      isStablePair: false,
      $or: [
        { token0: tokenLower },
        { token1: tokenLower },
      ],
    })
      .sort({ score: -1, confidence: -1 })
      .lean();
    
    if (!pool) return null;
    return this.mapToResult(pool, tokenLower);
  }
  
  /**
   * Map pool document to result
   */
  private mapToResult(pool: any, targetToken: string): BestPoolResult {
    const isToken0 = pool.token0 === targetToken;
    const stableToken = isToken0 ? pool.token1 : pool.token0;
    
    return {
      pool: pool.address,
      token0: pool.token0,
      token1: pool.token1,
      fee: pool.fee || 3000,
      stableToken,
      score: pool.score || 0,
      confidence: pool.confidence || 0,
      status: pool.status || 'CANDIDATE',
    };
  }
  
  /**
   * Clear cache (for testing)
   */
  clearCache(): void {
    this.cache.clear();
  }
  
  /**
   * Get cache stats
   */
  getStats(): { cacheSize: number; ttlMs: number } {
    return {
      cacheSize: this.cache.size,
      ttlMs: this.cacheTtlMs,
    };
  }
}

export const bestPoolResolver = new BestPoolResolverService();

console.log('[OnChain V2] Best Pool Resolver loaded');
