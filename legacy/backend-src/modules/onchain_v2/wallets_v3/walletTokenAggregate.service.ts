/**
 * Wallet Token Aggregate Service — Phase C3.1
 * ==============================================
 * Reads pre-aggregated daily token buckets and returns
 * top tokens for a wallet in a given time window.
 *
 * Pipeline: $match → $group → $addFields → $sort → $limit
 * Data source: WalletTokenFlowBucketModel (bucket-based, no raw logs)
 */

import { WalletTokenFlowBucketModel } from './walletTokenFlowBucket.model';
import type { WindowKey, WalletTokenRow } from './contracts';

function windowToMs(w: WindowKey): number {
  if (w === '24h') return 24 * 3600_000;
  if (w === '7d') return 7 * 24 * 3600_000;
  return 30 * 24 * 3600_000;
}

const DEFAULT_LIMIT = 20;

export interface WalletTokensResult {
  ok: boolean;
  chainId: number;
  address: string;
  window: WindowKey;
  items: WalletTokenRow[];
  bucketed: boolean;
  bucketCount: number;
}

export async function getWalletTokens(params: {
  chainId: number;
  address: string;
  window: WindowKey;
  limit?: number;
}): Promise<WalletTokensResult> {
  const { chainId, window: win } = params;
  const address = params.address.toLowerCase();
  const limit = params.limit ?? DEFAULT_LIMIT;

  const cutoff = new Date(Date.now() - windowToMs(win));

  const pipeline = [
    // Stage 1: Match wallet + chain + time range
    {
      $match: {
        chainId,
        walletAddress: address,
        bucketTs: { $gte: cutoff },
      },
    },
    // Stage 2: Group by tokenAddress, sum metrics
    {
      $group: {
        _id: '$tokenAddress',
        tokenSymbol: { $first: '$tokenSymbol' },
        inUsd:    { $sum: '$inUsd' },
        outUsd:   { $sum: '$outUsd' },
        netUsd:   { $sum: '$netUsd' },
        transfers:{ $sum: '$transfers' },
        buckets:  { $sum: 1 },
      },
    },
    // Stage 3: Add absNet for sorting
    {
      $addFields: {
        absNet: { $abs: '$netUsd' },
      },
    },
    // Stage 4: Sort by absolute net USD descending
    { $sort: { absNet: -1 as const } },
    // Stage 5: Limit results
    { $limit: limit },
    // Stage 6: Project final shape
    {
      $project: {
        _id: 0,
        tokenAddress: '$_id',
        symbol: { $ifNull: ['$tokenSymbol', ''] },
        inUsd: 1,
        outUsd: 1,
        netUsd: 1,
        transfers: 1,
        priceUsd: { $literal: null },
      },
    },
  ];

  const results = await WalletTokenFlowBucketModel.aggregate(pipeline).allowDiskUse(true);

  // Count total buckets for diagnostics
  const bucketCount = await WalletTokenFlowBucketModel.countDocuments({
    chainId,
    walletAddress: address,
    bucketTs: { $gte: cutoff },
  });

  return {
    ok: true,
    chainId,
    address,
    window: win,
    items: results as WalletTokenRow[],
    bucketed: true,
    bucketCount,
  };
}
