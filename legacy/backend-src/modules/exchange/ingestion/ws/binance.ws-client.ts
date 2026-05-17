/**
 * Binance WebSocket Client - miniTicker stream
 */
import { BaseWsClient } from './base.ws-client.js';
import { memoryTickCache } from '../cache/memory-tick.cache.js';
import { RawTick } from '../types/market-data.js';

export class BinanceWsClient extends BaseWsClient {
  constructor(private readonly symbols: string[]) {
    super(
      'BINANCE_USDM_WS',
      `BINANCE_WS(${symbols.length})`,
      BinanceWsClient.buildUrl(symbols)
    );
  }

  private static buildUrl(symbols: string[]) {
    const streams = symbols.map((s) => `${s.toLowerCase()}@miniTicker`).join('/');
    return `wss://fstream.binance.com/stream?streams=${streams}`;
  }

  protected onOpen(): void {
    console.log(`[BINANCE_WS] subscribed symbols=${this.symbols.join(',')}`);
  }

  protected onMessage(raw: string): void {
    const parsed = JSON.parse(raw);
    const data = parsed?.data;

    if (!data?.s || !data?.c) return;

    const tick: RawTick = {
      providerId: 'BINANCE_USDM',
      providerRole: 'perp_primary',
      symbol: data.s,
      price: Number(data.c),
      timestamp: Number(data.E ?? Date.now()),
      fundingRate: null,
      openInterest: null,
      sourceType: 'ws',
    };

    if (!Number.isFinite(tick.price) || tick.price <= 0) return;

    memoryTickCache.push(tick.symbol, tick);
  }
}
