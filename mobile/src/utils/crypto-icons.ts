/**
 * Crypto Asset Icon utility.
 *
 * Powered by our backend /api/assets/logo/{symbol} endpoint — single source
 * of truth backed by CoinGecko (250+ coins cached in MongoDB, on-demand
 * autofill for new symbols).
 *
 * Replaces the old `cryptocurrency-icons` CDN which only covered ~500 coins
 * and missed many newer ones (PEPE, TIA, INJ, FET, etc.).
 */

const BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_URL ||
  process.env.EXPO_PUBLIC_API_URL ||
  '';

const FALLBACK_SOURCE_CDN =
  'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color';

export function getCryptoIconUrl(symbol: string, size: 'thumb' | 'small' | 'large' = 'small'): string {
  const sym = (symbol || 'generic').toUpperCase();
  const base = BACKEND_URL.replace(/\/$/, '');
  return `${base}/api/assets/logo/${encodeURIComponent(sym)}?size=${size}`;
}

// Fallback for offline / unknown cases (used directly in a few places)
export const FALLBACK_ICON = `${FALLBACK_SOURCE_CDN}/generic.png`;

/**
 * Source / platform / exchange logo URL — Twitter, Telegram, CoinDesk, Binance, etc.
 */
export function getSourceIconUrl(slug: string): string {
  const key = (slug || 'generic').toLowerCase();
  const base = BACKEND_URL.replace(/\/$/, '');
  return `${base}/api/assets/source/${encodeURIComponent(key)}`;
}
