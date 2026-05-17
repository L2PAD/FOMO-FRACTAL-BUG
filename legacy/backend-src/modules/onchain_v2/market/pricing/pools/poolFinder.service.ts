/**
 * OnChain V2 — Pool Finder Service
 * ==================================
 * 
 * STEP 2.5.3: Finds Uniswap V3 pools via Factory contract
 */

import { rpcPool } from '../../../rpc-pool';
import { DISCOVERY } from './poolScoring.constants';
import type { RpcChainId } from '../../../rpc-pool/models';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

// UniV3 Factory getPool(address,address,uint24) selector
const GET_POOL_SELECTOR = '0x1698ee82';
const ZERO_ADDRESS = '0x0000000000000000000000000000000000000000';

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function encodeGetPool(tokenA: string, tokenB: string, fee: number): string {
  // Encode: getPool(address tokenA, address tokenB, uint24 fee)
  const a = tokenA.toLowerCase().replace('0x', '').padStart(64, '0');
  const b = tokenB.toLowerCase().replace('0x', '').padStart(64, '0');
  const f = fee.toString(16).padStart(64, '0');
  return GET_POOL_SELECTOR + a + b + f;
}

function decodeAddress(hex: string): string {
  if (!hex || hex === '0x') return ZERO_ADDRESS;
  // Address is in last 40 chars of the 64-char (32-byte) return value
  const clean = hex.replace('0x', '');
  if (clean.length < 40) return ZERO_ADDRESS;
  return '0x' + clean.slice(-40).toLowerCase();
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

export class PoolFinderService {
  
  /**
   * Find UniV3 pools for a token pair across all fee tiers
   */
  async findUniV3Pools(args: {
    chainId: number;
    tokenA: string;
    tokenB: string;
  }): Promise<{ pool: string; fee: number }[]> {
    const { chainId, tokenA, tokenB } = args;
    
    const factory = DISCOVERY.UNIV3_FACTORY[chainId];
    if (!factory) {
      return [];
    }
    
    const results: { pool: string; fee: number }[] = [];
    
    // Query all fee tiers in parallel
    const promises = DISCOVERY.FEES.map(async (fee) => {
      try {
        const data = encodeGetPool(tokenA, tokenB, fee);
        const result = await rpcPool.call<string>(
          chainId as RpcChainId,
          'eth_call',
          [{ to: factory, data }, 'latest']
        );
        
        const poolAddress = decodeAddress(result);
        if (poolAddress && poolAddress !== ZERO_ADDRESS) {
          return { pool: poolAddress, fee };
        }
        return null;
      } catch {
        return null;
      }
    });
    
    const resolved = await Promise.all(promises);
    
    for (const r of resolved) {
      if (r) results.push(r);
    }
    
    return results;
  }
  
  /**
   * Find a specific pool by tokens and fee
   */
  async findPool(chainId: number, tokenA: string, tokenB: string, fee: number): Promise<string | null> {
    const factory = DISCOVERY.UNIV3_FACTORY[chainId];
    if (!factory) return null;
    
    try {
      const data = encodeGetPool(tokenA, tokenB, fee);
      const result = await rpcPool.call<string>(
        chainId as RpcChainId,
        'eth_call',
        [{ to: factory, data }, 'latest']
      );
      
      const poolAddress = decodeAddress(result);
      if (poolAddress && poolAddress !== ZERO_ADDRESS) {
        return poolAddress;
      }
      return null;
    } catch {
      return null;
    }
  }
  
  /**
   * Check if factory is configured for chain
   */
  hasFactory(chainId: number): boolean {
    return !!DISCOVERY.UNIV3_FACTORY[chainId];
  }
}

export const poolFinderService = new PoolFinderService();

console.log('[OnChain V2] Pool Finder Service loaded');
