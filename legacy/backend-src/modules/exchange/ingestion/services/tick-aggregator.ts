/**
 * Tick Aggregator v2 - Weighted aggregation with provider health
 */
import type { AggregatedTick, RawTick } from '../types/market-data.js';
import { providerHealthTracker } from '../ws/provider-health.js';

// Base weights по приоритету источников
const BASE_WEIGHTS: Record<string, number> = {
  HYPERLIQUID: 1.0,
  BYBIT_USDTPERP: 1.0,
  BYBIT_USDTPERP_WS: 1.0,
  BINANCE_USDM: 0.95,
  BINANCE_USDM_WS: 0.95,
  COINBASE_SPOT: 0.7,
  COINGECKO: 0.5,
  MOCK: 0.1,
};

export class TickAggregator {
  aggregate(symbol: string, ticks: RawTick[]): AggregatedTick | null {
    const valid = ticks.filter(
      (t) => t && Number.isFinite(t.price) && t.price > 0
    );

    if (!valid.length) return null;

    // Separate by role
    const perpTicks = valid.filter((t) => t.providerRole === 'perp_primary');
    const validationTicks = valid.filter(
      (t) => t.providerRole === 'spot_validation'
    );
    const fallbackTicks = valid.filter((t) => t.providerRole === 'fallback');

    // Calculate weighted average price (учитывает health)
    const weightedPrice = this.weightedAverage(valid);

    // Calculate median price для spread
    const prices = valid.map((t) => t.price).sort((a, b) => a - b);
    const medianPrice = this.median(prices);

    // Calculate spread
    const minPrice = prices[0];
    const maxPrice = prices[prices.length - 1];
    const reference = medianPrice || weightedPrice;
    const spreadBps = reference > 0 ? ((maxPrice - minPrice) / reference) * 10000 : 0;

    // Get funding rate and OI from perp sources
    const fundingCandidates = perpTicks
      .map((t) => t.fundingRate)
      .filter((v): v is number => typeof v === 'number' && !Number.isNaN(v));

    const oiCandidates = perpTicks
      .map((t) => t.openInterest)
      .filter((v): v is number => typeof v === 'number' && !Number.isNaN(v));

    // Determine quality (будет улучшено в observation builder)
    let quality: 'HIGH' | 'MEDIUM' | 'LOW' = 'LOW';

    if (perpTicks.length >= 2 && spreadBps < 20) {
      quality = 'HIGH';
    } else if (
      perpTicks.length >= 1 &&
      (validationTicks.length >= 1 || fallbackTicks.length >= 1) &&
      spreadBps < 35
    ) {
      quality = 'MEDIUM';
    } else {
      quality = 'LOW';
    }

    return {
      symbol,
      price: Number(weightedPrice.toFixed(6)),
      timestamp: Date.now(),
      providersUsed: valid.map((t) => t.providerId),
      priceSpreadBps: Number(spreadBps.toFixed(2)),
      fundingRate: fundingCandidates.length
        ? this.median(fundingCandidates)
        : null,
      openInterest: oiCandidates.length ? this.median(oiCandidates) : null,
      quality,
    };
  }

  /**
   * Weighted average - учитывает базовый вес провайдера и его health score
   */
  private weightedAverage(ticks: RawTick[]): number {
    let weightedSum = 0;
    let totalWeight = 0;

    for (const tick of ticks) {
      const baseWeight = BASE_WEIGHTS[tick.providerId] ?? 0.3;
      const health = providerHealthTracker.get(tick.providerId);
      const healthFactor = Math.max(0.1, health.score / 100);
      const weight = baseWeight * healthFactor;

      weightedSum += tick.price * weight;
      totalWeight += weight;
    }

    return totalWeight > 0 ? weightedSum / totalWeight : 0;
  }

  private median(values: number[]): number {
    if (!values.length) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);

    return sorted.length % 2 === 0
      ? (sorted[mid - 1] + sorted[mid]) / 2
      : sorted[mid];
  }
}
