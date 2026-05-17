/**
 * OnChain V2 — Pool Liquidity Types
 * ===================================
 * 
 * STEP 4.1: TVL/Liquidity Scoring Integration
 * Types for liquidity data providers.
 */

// ═══════════════════════════════════════════════════════════════
// INPUT/OUTPUT TYPES
// ═══════════════════════════════════════════════════════════════

export interface PoolLiquidityInput {
  chainId: number;
  poolAddress: string;
}

export type TvlSource = 'UNISWAP_SUBGRAPH' | 'DEFILLAMA' | 'NONE';

export interface PoolLiquidityOutput {
  chainId: number;
  poolAddress: string;
  liquidityUsd: number | null;
  volumeUsd24h: number | null;
  feesUsd24h: number | null;
  source: TvlSource;
  reliability: number; // 0..1
  fetchedAt: number;
}

// ═══════════════════════════════════════════════════════════════
// PROVIDER INTERFACE
// ═══════════════════════════════════════════════════════════════

export interface PoolLiquidityProvider {
  name: TvlSource;
  
  /**
   * Fetch liquidity data for a batch of pools
   */
  fetchBatch(input: PoolLiquidityInput[]): Promise<PoolLiquidityOutput[]>;
  
  /**
   * Check if provider supports this chain
   */
  supportsChain(chainId: number): boolean;
}

// ═══════════════════════════════════════════════════════════════
// AGGREGATED RESULT
// ═══════════════════════════════════════════════════════════════

export interface LiquidityRefreshResult {
  ok: boolean;
  chainId: number;
  poolsProcessed: number;
  poolsUpdated: number;
  avgLiquidityUsd: number;
  source: TvlSource;
  errors: string[];
  durationMs: number;
}

export interface LiquidityHealthStatus {
  enabled: boolean;
  lastRefreshAt: number | null;
  lastRefreshResult: LiquidityRefreshResult | null;
  providers: {
    name: TvlSource;
    available: boolean;
    supportedChains: number[];
  }[];
}

console.log('[OnChain V2] Liquidity Types loaded');
