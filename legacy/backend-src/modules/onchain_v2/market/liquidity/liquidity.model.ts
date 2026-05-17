/**
 * LiquidityScore Model
 * =====================
 * 
 * PHASE 2.1: Persistent storage for liquidity series
 * 
 * Collection: onchain_v2_liquidity_series
 */

import mongoose, { Schema, Document } from 'mongoose';
import { LiquidityRegime } from './contracts';

export interface ILiquiditySeries extends Document {
  chainId: number;
  t: number;              // bucketTime (10m aligned)
  score: number;          // 0-100
  confidence: number;     // 0-1
  regime: string;         // LiquidityRegime enum value
  flags: string[];        // Flag codes
  drivers: string[];      // Driver strings
}

const LiquiditySeriesSchema = new Schema<ILiquiditySeries>(
  {
    chainId: { type: Number, required: true, default: 1, index: true },
    t: { type: Number, required: true, index: true },
    score: { type: Number, required: true, min: 0, max: 100 },
    confidence: { type: Number, required: true, min: 0, max: 1 },
    regime: { 
      type: String, 
      required: true,
      enum: Object.values(LiquidityRegime),
      default: LiquidityRegime.NEUTRAL,
    },
    flags: [{ type: String }],
    drivers: [{ type: String }],
  },
  {
    collection: 'onchain_v2_liquidity_series',
    timestamps: false,
  }
);

// Chain-aware unique index
LiquiditySeriesSchema.index({ chainId: 1, t: 1 }, { unique: true });

export const LiquiditySeriesModel = mongoose.model<ILiquiditySeries>(
  'OnchainV2LiquiditySeries',
  LiquiditySeriesSchema
);

/**
 * Align timestamp to 10-minute bucket
 */
export function bucket10m(ts: number): number {
  const BUCKET_MS = 10 * 60 * 1000; // 10 minutes
  return Math.floor(ts / BUCKET_MS) * BUCKET_MS;
}

console.log('[Liquidity] Model loaded: onchain_v2_liquidity_series');
