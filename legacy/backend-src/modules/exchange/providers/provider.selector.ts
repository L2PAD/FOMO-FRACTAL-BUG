/**
 * X1 — Provider Selector
 * =======================
 * 
 * Resolves the best provider for a given symbol.
 * Falls back to MOCK if no provider available.
 */

import { IExchangeProvider, ProviderId } from './exchangeProvider.types.js';
import { getEnabledProviders, getProvider } from './provider.registry.js';

// Symbol cache to avoid repeated getSymbols calls
const symbolCache = new Map<ProviderId, { symbols: Set<string>; cachedAt: number }>();
const CACHE_TTL_MS = 5 * 60 * 1000;  // 5 minutes

// Preferred providers for perp/futures symbols
const PREFERRED_PROVIDER_IDS = ['BYBIT_USDTPERP', 'BINANCE_USDM'];

/**
 * Resolve the best provider for a symbol
 */
export async function resolveProviderForSymbol(
  symbol: string
): Promise<IExchangeProvider> {
  const normalizedSymbol = symbol.toUpperCase().replace('-', '');
  const candidates = getEnabledProviders();
  
  // Log all candidates for debug
  console.log(`[Selector] Candidates for ${symbol}:`, candidates.map(e => ({
    id: e.provider?.id,
    priority: e.config?.priority,
    enabled: e.config?.enabled,
    health: e.health?.status,
  })));
  
  // Common symbols that all major providers support
  const COMMON_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT'];
  const isCommonSymbol = COMMON_SYMBOLS.includes(normalizedSymbol);
  
  // For common symbols, prefer perp/futures providers
  if (isCommonSymbol) {
    const preferred = candidates.find(e => PREFERRED_PROVIDER_IDS.includes(e.provider.id));
    if (preferred) {
      console.log(`[Selector] Using preferred ${preferred.provider.id} for common symbol ${symbol}`);
      return preferred.provider;
    }
  }
  
  // Default: use highest priority provider
  if (candidates.length > 0) {
    const selected = candidates[0];
    console.log(`[Selector] Using ${selected.provider.id} for ${symbol} (priority: ${selected.config.priority})`);
    return selected.provider;
  }
  
  // Fallback to MOCK provider
  const mockEntry = getProvider('MOCK');
  if (mockEntry) {
    console.warn(`[Selector] No real provider for ${symbol}, using MOCK`);
    return mockEntry.provider;
  }
  
  throw new Error(`No provider available for symbol ${symbol}`);
}

/**
 * Clear symbol cache (admin action)
 */
export function clearSymbolCache(): void {
  symbolCache.clear();
  console.log('[Selector] Symbol cache cleared');
}

/**
 * Get cache stats
 */
export function getCacheStats() {
  const entries: Record<string, number> = {};
  symbolCache.forEach((value, key) => {
    entries[key] = value.symbols.size;
  });
  return entries;
}

console.log('[X1] Provider Selector loaded');
