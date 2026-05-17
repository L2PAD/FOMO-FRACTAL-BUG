/**
 * Bybit WebSocket Client - tickers stream
 */
import { BaseWsClient } from './base.ws-client.js';
import { memoryTickCache } from '../cache/memory-tick.cache.js';
import { RawTick } from '../types/market-data.js';

export class BybitWsClient extends BaseWsClient {
  constructor(private readonly symbols: string[]) {
    super(
      'BYBIT_USDTPERP_WS',
      `BYBIT_WS(${symbols.length})`,
      'wss://stream.bybit.com/v5/public/linear'
    );
  }

  protected onOpen(): void {
    const args = this.symbols.map((symbol) => `tickers.${symbol}`);
    this.send({ op: 'subscribe', args });
    console.log(`[BYBIT_WS] subscribed symbols=${this.symbols.join(',')}`);
  }

  protected onMessage(raw: string): void {
    const parsed = JSON.parse(raw);

    // Ignore pong
    if (parsed?.op === 'pong' || parsed?.ret_msg === 'pong') return;

    const topic = parsed?.topic;
    const item = parsed?.data;

    if (!topic || !item) return;

    const symbol = item.symbol;
    const lastPrice = Number(item.lastPrice);

    if (!symbol || !Number.isFinite(lastPrice) || lastPrice <= 0) return;

    const tick: RawTick = {
      providerId: 'BYBIT_USDTPERP',
      providerRole: 'perp_primary',
      symbol,
      price: lastPrice,
      timestamp: Date.now(),
      fundingRate: item.fundingRate ? Number(item.fundingRate) : null,
      openInterest: item.openInterest ? Number(item.openInterest) : null,
      sourceType: 'ws',
    };

    memoryTickCache.push(symbol, tick);
  }

  protected override sendPing(): void {
    this.send({ op: 'ping' });
  }
}
