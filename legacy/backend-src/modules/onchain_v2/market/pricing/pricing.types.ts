/**
 * OnChain V2 — Pricing Types
 * ===========================
 * 
 * STEP 1: USD Valuation Layer
 * Type definitions for multi-source pricing system.
 */

export type PriceSource = 'CHAINLINK' | 'UNIV3_TWAP' | 'DEX_VWAP' | 'NONE';

export interface PriceQuote {
  chainId: number;
  token: string;
  priceUsd: number;
  confidence: number;
  source: PriceSource;
  updatedAt: number;
  priceAgeMs?: number;      // PHASE 2.3: Time since last fresh quote
  isStale?: boolean;         // PHASE 2.3: Whether price exceeds stale threshold
  meta?: Record<string, unknown>;
}

export interface PriceProvider {
  name: PriceSource;
  getUsdPrice(args: { chainId: number; token: string }): Promise<PriceQuote | null>;
}

export interface PricingServiceOptions {
  providers: PriceProvider[];
  cacheTtlMs?: number;
  hardStaleMs?: number;
}

export interface PricingHealth {
  cacheSize: number;
  totalProviders: number;
  lastRefreshAt: number | null;
  lastRefreshToken: string | null;
  settings: {
    cacheTtlMs: number;
    hardStaleMs: number;
  };
}

console.log('[OnChain V2] Pricing Types loaded');
