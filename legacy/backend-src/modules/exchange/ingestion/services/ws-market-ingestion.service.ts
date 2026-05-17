/**
 * WS-First Market Ingestion Service v2
 * 
 * Приоритет источников:
 * 1. Fresh WS ticks (primary)
 * 2. REST fallback (secondary)
 * 3. Last good tick cache (tertiary)
 */
import { ITickCache } from '../cache/tick-cache.interface.js';
import { memoryTickCache } from '../cache/memory-tick.cache.js';
import { TickAggregator } from './tick-aggregator.js';
import { MarketIngestionService } from './market-ingestion.service.js';
import { aggregatedTickToObservationInput } from '../adapters/observation.adapter.js';
import { isAlphaSymbol } from '../ws/symbol-groups.js';
import type { AggregatedTick } from '../types/market-data.js';

export class WsMarketIngestionService {
  private readonly cache: ITickCache;
  private readonly aggregator = new TickAggregator();
  private readonly restFallback = new MarketIngestionService();
  private readonly lastGood = new Map<string, AggregatedTick>();

  constructor(cache?: ITickCache) {
    this.cache = cache ?? memoryTickCache;
  }

  async collect(symbol: string): Promise<AggregatedTick | null> {
    const alpha = isAlphaSymbol(symbol);
    const wsFreshnessMs = alpha ? 12_000 : 20_000;

    // 1. Try WS cache first
    const wsTicks = await this.cache.getFresh(symbol, wsFreshnessMs);

    if (wsTicks.length > 0) {
      const aggregated = this.aggregator.aggregate(symbol, wsTicks);

      if (aggregated) {
        this.lastGood.set(symbol, aggregated);

        console.log(
          `[WsMarketIngestion] ✅ ${symbol} via WS | providers=${aggregated.providersUsed.join(',')} | quality=${aggregated.quality} | spread=${aggregated.priceSpreadBps}bps`
        );

        return aggregated;
      }
    }

    // 2. Fallback to REST
    const restTick = await this.restFallback.collect(symbol);
    if (restTick) {
      this.lastGood.set(symbol, restTick);
      console.warn(`[WsMarketIngestion] ⚠️  ${symbol} fallback REST`);
      return restTick;
    }

    // 3. Last resort: use cached last good tick
    const cached = this.lastGood.get(symbol);
    if (cached) {
      console.warn(`[WsMarketIngestion] 📦 ${symbol} fallback LAST_GOOD (age=${Date.now() - cached.timestamp}ms)`);
      return {
        ...cached,
        timestamp: Date.now(),
      };
    }

    return null;
  }
}
