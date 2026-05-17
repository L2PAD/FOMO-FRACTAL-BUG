/**
 * OnChain V2 — Price Sources Index
 * ==================================
 * 
 * STEP 1: USD Valuation Layer
 * Exports all price source implementations.
 */

export { ChainlinkSource, chainlinkSource } from './chainlink.source';
export { UniV3TwapSource, uniV3TwapSource } from './uniV3Twap.source';
export { DexVwapSource, dexVwapSource } from './dexVwap.source';

console.log('[OnChain V2] Price Sources Index loaded');
