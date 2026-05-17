/**
 * OnChain V2 — Token Meta Service
 * =================================
 * 
 * STEP 4: Enhanced token metadata resolver
 * 
 * Resolution order:
 * 1. Memory cache
 * 2. Token Universe (known list)
 * 3. MongoDB cache
 * 4. RPC fallback (ERC20 calls)
 */

import { TokenMetadataModel } from '../../ingestion/erc20/models';
import { 
  TOKENS_BY_CHAIN, 
  getTokenFromUniverse, 
  getUniverseAddresses,
  type TokenInfo,
} from './tokenUniverse';
import { rpcPool } from '../../rpc-pool';
import type { RpcChainId } from '../../rpc-pool/models';

// ═══════════════════════════════════════════════════════════════
// ERC20 SELECTORS
// ═══════════════════════════════════════════════════════════════

const ERC20_SYMBOL_SELECTOR = '0x95d89b41';   // symbol()
const ERC20_NAME_SELECTOR = '0x06fdde03';     // name()
const ERC20_DECIMALS_SELECTOR = '0x313ce567'; // decimals()

// Base tokens (not considered "alts")
const BASE_TOKEN_SYMBOLS = new Set(['WETH', 'USDC', 'USDT', 'DAI', 'BUSD', 'FRAX', 'WBTC', 'USDC.e', 'USDbC']);

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface TokenMeta {
  chainId: number;
  address: string;
  symbol: string;
  name: string;
  decimals: number;
  isStable: boolean;
  isBase: boolean;
  source: 'known' | 'db' | 'rpc' | 'unknown';
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function decodeString(hex: string): string | null {
  try {
    if (!hex || hex === '0x' || hex.length < 130) {
      // Might be short string (non-standard)
      if (hex && hex.length > 2) {
        const bytes = Buffer.from(hex.slice(2), 'hex');
        const str = bytes.toString('utf8').replace(/\0/g, '').trim();
        if (str && str.length > 0 && str.length < 32) return str;
      }
      return null;
    }
    
    // Standard ABI encoding: offset (32) + length (32) + data
    const data = hex.slice(2);
    const lengthHex = data.slice(64, 128);
    const length = parseInt(lengthHex, 16);
    
    if (length === 0 || length > 64) return null;
    
    const strHex = data.slice(128, 128 + length * 2);
    return Buffer.from(strHex, 'hex').toString('utf8').trim();
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
// SERVICE
// ═══════════════════════════════════════════════════════════════

class TokenMetaService {
  private cache = new Map<string, TokenMeta>();
  private pendingRpc = new Map<string, Promise<TokenMeta>>();
  
  private key(chainId: number, address: string): string {
    return `${chainId}:${address.toLowerCase()}`;
  }
  
  /**
   * Get token metadata (from cache, universe, DB, or RPC)
   */
  async get(chainId: number, address: string): Promise<TokenMeta> {
    const addr = address.toLowerCase();
    const k = this.key(chainId, addr);
    
    // 1. Check memory cache
    if (this.cache.has(k)) {
      return this.cache.get(k)!;
    }
    
    // 2. Check Token Universe (known list)
    const known = getTokenFromUniverse(chainId, addr);
    if (known) {
      const meta: TokenMeta = {
        chainId,
        address: addr,
        symbol: known.symbol,
        name: known.name,
        decimals: known.decimals,
        isStable: known.isStable ?? false,
        isBase: known.isBase ?? BASE_TOKEN_SYMBOLS.has(known.symbol),
        source: 'known',
      };
      this.cache.set(k, meta);
      return meta;
    }
    
    // 3. Check MongoDB cache
    try {
      const doc = await TokenMetadataModel.findOne({ chainId, address: addr }).lean();
      if (doc && doc.symbol) {
        const meta: TokenMeta = {
          chainId,
          address: addr,
          symbol: doc.symbol,
          name: doc.name || doc.symbol,
          decimals: doc.decimals ?? 18,
          isStable: doc.isStable ?? false,
          isBase: BASE_TOKEN_SYMBOLS.has(doc.symbol),
          source: 'db',
        };
        this.cache.set(k, meta);
        return meta;
      }
    } catch (e) {
      console.error('[TokenMeta] DB lookup error:', e);
    }
    
    // 4. RPC fallback (with deduplication)
    if (this.pendingRpc.has(k)) {
      return this.pendingRpc.get(k)!;
    }
    
    const promise = this.resolveFromRpc(chainId, addr);
    this.pendingRpc.set(k, promise);
    
    try {
      const meta = await promise;
      this.cache.set(k, meta);
      return meta;
    } finally {
      this.pendingRpc.delete(k);
    }
  }
  
  /**
   * Resolve token metadata from RPC (ERC20 calls)
   */
  private async resolveFromRpc(chainId: number, address: string): Promise<TokenMeta> {
    const addr = address.toLowerCase();
    
    try {
      // Parallel RPC calls
      const [symbolRes, nameRes, decimalsRes] = await Promise.allSettled([
        rpcPool.call<string>(chainId as RpcChainId, 'eth_call', [{ to: addr, data: ERC20_SYMBOL_SELECTOR }, 'latest']),
        rpcPool.call<string>(chainId as RpcChainId, 'eth_call', [{ to: addr, data: ERC20_NAME_SELECTOR }, 'latest']),
        rpcPool.call<string>(chainId as RpcChainId, 'eth_call', [{ to: addr, data: ERC20_DECIMALS_SELECTOR }, 'latest']),
      ]);
      
      const symbol = symbolRes.status === 'fulfilled' ? decodeString(symbolRes.value) : null;
      const name = nameRes.status === 'fulfilled' ? decodeString(nameRes.value) : null;
      const decimals = decimalsRes.status === 'fulfilled' && decimalsRes.value 
        ? parseInt(decimalsRes.value, 16) 
        : null;
      
      if (symbol || name || decimals != null) {
        const finalSymbol = symbol || `0x${addr.slice(2, 6)}...${addr.slice(-4)}`;
        const finalName = name || finalSymbol;
        const finalDecimals = (decimals != null && decimals >= 0 && decimals <= 18) ? decimals : 18;
        
        const meta: TokenMeta = {
          chainId,
          address: addr,
          symbol: finalSymbol.slice(0, 20),
          name: finalName.slice(0, 64),
          decimals: finalDecimals,
          isStable: BASE_TOKEN_SYMBOLS.has(finalSymbol.toUpperCase()),
          isBase: BASE_TOKEN_SYMBOLS.has(finalSymbol.toUpperCase()),
          source: 'rpc',
        };
        
        // Save to DB (fire and forget)
        TokenMetadataModel.updateOne(
          { chainId, address: addr },
          { $set: { symbol: meta.symbol, name: meta.name, decimals: meta.decimals, updatedAt: new Date() } },
          { upsert: true }
        ).catch(() => {});
        
        return meta;
      }
    } catch (e) {
      // RPC failed, return unknown
    }
    
    // Unknown token - return with short address as symbol
    const shortAddr = `0x${addr.slice(2, 6)}...${addr.slice(-4)}`;
    return {
      chainId,
      address: addr,
      symbol: shortAddr,
      name: 'Unknown',
      decimals: 18,
      isStable: false,
      isBase: false,
      source: 'unknown',
    };
  }
  
  /**
   * Batch get multiple tokens
   */
  async getBatch(chainId: number, addresses: string[]): Promise<Map<string, TokenMeta>> {
    const result = new Map<string, TokenMeta>();
    
    // Parallel resolve
    const metas = await Promise.all(
      addresses.map(addr => this.get(chainId, addr))
    );
    
    for (let i = 0; i < addresses.length; i++) {
      result.set(addresses[i].toLowerCase(), metas[i]);
    }
    
    return result;
  }
  
  /**
   * Get universe addresses for a chain
   */
  getUniverseAddresses(chainId: number): string[] {
    return getUniverseAddresses(chainId);
  }
  
  /**
   * Check if token is a base token (not an alt)
   */
  isBaseToken(symbol: string): boolean {
    return BASE_TOKEN_SYMBOLS.has(symbol.toUpperCase());
  }
  
  /**
   * Get stats
   */
  getStats() {
    const universeCount = Object.values(TOKENS_BY_CHAIN).reduce(
      (sum, tokens) => sum + Object.keys(tokens).length, 0
    );
    return {
      cacheSize: this.cache.size,
      pendingRpc: this.pendingRpc.size,
      universeTokens: universeCount,
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
export const tokenMetaService = new TokenMetaService();

console.log('[OnChain V2] Token Meta Service v2 loaded');
