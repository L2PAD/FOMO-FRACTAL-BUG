/**
 * OnChain V2 — Pricing Module Index
 * ===================================
 * 
 * STEP 1: USD Valuation Layer
 * 
 * Main entry point for pricing module.
 * Initializes PricingService with all providers.
 */

import { PricingService } from './price.service';
import { chainlinkSource } from './sources/chainlink.source';
import { uniV3TwapSource } from './sources/uniV3Twap.source';
import { dexVwapSource } from './sources/dexVwap.source';
import { pricingRoutes } from './price.routes';

// Export types
export * from './pricing.types';
export { TokenUsdPriceModel } from './price.model';
export { PricingService } from './price.service';
export { pricingRoutes } from './price.routes';

// Export sources
export { chainlinkSource, uniV3TwapSource, dexVwapSource } from './sources';

// ═══════════════════════════════════════════════════════════════
// SINGLETON INSTANCE
// ═══════════════════════════════════════════════════════════════

/**
 * Pricing service instance with all providers
 * Priority order: Chainlink > TWAP > VWAP
 */
export const pricingService = new PricingService({
  providers: [
    chainlinkSource,   // Highest confidence (0.95)
    uniV3TwapSource,   // Medium confidence (0.75)
    dexVwapSource,     // Fallback (0.35)
  ],
  cacheTtlMs: 10 * 60_000,    // 10 minutes
  hardStaleMs: 60 * 60_000,   // 1 hour
});

console.log('[OnChain V2] Pricing Module initialized');
