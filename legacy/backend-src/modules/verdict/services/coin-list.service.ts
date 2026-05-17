/**
 * Coin List Service
 * =================
 * Fetches Top N coins from CoinGecko (free API, no key required).
 * Caches results to avoid rate limiting.
 * Used by HeavyVerdictJob for expanding analysis to Top 300 coins.
 */

const COINGECKO_API = 'https://api.coingecko.com/api/v3';
const CACHE_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours
const MAX_PER_PAGE = 250; // CoinGecko max per page

interface CoinEntry {
  id: string;
  symbol: string;
  name: string;
  market_cap_rank: number;
}

interface CoinListCache {
  symbols: string[];
  fetchedAt: number;
  count: number;
}

class CoinListService {
  private cache: CoinListCache | null = null;

  /**
   * Get Top N coin symbols (e.g., ['BTC', 'ETH', 'SOL', ...])
   * Returns uppercase ticker symbols.
   */
  async getTopCoins(n: number = 300): Promise<string[]> {
    // Check cache
    if (this.cache && Date.now() - this.cache.fetchedAt < CACHE_TTL_MS && this.cache.count >= n) {
      return this.cache.symbols.slice(0, n);
    }

    try {
      const symbols = await this.fetchFromCoinGecko(n);
      this.cache = {
        symbols,
        fetchedAt: Date.now(),
        count: symbols.length,
      };
      console.log(`[CoinListService] Fetched ${symbols.length} top coins from CoinGecko`);
      return symbols.slice(0, n);
    } catch (err: any) {
      console.error(`[CoinListService] CoinGecko fetch failed: ${err.message}`);

      // Fallback: return cached or hardcoded top coins
      if (this.cache) {
        console.log(`[CoinListService] Using stale cache (${this.cache.count} coins)`);
        return this.cache.symbols.slice(0, n);
      }

      console.log(`[CoinListService] Using hardcoded fallback`);
      return HARDCODED_TOP_50.slice(0, n);
    }
  }

  /**
   * Fetch coin list from CoinGecko markets API.
   * Uses pagination to get 300+ coins. Handles rate limits gracefully.
   */
  private async fetchFromCoinGecko(n: number): Promise<string[]> {
    const allSymbols: string[] = [];
    const PER_PAGE = 250;
    const pages = Math.ceil(n / PER_PAGE);

    for (let page = 1; page <= pages; page++) {
      const perPage = Math.min(PER_PAGE, n - allSymbols.length);
      const url = `${COINGECKO_API}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=${perPage}&page=${page}&sparkline=false`;

      try {
        const response = await fetch(url, {
          headers: { 'Accept': 'application/json' },
          signal: AbortSignal.timeout(20000),
        });

        if (response.status === 429) {
          // Rate limited — wait longer and retry once
          console.warn(`[CoinListService] Rate limited on page ${page}, waiting 5s...`);
          await new Promise(r => setTimeout(r, 5000));
          const retry = await fetch(url, {
            headers: { 'Accept': 'application/json' },
            signal: AbortSignal.timeout(20000),
          });
          if (!retry.ok) {
            console.error(`[CoinListService] Retry failed for page ${page}: ${retry.status}`);
            break;
          }
          const data: CoinEntry[] = await retry.json();
          for (const coin of data) allSymbols.push(coin.symbol.toUpperCase());
        } else if (!response.ok) {
          console.error(`[CoinListService] CoinGecko API ${response.status} on page ${page}`);
          break;
        } else {
          const data: CoinEntry[] = await response.json();
          for (const coin of data) allSymbols.push(coin.symbol.toUpperCase());
        }

        // Longer delay between pages to avoid rate limiting
        if (page < pages) {
          await new Promise(r => setTimeout(r, 3000));
        }
      } catch (err: any) {
        console.error(`[CoinListService] Page ${page} error: ${err.message}`);
        break; // Use what we have
      }
    }

    // Deduplicate
    return [...new Set(allSymbols)];
  }

  /**
   * Get cache info for monitoring
   */
  getCacheInfo(): { hasCached: boolean; count: number; ageMinutes: number } {
    if (!this.cache) return { hasCached: false, count: 0, ageMinutes: 0 };
    return {
      hasCached: true,
      count: this.cache.count,
      ageMinutes: Math.round((Date.now() - this.cache.fetchedAt) / 60000),
    };
  }
}

// Hardcoded fallback for when CoinGecko is unavailable
const HARDCODED_TOP_50 = [
  'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'XRP', 'USDC', 'ADA', 'DOGE', 'AVAX',
  'DOT', 'TRX', 'LINK', 'MATIC', 'TON', 'SHIB', 'DAI', 'LTC', 'BCH', 'ATOM',
  'UNI', 'XLM', 'NEAR', 'XMR', 'PEPE', 'ETC', 'OKB', 'HBAR', 'APT', 'FIL',
  'ARB', 'MNT', 'IMX', 'MKR', 'OP', 'INJ', 'VET', 'RUNE', 'GRT', 'AAVE',
  'FTM', 'ALGO', 'THETA', 'FLR', 'FLOW', 'AXS', 'SAND', 'MANA', 'SUI', 'SEI',
];

export const coinListService = new CoinListService();
