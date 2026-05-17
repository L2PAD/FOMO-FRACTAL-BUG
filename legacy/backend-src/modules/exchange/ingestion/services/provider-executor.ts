/**
 * Provider Executor - Multi-provider fetch with isolation
 */
import type { IMarketProvider } from '../types/market-data.js';
import type { RawTick } from '../types/market-data.js';

export class ProviderExecutor {
  constructor(private readonly providers: IMarketProvider[]) {}

  async fetchAll(symbol: string): Promise<RawTick[]> {
    const supported = this.providers.filter((p) => p.supportsSymbol(symbol));

    console.log(
      `[Executor] Fetching ${symbol} from ${supported.length} providers:`,
      supported.map((p) => `${p.id}(${p.role})`).join(', ')
    );

    const results = await Promise.allSettled(
      supported.map((provider) => provider.getTicker(symbol))
    );

    const ticks: RawTick[] = [];

    for (let i = 0; i < results.length; i++) {
      const result = results[i];
      const provider = supported[i];

      if (result.status === 'fulfilled' && result.value) {
        ticks.push(result.value);
        console.log(`[Executor] ✅ ${provider.id}: $${result.value.price}`);
      } else {
        console.log(
          `[Executor] ❌ ${provider.id}: failed`,
          result.status === 'rejected' ? result.reason?.message : ''
        );
      }
    }

    return ticks;
  }
}
