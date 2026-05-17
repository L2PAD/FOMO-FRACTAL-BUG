/**
 * Symbol Extractor
 * ================
 * 
 * BLOCK 2B: Извлечение криптосимволов из текста твита
 * 
 * Поддерживает:
 * - $BTC, $ETH (cashtag)
 * - #BTC, #ETH (hashtag)  
 * - bitcoin, ethereum (aliases)
 * - BTC, ETH (plain uppercase)
 * 
 * Whitelist для фильтрации мусора
 */

// Alias mapping: lowercase word → canonical symbol
const ALIASES: Record<string, string> = {
  // Bitcoin
  bitcoin: 'BTC',
  btc: 'BTC',
  
  // Ethereum  
  ethereum: 'ETH',
  eth: 'ETH',
  ether: 'ETH',
  
  // Solana
  solana: 'SOL',
  sol: 'SOL',
  
  // BNB
  binance: 'BNB',
  bnb: 'BNB',
  
  // XRP
  ripple: 'XRP',
  xrp: 'XRP',
  
  // Other majors
  cardano: 'ADA',
  ada: 'ADA',
  dogecoin: 'DOGE',
  doge: 'DOGE',
  polkadot: 'DOT',
  dot: 'DOT',
  avalanche: 'AVAX',
  avax: 'AVAX',
  polygon: 'MATIC',
  matic: 'MATIC',
  chainlink: 'LINK',
  link: 'LINK',
  uniswap: 'UNI',
  uni: 'UNI',
  litecoin: 'LTC',
  ltc: 'LTC',
  
  // Stablecoins (excluded from trading signals)
  // usdt: 'USDT',
  // usdc: 'USDC',
};

// Whitelist of valid trading symbols (exclude stablecoins)
const WHITELIST = new Set([
  'BTC', 'ETH', 'SOL', 'BNB', 'XRP',
  'ADA', 'DOGE', 'DOT', 'AVAX', 'MATIC',
  'LINK', 'UNI', 'LTC', 'ATOM', 'NEAR',
  'APT', 'ARB', 'OP', 'SUI', 'SEI',
  'INJ', 'TIA', 'PYTH', 'JUP', 'WIF',
  'PEPE', 'SHIB', 'BONK', 'FLOKI',
]);

// Regex patterns
const CASHTAG_RE = /\$([A-Z]{2,10})\b/gi;      // $BTC, $eth
const HASHTAG_RE = /#([A-Z]{2,10})\b/gi;       // #BTC, #ETH
const PLAIN_RE = /\b([A-Z]{2,10})\b/g;          // BTC, ETH (uppercase only)

/**
 * Extract crypto symbols from tweet text
 * 
 * @param text - Tweet text
 * @param maxSymbols - Maximum symbols to return (default 3)
 * @returns Array of canonical symbols (uppercase)
 */
export function extractSymbols(text: string, maxSymbols = 3): string[] {
  const out = new Set<string>();
  const t = (text || '').trim();
  
  if (!t) return [];

  // 1. Extract cashtags ($BTC)
  let match: RegExpExecArray | null;
  
  const cashtagRe = new RegExp(CASHTAG_RE);
  while ((match = cashtagRe.exec(t)) && out.size < maxSymbols) {
    const sym = match[1].toUpperCase();
    if (WHITELIST.has(sym)) {
      out.add(sym);
    }
  }

  // 2. Extract hashtags (#BTC)
  const hashtagRe = new RegExp(HASHTAG_RE);
  while ((match = hashtagRe.exec(t)) && out.size < maxSymbols) {
    const sym = match[1].toUpperCase();
    if (WHITELIST.has(sym)) {
      out.add(sym);
    }
  }

  // 3. Extract plain uppercase symbols (BTC ETH)
  const plainRe = new RegExp(PLAIN_RE);
  while ((match = plainRe.exec(t)) && out.size < maxSymbols) {
    const sym = match[1];
    if (WHITELIST.has(sym)) {
      out.add(sym);
    }
  }

  // 4. Extract aliases (bitcoin, ethereum, solana)
  const words = t.toLowerCase().split(/\W+/);
  for (const word of words) {
    if (out.size >= maxSymbols) break;
    
    const alias = ALIASES[word];
    if (alias && WHITELIST.has(alias)) {
      out.add(alias);
    }
  }

  return Array.from(out).slice(0, maxSymbols);
}

/**
 * Check if text contains any crypto symbols
 */
export function hasCryptoMention(text: string): boolean {
  return extractSymbols(text, 1).length > 0;
}

/**
 * Get whitelist of supported symbols
 */
export function getSupportedSymbols(): string[] {
  return Array.from(WHITELIST);
}
