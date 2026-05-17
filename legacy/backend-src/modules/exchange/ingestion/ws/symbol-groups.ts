/**
 * Symbol Partitioning - Группировка торговых пар по приоритету
 */

export const ALPHA_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];

export const SECONDARY_SYMBOLS = [
  'BNBUSDT',
  'XRPUSDT',
  'ADAUSDT',
  'DOGEUSDT',
  'LINKUSDT',
];

export const LONG_TAIL_SYMBOLS = [
  'MATICUSDT',
  'DOTUSDT',
  'AVAXUSDT',
  'UNIUSDT',
  'LTCUSDT',
  'ATOMUSDT',
  'ETCUSDT',
];

export function chunkSymbols(symbols: string[], size: number): string[][] {
  const chunks: string[][] = [];

  for (let i = 0; i < symbols.length; i += size) {
    chunks.push(symbols.slice(i, i + size));
  }

  return chunks;
}

export function isAlphaSymbol(symbol: string): boolean {
  return ALPHA_SYMBOLS.includes(symbol);
}

export function getSymbolTier(symbol: string): 'ALPHA' | 'SECONDARY' | 'LONG_TAIL' {
  if (ALPHA_SYMBOLS.includes(symbol)) return 'ALPHA';
  if (SECONDARY_SYMBOLS.includes(symbol)) return 'SECONDARY';
  return 'LONG_TAIL';
}
