/**
 * Wallet Counterparty Aggregate Service — Phase C3.2
 * =====================================================
 * Reads pre-aggregated daily counterparty buckets and returns
 * top counterparties for a wallet in a given time window.
 *
 * Pipeline: $match → $group → $addFields → $sort → $limit
 * Data source: WalletCounterpartyFlowBucketModel (bucket-based, no raw logs)
 */

import { WalletCounterpartyFlowBucketModel } from './walletCounterpartyFlowBucket.model';
import type { WindowKey, WalletCounterpartyRow } from './contracts';

function windowToMs(w: WindowKey): number {
  if (w === '24h') return 24 * 3600_000;
  if (w === '7d') return 7 * 24 * 3600_000;
  return 30 * 24 * 3600_000;
}

const DEFAULT_LIMIT = 20;

export interface WalletCounterpartiesResult {
  ok: boolean;
  chainId: number;
  address: string;
  window: WindowKey;
  items: WalletCounterpartyRow[];
  bucketed: boolean;
  bucketCount: number;
}

export async function getWalletCounterparties(params: {
  chainId: number;
  address: string;
  window: WindowKey;
  limit?: number;
}): Promise<WalletCounterpartiesResult> {
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
    // Stage 2: Group by counterpartyAddress, sum metrics
    {
      $group: {
        _id: '$counterpartyAddress',
        entityId:   { $first: '$entityId' },
        entityName: { $first: '$entityName' },
        entityType: { $first: '$entityType' },
        inUsd:      { $sum: '$inUsd' },
        outUsd:     { $sum: '$outUsd' },
        netUsd:     { $sum: '$netUsd' },
        transfers:  { $sum: '$transfers' },
        buckets:    { $sum: 1 },
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
        address: '$_id',
        inUsd: 1,
        outUsd: 1,
        netUsd: 1,
        transfers: 1,
        attribution: {
          entityId:   '$entityId',
          entityName: '$entityName',
          entityType: '$entityType',
          source: {
            $cond: [
              { $ne: ['$entityId', null] },
              'LABEL_V2',
              'NONE',
            ],
          },
          confidence: {
            $cond: [
              { $ne: ['$entityId', null] },
              0.9,
              0,
            ],
          },
          evidence: { $literal: [] },
        },
      },
    },
  ];

  const results = await WalletCounterpartyFlowBucketModel.aggregate(pipeline).allowDiskUse(true);

  const bucketCount = await WalletCounterpartyFlowBucketModel.countDocuments({
    chainId,
    walletAddress: address,
    bucketTs: { $gte: cutoff },
  });

  return {
    ok: true,
    chainId,
    address,
    window: win,
    items: results as WalletCounterpartyRow[],
    bucketed: true,
    bucketCount,
  };
}
