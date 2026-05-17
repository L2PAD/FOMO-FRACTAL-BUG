/**
 * OnChain V2 — UniswapV3 TWAP Price Source
 * ==========================================
 * 
 * STEP 1: USD Valuation Layer
 * Gets token prices via Uniswap V3 TWAP (Time-Weighted Average Price).
 * Medium confidence source (0.75).
 */

import type { PriceProvider, PriceQuote, PriceSource } from '../pricing.types';
import { rpcPool, RpcChainId } from '../../../rpc-pool';
import { DexPoolModel } from '../../../ingestion/dex/models';
import { tokenMetaService } from '../../flow/tokenMeta.service';

// Stable token addresses (ETH Mainnet)
const STABLE_TOKENS: Record<number, string[]> = {
  1: [
    '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', // USDC
    '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT
    '0x6b175474e89094c44da98b954eedeac495271d0f', // DAI
  ],
  42161: [
    '0xaf88d065e77c8cc2239327c5edb3a432268e5831', // USDC (native)
    '0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9', // USDT
  ],
};

export class UniV3TwapSource implements PriceProvider {
  readonly name: PriceSource = 'UNIV3_TWAP';
  private twapWindowSec = 900; // 15 minutes
  
  async getUsdPrice(args: { chainId: number; token: string }): Promise<PriceQuote | null> {
    const token = args.token.toLowerCase();
    const chainId = args.chainId;
    
    try {
      // Find a pool with stable token
      const poolMeta = await this.findBestStablePool(chainId, token);
      if (!poolMeta) return null;
      
      // Calculate TWAP price
      const price = await this.calculateTwapPrice(chainId, poolMeta);
      if (!price || !Number.isFinite(price) || price <= 0) return null;
      
      return {
        chainId,
        token,
        priceUsd: price,
        confidence: 0.75,
        source: 'UNIV3_TWAP',
        updatedAt: Date.now(),
        meta: { pool: poolMeta.pool, windowSec: this.twapWindowSec },
      };
    } catch (error) {
      console.error(`[UniV3TwapSource] Error fetching price for ${token}:`, error);
      return null;
    }
  }
  
  private async findBestStablePool(chainId: number, token: string): Promise<{
    pool: string;
    token0: string;
    token1: string;
    decimals0: number;
    decimals1: number;
    stableToken: string;
  } | null> {
    const stables = STABLE_TOKENS[chainId] || [];
    if (stables.length === 0) return null;
    
    // Find pool where one token is our target and other is stable
    const pools = await DexPoolModel.find({
      chainId,
      enabled: true,
      $or: [
        { token0: token, token1: { $in: stables } },
        { token1: token, token0: { $in: stables } },
      ],
    }).lean();
    
    if (!pools || pools.length === 0) return null;
    
    // Take first pool (could prioritize by volume later)
    const pool = pools[0];
    
    const [meta0, meta1] = await Promise.all([
      tokenMetaService.get(chainId, pool.token0),
      tokenMetaService.get(chainId, pool.token1),
    ]);
    
    const stableToken = stables.includes(pool.token0) ? pool.token0 : pool.token1;
    
    return {
      pool: pool.address,
      token0: pool.token0,
      token1: pool.token1,
      decimals0: meta0.decimals,
      decimals1: meta1.decimals,
      stableToken,
    };
  }
  
  private async calculateTwapPrice(chainId: number, poolMeta: {
    pool: string;
    token0: string;
    token1: string;
    decimals0: number;
    decimals1: number;
    stableToken: string;
  }): Promise<number | null> {
    try {
      // Call observe() on UniV3 pool
      const secondsAgos = [this.twapWindowSec, 0];
      
      // Encode observe call: observe(uint32[] secondsAgos)
      // Function selector: 0x883bdbfd
      const encodedCall = this.encodeObserveCall(secondsAgos);
      
      const result = await rpcPool.call<string>(
        chainId as RpcChainId,
        'eth_call',
        [{ to: poolMeta.pool, data: encodedCall }, 'latest']
      );
      
      // Decode result
      const avgTick = this.decodeObserveResult(result, this.twapWindowSec);
      if (avgTick === null) return null;
      
      // Convert tick to price
      const price1Per0 = Math.pow(1.0001, avgTick);
      
      // Determine which way to calculate price
      const targetIsToken0 = poolMeta.token0 !== poolMeta.stableToken;
      
      if (targetIsToken0) {
        // Target is token0, stable is token1
        // price1Per0 = token1/token0, so token0 price = price1Per0 * (stable price = 1)
        const decimalAdjust = Math.pow(10, poolMeta.decimals1 - poolMeta.decimals0);
        return price1Per0 * decimalAdjust;
      } else {
        // Target is token1, stable is token0
        // price1Per0 = token1/token0, so token1 price = 1/price1Per0
        const decimalAdjust = Math.pow(10, poolMeta.decimals0 - poolMeta.decimals1);
        return (1 / price1Per0) * decimalAdjust;
      }
    } catch (error) {
      console.error('[UniV3TwapSource] TWAP calculation error:', error);
      return null;
    }
  }
  
  private encodeObserveCall(secondsAgos: number[]): string {
    // observe(uint32[] calldata secondsAgos)
    // Selector: 0x883bdbfd
    // ABI encode: offset(32) + length(32) + values...
    const selector = '0x883bdbfd';
    const offset = '0000000000000000000000000000000000000000000000000000000000000020'; // 32
    const length = this.toHex32(secondsAgos.length);
    const values = secondsAgos.map(v => this.toHex32(v)).join('');
    return selector + offset + length + values;
  }
  
  private decodeObserveResult(result: string, windowSec: number): number | null {
    try {
      const hex = result.slice(2);
      // observe returns: (int56[] tickCumulatives, uint160[] secondsPerLiquidityCumulativeX128s)
      // First array starts at offset 64 (skip 2 offsets)
      // tickCumulatives offset at bytes 0-32
      // tickCumulatives length at that offset
      
      // Simplified: assume 2 elements
      // tickCumulative[0] at offset ~128
      // tickCumulative[1] at offset ~192
      
      const tick0Hex = hex.slice(128, 192);
      const tick1Hex = hex.slice(192, 256);
      
      const tick0 = this.parseSignedInt56(tick0Hex);
      const tick1 = this.parseSignedInt56(tick1Hex);
      
      const tickDelta = Number(tick1 - tick0);
      return tickDelta / windowSec;
    } catch {
      return null;
    }
  }
  
  private parseSignedInt56(hex: string): bigint {
    // int56 is 7 bytes, but padded to 32 bytes
    const value = BigInt('0x' + hex);
    const mask = (1n << 56n) - 1n;
    const signBit = 1n << 55n;
    const truncated = value & mask;
    if (truncated & signBit) {
      return truncated - (1n << 56n);
    }
    return truncated;
  }
  
  private toHex32(n: number): string {
    return n.toString(16).padStart(64, '0');
  }
}

export const uniV3TwapSource = new UniV3TwapSource();
console.log('[OnChain V2] UniV3 TWAP Price Source loaded');
