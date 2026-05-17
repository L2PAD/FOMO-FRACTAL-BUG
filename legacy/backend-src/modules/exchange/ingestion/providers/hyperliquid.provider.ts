/**
 * Hyperliquid Provider - Perp Primary (Tier A)
 */
import axios from 'axios';
import type { IMarketProvider, RawTick } from '../types/market-data.js';

export class HyperliquidProvider implements IMarketProvider {
  id: RawTick['providerId'] = 'HYPERLIQUID';
  role: RawTick['providerRole'] = 'perp_primary';

  supportsSymbol(symbol: string): boolean {
    return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'].includes(symbol);
  }

  async getTicker(symbol: string): Promise<RawTick | null> {
    try {
      const coin = symbol.replace('USDT', '');

      const res = await axios.post(
        'https://api.hyperliquid.xyz/info',
        { type: 'metaAndAssetCtxs' },
        { timeout: 8000 }
      );

      const [, assetCtxs] = res.data;
      const asset = assetCtxs.find((a: any) => a.coin === coin);

      if (!asset?.markPx) return null;

      return {
        providerId: this.id,
        providerRole: this.role,
        symbol,
        price: Number(asset.markPx),
        timestamp: Date.now(),
        fundingRate: asset.funding ? Number(asset.funding) : null,
        openInterest: asset.openInterest ? Number(asset.openInterest) : null,
        sourceType: 'rest',
      };
    } catch (error: any) {
      console.error(`[Hyperliquid] ${symbol} failed:`, error?.message);
      return null;
    }
  }
}
