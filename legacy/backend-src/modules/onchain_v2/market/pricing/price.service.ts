/**
 * OnChain V2 — Pricing Service
 * ==============================
 * 
 * STEP 1: USD Valuation Layer
 * 
 * Main orchestrator for multi-source USD pricing.
 * Priority: Chainlink > UniV3 TWAP > DEX VWAP
 * 
 * Features:
 * - Memory + DB cache for performance
 * - Failover between price sources
 * - Stale data handling with degraded confidence
 */

import { TokenUsdPriceModel, ITokenUsdPrice } from './price.model';
import type { PriceQuote, PriceProvider, PricingServiceOptions, PricingHealth, PriceSource } from './pricing.types';

const now = () => Date.now();

export class PricingService {
  private providers: PriceProvider[];
  private memCache = new Map<string, PriceQuote>();
  private cacheTtlMs: number;
  private hardStaleMs: number;
  private lastRefreshAt: number | null = null;
  private lastRefreshToken: string | null = null;
  
  constructor(opts: PricingServiceOptions) {
    this.providers = opts.providers;
    this.cacheTtlMs = opts.cacheTtlMs ?? 10 * 60_000; // 10 minutes
    this.hardStaleMs = opts.hardStaleMs ?? 60 * 60_000; // 1 hour
  }
  
  private key(chainId: number, token: string): string {
    return `${chainId}:${token.toLowerCase()}`;
  }
  
  /**
   * Get USD price for a token
   * Uses cache -> DB -> providers hierarchy
   */
  async getUsdPrice(args: {
    chainId: number;
    token: string;
    allowStale?: boolean;
  }): Promise<PriceQuote | null> {
    const { chainId, token, allowStale = true } = args;
    const k = this.key(chainId, token);
    const tokenLower = token.toLowerCase();
    
    // 1) Check memory cache
    const mem = this.memCache.get(k);
    if (mem && (now() - mem.updatedAt) <= this.cacheTtlMs) {
      return this.enrichQuote(mem);
    }
    
    // 2) Check MongoDB
    try {
      const db = await TokenUsdPriceModel.findOne({
        chainId,
        token: tokenLower,
      }).lean() as ITokenUsdPrice | null;
      
      if (db) {
        const quote: PriceQuote = {
          chainId,
          token: db.token,
          priceUsd: db.priceUsd,
          confidence: db.confidence,
          source: db.source as PriceSource,
          updatedAt: db.updatedAt,
          meta: db.meta,
        };
        
        // If fresh enough, return from DB
        if ((now() - quote.updatedAt) <= this.cacheTtlMs) {
          this.memCache.set(k, quote);
          return this.enrichQuote(quote);
        }
        
        // If allowStale and not hard-stale, return degraded
        if (allowStale && (now() - quote.updatedAt) <= this.hardStaleMs) {
          this.memCache.set(k, quote);
          return quote;
        }
      }
    } catch (e) {
      console.error('[PricingService] DB lookup error:', e);
    }
    
    // 3) Fetch from providers
    const fresh = await this.fetchFromProviders({ chainId, token: tokenLower });
    
    if (!fresh) {
      // If we had DB data and it's not hard-stale, return degraded
      const mem2 = this.memCache.get(k);
      if (mem2 && allowStale && (now() - mem2.updatedAt) <= this.hardStaleMs) {
        const degraded: PriceQuote = {
          ...mem2,
          confidence: Math.min(mem2.confidence, 0.35),
          meta: { ...(mem2.meta ?? {}), degraded: true, reason: 'PRICE_REFRESH_FAILED' },
        };
        return degraded;
      }
      return null;
    }
    
    // 4) Persist to DB
    try {
      await TokenUsdPriceModel.updateOne(
        { chainId, token: tokenLower },
        { $set: { ...fresh, token: tokenLower } },
        { upsert: true }
      );
    } catch (e) {
      console.error('[PricingService] DB persist error:', e);
    }
    
    // 5) Update memory cache
    this.memCache.set(k, fresh);
    this.lastRefreshAt = now();
    this.lastRefreshToken = tokenLower;
    
    return this.enrichQuote(fresh);
  }
  
  /**
   * PHASE 2.3: Enrich quote with priceAgeMs and stale detection
   */
  private enrichQuote(quote: PriceQuote): PriceQuote {
    const ageMs = now() - quote.updatedAt;
    return {
      ...quote,
      priceAgeMs: ageMs,
      isStale: ageMs > this.cacheTtlMs,
    };
  }
  
  /**
   * Try each provider in order until one succeeds
   */
  private async fetchFromProviders(args: {
    chainId: number;
    token: string;
  }): Promise<PriceQuote | null> {
    for (const provider of this.providers) {
      try {
        const quote = await provider.getUsdPrice(args);
        if (!quote) continue;
        if (!Number.isFinite(quote.priceUsd) || quote.priceUsd <= 0) continue;
        
        // Normalize confidence
        if (!Number.isFinite(quote.confidence) || quote.confidence < 0) quote.confidence = 0;
        if (quote.confidence > 1) quote.confidence = 1;
        
        return {
          ...quote,
          token: args.token.toLowerCase(),
          updatedAt: quote.updatedAt ?? now(),
        };
      } catch (e) {
        console.warn(`[PricingService] Provider ${provider.name} failed:`, e);
        // Continue to next provider
      }
    }
    return null;
  }
  
  /**
   * Get multiple prices at once
   */
  async getBatchPrices(args: {
    chainId: number;
    tokens: string[];
    allowStale?: boolean;
  }): Promise<Map<string, PriceQuote | null>> {
    const results = new Map<string, PriceQuote | null>();
    
    for (const token of args.tokens) {
      const price = await this.getUsdPrice({
        chainId: args.chainId,
        token,
        allowStale: args.allowStale,
      });
      results.set(token.toLowerCase(), price);
    }
    
    return results;
  }
  
  /**
   * Force refresh price (bypass cache)
   */
  async refreshPrice(args: { chainId: number; token: string }): Promise<PriceQuote | null> {
    const k = this.key(args.chainId, args.token);
    this.memCache.delete(k);
    
    return this.getUsdPrice({ ...args, allowStale: false });
  }
  
  /**
   * Get service health status
   */
  getHealth(): PricingHealth {
    return {
      cacheSize: this.memCache.size,
      totalProviders: this.providers.length,
      lastRefreshAt: this.lastRefreshAt,
      lastRefreshToken: this.lastRefreshToken,
      settings: {
        cacheTtlMs: this.cacheTtlMs,
        hardStaleMs: this.hardStaleMs,
      },
    };
  }
  
  /**
   * Clear memory cache
   */
  clearCache(): void {
    this.memCache.clear();
    console.log('[PricingService] Cache cleared');
  }
  
  /**
   * Get cached price (no fetch)
   */
  getCachedPrice(chainId: number, token: string): PriceQuote | null {
    return this.memCache.get(this.key(chainId, token)) || null;
  }
}

console.log('[OnChain V2] Pricing Service loaded');
