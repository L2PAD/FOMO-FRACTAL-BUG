/**
 * TOP 20 Symbols for Sentiment Analysis
 * =====================================
 * 
 * BLOCK 4: Фиксированный список символов для агрегации
 * 
 * Принцип:
 * - Никакой динамики
 * - Предсказуемость
 * - Легко заморозить
 * - Top по ликвидности
 */

export const SENTIMENT_TOP20 = [
  'BTC',
  'ETH',
  'SOL',
  'BNB',
  'XRP',
  'ADA',
  'AVAX',
  'DOGE',
  'DOT',
  'MATIC',
  'LINK',
  'LTC',
  'ATOM',
  'NEAR',
  'APT',
  'ARB',
  'OP',
  'UNI',
  'INJ',
  'SUI',
] as const;

export type SentimentSymbol = typeof SENTIMENT_TOP20[number];

/**
 * Check if symbol is in TOP 20
 */
export function isTop20Symbol(symbol: string): boolean {
  return SENTIMENT_TOP20.includes(symbol.toUpperCase() as SentimentSymbol);
}
