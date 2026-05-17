/**
 * Market Series Model
 * ====================
 * 
 * PHASE 1: Liquidity & Alt Rotation Engine
 * 
 * Stores time-series for market-level metrics:
 * - PURE_ALT_CAP
 * - STABLE_SUPPLY_TOTAL
 * - STABLE_DOMINANCE
 * - ETHBTC_RATIO
 * - BTC_DOMINANCE_RAW
 */

import mongoose, { Schema, Document } from 'mongoose';

export interface IMarketSeries extends Document {
  chainId: number;
  key: string;
  t: number;
  value: number;
  meta?: {
    source?: string;
  };
}

const MarketSeriesSchema = new Schema<IMarketSeries>(
  {
    chainId: { type: Number, required: true, default: 1, index: true },
    key: { type: String, required: true, index: true },
    t: { type: Number, required: true, index: true },
    value: { type: Number, required: true },
    meta: {
      source: { type: String },
    },
  },
  {
    collection: 'onchain_v2_market_series',
    timestamps: false,
  }
);

// Compound unique index (chain-aware)
MarketSeriesSchema.index({ chainId: 1, key: 1, t: 1 }, { unique: true });

export const MarketSeriesModel = mongoose.model<IMarketSeries>(
  'OnchainV2MarketSeries',
  MarketSeriesSchema
);

// Series key constants
export const MARKET_SERIES_KEYS = {
  PURE_ALT_CAP: 'PURE_ALT_CAP',
  STABLE_SUPPLY_TOTAL: 'STABLE_SUPPLY_TOTAL',
  STABLE_DOMINANCE: 'STABLE_DOMINANCE',
  ETHBTC_RATIO: 'ETHBTC_RATIO',
  BTC_DOMINANCE_RAW: 'BTC_DOMINANCE_RAW',
} as const;

export type MarketSeriesKey = typeof MARKET_SERIES_KEYS[keyof typeof MARKET_SERIES_KEYS];

console.log('[Market] Model loaded: onchain_v2_market_series');
