/**
 * Market Ingestion Service - Production Ready
 */
import { HyperliquidProvider } from '../providers/hyperliquid.provider.js';
import { BybitProvider } from '../providers/bybit.provider.js';
import { BinanceProvider } from '../providers/binance.provider.js';
import { CoinbaseProvider } from '../providers/coinbase.provider.js';
import { CoinGeckoProvider } from '../providers/coingecko.provider.js';
import { MockProvider } from '../providers/mock.provider.js';
import { ProviderExecutor } from './provider-executor.js';
import { TickAggregator } from './tick-aggregator.js';
import type { AggregatedTick } from '../types/market-data.js';

export class MarketIngestionService {
  private executor = new ProviderExecutor([
    new HyperliquidProvider(),
    new BybitProvider(),
    new BinanceProvider(),
    new CoinbaseProvider(),
    new CoinGeckoProvider(),
    new MockProvider(),
  ]);

  private aggregator = new TickAggregator();

  async collect(symbol: string): Promise<AggregatedTick | null> {
    console.log(`\n[MarketIngestion] === Collecting ${symbol} ===`);

    const ticks = await this.executor.fetchAll(symbol);

    if (!ticks.length) {
      console.error(`[MarketIngestion] \u274c No ticks for ${symbol}`);
      return null;
    }

    const aggregated = this.aggregator.aggregate(symbol, ticks);
    if (!aggregated) {
      console.error(`[MarketIngestion] \u274c Aggregation failed for ${symbol}`);
      return null;
    }

    console.log(
      `[MarketIngestion] \u2705 ${symbol} | price=$${aggregated.price.toFixed(2)} | providers=${aggregated.providersUsed.join(',')} | quality=${aggregated.quality} | spread=${aggregated.priceSpreadBps}bps`
    );

    return aggregated;
  }
}
