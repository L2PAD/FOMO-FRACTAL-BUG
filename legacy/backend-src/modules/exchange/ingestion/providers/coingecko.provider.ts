/**
 * CoinGecko Provider - Fallback (Tier B)
 */
import axios from 'axios';
import type { IMarketProvider, RawTick } from '../types/market-data.js';

const SYMBOL_MAP: Record<string, string> = {
  BTCUSDT: 'bitcoin',
  ETHUSDT: 'ethereum',
  SOLUSDT: 'solana',
  BNBUSDT: 'binancecoin',
  XRPUSDT: 'ripple',
  ADAUSDT: 'cardano',
  DOGEUSDT: 'dogecoin',
  MATICUSDT: 'matic-network',
  DOTUSDT: 'polkadot',
  AVAXUSDT: 'avalanche-2',
  LINKUSDT: 'chainlink',
  UNIUSDT: 'uniswap',
  LTCUSDT: 'litecoin',
  ATOMUSDT: 'cosmos',
  ETCUSDT: 'ethereum-classic',
};

export class CoinGeckoProvider implements IMarketProvider {
  id: RawTick['providerId'] = 'COINGECKO';
  role: RawTick['providerRole'] = 'fallback';

  supportsSymbol(symbol: string): boolean {
    return Boolean(SYMBOL_MAP[symbol]);
  }

  async getTicker(symbol: string): Promise<RawTick | null> {
    try {
      const coinId = SYMBOL_MAP[symbol];
      if (!coinId) return null;

      const res = await axios.get(
        'https://api.coingecko.com/api/v3/simple/price',
        {
          params: { ids: coinId, vs_currencies: 'usd' },
          timeout: 8000,
        }
      );

      const price = Number(res.data?.[coinId]?.usd);
      if (!price || Number.isNaN(price)) return null;

      return {
        providerId: this.id,
        providerRole: this.role,
        symbol,
        price,
        timestamp: Date.now(),
        fundingRate: null,
        openInterest: null,
        sourceType: 'rest',
      };
    } catch (error: any) {
      console.error(`[CoinGecko] ${symbol} failed:`, error?.message);
      return null;
    }
  }
}
