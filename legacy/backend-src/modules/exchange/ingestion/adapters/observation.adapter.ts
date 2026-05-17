/**
 * Observation Adapter - Converts new ingestion system to legacy observation format
 */
import type { AggregatedTick } from '../types/market-data.js';

export interface CreateObservationInput {
  symbol: string;
  market: {
    price: number;
    priceChange5m?: number;
    priceChange15m?: number;
    volatility?: number;
  };
  openInterest?: {
    value: number;
    delta?: number;
    deltaPct?: number;
  };
  patterns?: any[];
  source?: string;
  metadata?: {
    providersUsed?: string[];
    priceSpreadBps?: number;
    quality?: string;
    providerCount?: number;
  };
}

/**
 * Convert AggregatedTick to CreateObservationInput
 */
export function aggregatedTickToObservationInput(
  tick: AggregatedTick
): CreateObservationInput {
  return {
    symbol: tick.symbol,
    market: {
      price: tick.price,
      priceChange5m: 0,
      priceChange15m: 0,
      volatility: 0,
    },
    openInterest: tick.openInterest
      ? {
          value: tick.openInterest,
          delta: 0,
          deltaPct: 0,
        }
      : undefined,
    patterns: [],
    source: 'multi_provider_ingestion',
    metadata: {
      providersUsed: tick.providersUsed,
      priceSpreadBps: tick.priceSpreadBps,
      quality: tick.quality,
      providerCount: tick.providersUsed.length,
    },
  };
}
