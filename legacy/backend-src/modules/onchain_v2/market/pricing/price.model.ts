/**
 * OnChain V2 — Token Price Model
 * ================================
 * 
 * STEP 1: USD Valuation Layer
 * MongoDB model for caching token USD prices.
 */

import mongoose, { Schema, Document } from 'mongoose';
import type { PriceSource } from './pricing.types';

export interface ITokenUsdPrice extends Document {
  chainId: number;
  token: string;
  priceUsd: number;
  confidence: number;
  source: PriceSource;
  updatedAt: number;
  meta?: Record<string, unknown>;
}

const TokenUsdPriceSchema = new Schema<ITokenUsdPrice>({
  chainId: { type: Number, required: true, index: true },
  token: { type: String, required: true, lowercase: true, index: true },
  priceUsd: { type: Number, required: true },
  confidence: { type: Number, required: true, min: 0, max: 1 },
  source: { 
    type: String, 
    required: true, 
    enum: ['CHAINLINK', 'UNIV3_TWAP', 'DEX_VWAP'] 
  },
  updatedAt: { type: Number, required: true },
  meta: { type: Schema.Types.Mixed },
}, {
  collection: 'onchain_v2_token_prices',
  timestamps: false,
});

TokenUsdPriceSchema.index({ chainId: 1, token: 1 }, { unique: true });
TokenUsdPriceSchema.index({ updatedAt: -1 });

export const TokenUsdPriceModel = mongoose.model<ITokenUsdPrice>(
  'OnchainV2TokenUsdPrice',
  TokenUsdPriceSchema
);

console.log('[OnChain V2] Token USD Price Model loaded');
