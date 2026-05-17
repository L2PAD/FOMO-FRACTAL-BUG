/**
 * Binance USDM Provider - Perp Primary (Tier A)
 */
import axios from 'axios';
import type { IMarketProvider, RawTick } from '../types/market-data.js';

export class BinanceProvider implements IMarketProvider {
  id: RawTick['providerId'] = 'BINANCE_USDM';
  role: RawTick['providerRole'] = 'perp_primary';

  supportsSymbol(symbol: string): boolean {
    return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'].includes(symbol);
  }

  async getTicker(symbol: string): Promise<RawTick | null> {
    try {
      const [priceRes, fundingRes, oiRes] = await Promise.allSettled([
        axios.get('https://fapi.binance.com/fapi/v1/ticker/price', {
          params: { symbol },
          timeout: 8000,
        }),
        axios.get('https://fapi.binance.com/fapi/v1/premiumIndex', {
          params: { symbol },
          timeout: 8000,
        }),
        axios.get('https://fapi.binance.com/futures/data/openInterestHist', {
          params: { symbol, period: '5m', limit: 1 },
          timeout: 8000,
        }),
      ]);

      const price =
        priceRes.status === 'fulfilled'
          ? Number(priceRes.value.data.price)
          : null;

      if (!price || Number.isNaN(price)) return null;

      const fundingRate =
        fundingRes.status === 'fulfilled'
          ? Number(fundingRes.value.data.lastFundingRate)
          : null;

      const openInterest =
        oiRes.status === 'fulfilled' &&
        Array.isArray(oiRes.value.data) &&
        oiRes.value.data[0]
          ? Number(oiRes.value.data[0].sumOpenInterest)
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
      console.error(`[Binance] ${symbol} failed:`, error?.message);
      return null;
    }
  }
}
