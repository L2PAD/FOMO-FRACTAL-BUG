/**
 * Bybit Provider - Perp Primary (Tier A)
 */
import axios from 'axios';
import type { IMarketProvider, RawTick } from '../types/market-data.js';

export class BybitProvider implements IMarketProvider {
  id: RawTick['providerId'] = 'BYBIT_USDTPERP';
  role: RawTick['providerRole'] = 'perp_primary';

  supportsSymbol(symbol: string): boolean {
    return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'].includes(symbol);
  }

  async getTicker(symbol: string): Promise<RawTick | null> {
    try {
      const [tickerRes, fundingRes, oiRes] = await Promise.allSettled([
        axios.get('https://api.bybit.com/v5/market/tickers', {
          params: { category: 'linear', symbol },
          timeout: 8000,
        }),
        axios.get('https://api.bybit.com/v5/market/funding/history', {
          params: { category: 'linear', symbol, limit: 1 },
          timeout: 8000,
        }),
        axios.get('https://api.bybit.com/v5/market/open-interest', {
          params: { category: 'linear', symbol, intervalTime: '5min', limit: 1 },
          timeout: 8000,
        }),
      ]);

      const ticker =
        tickerRes.status === 'fulfilled'
          ? tickerRes.value.data?.result?.list?.[0]
          : null;

      const price = ticker ? Number(ticker.lastPrice) : null;
      if (!price || Number.isNaN(price)) return null;

      const fundingRate =
        fundingRes.status === 'fulfilled'
          ? Number(fundingRes.value.data?.result?.list?.[0]?.fundingRate ?? null)
          : null;

      const openInterest =
        oiRes.status === 'fulfilled'
          ? Number(oiRes.value.data?.result?.list?.[0]?.openInterest ?? null)
          : null;

      return {
        providerId: this.id,
        providerRole: this.role,
        symbol,
        price,
        timestamp: Date.now(),
        fundingRate,
        openInterest,
        sourceType: 'rest',
      };
    } catch (error: any) {
      console.error(`[Bybit] ${symbol} failed:`, error?.message);
      return null;
    }
  }
}
