/**
 * Mock Provider - Safety Net
 */
import type { IMarketProvider, RawTick } from '../types/market-data.js';

const BASE_PRICES: Record<string, number> = {
  BTCUSDT: 70000,
  ETHUSDT: 3500,
  SOLUSDT: 180,
  BNBUSDT: 600,
  XRPUSDT: 0.52,
  ADAUSDT: 0.38,
  DOGEUSDT: 0.12,
  MATICUSDT: 0.45,
  DOTUSDT: 5.2,
  AVAXUSDT: 26,
  LINKUSDT: 14,
  UNIUSDT: 7.5,
  LTCUSDT: 85,
  ATOMUSDT: 7.8,
  ETCUSDT: 20,
};

export class MockProvider implements IMarketProvider {
  id: RawTick['providerId'] = 'MOCK';
  role: RawTick['providerRole'] = 'mock';

  supportsSymbol(symbol: string): boolean {
    return Boolean(BASE_PRICES[symbol]);
  }

  async getTicker(symbol: string): Promise<RawTick | null> {
    const base = BASE_PRICES[symbol];
    if (!base) return null;

    const noise = (Math.random() - 0.5) * 0.01;
    const price = base * (1 + noise);

    return {
      providerId: this.id,
      providerRole: this.role,
      symbol,
      price,
      timestamp: Date.now(),
      fundingRate: 0,
      openInterest: null,
      sourceType: 'mock',
    };
  }
}
