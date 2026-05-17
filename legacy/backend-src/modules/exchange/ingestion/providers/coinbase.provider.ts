/**
 * Coinbase Provider - Spot Validation (Tier B)
 */
import axios from 'axios';
import type { IMarketProvider, RawTick } from '../types/market-data.js';

export class CoinbaseProvider implements IMarketProvider {
  id: RawTick['providerId'] = 'COINBASE_SPOT';
  role: RawTick['providerRole'] = 'spot_validation';

  supportsSymbol(symbol: string): boolean {
    return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'].includes(symbol);
  }

  async getTicker(symbol: string): Promise<RawTick | null> {
    try {
      const productMap: Record<string, string> = {
        BTCUSDT: 'BTC-USD',
        ETHUSDT: 'ETH-USD',
        SOLUSDT: 'SOL-USD',
      };

      const productId = productMap[symbol];
      if (!productId) return null;

      const res = await axios.get(
        `https://api.exchange.coinbase.com/products/${productId}/ticker`,
        { timeout: 8000 }
      );

      const price = Number(res.data?.price);
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
      console.error(`[Coinbase] ${symbol} failed:`, error?.message);
      return null;
    }
  }
}
