/**
 * Token Series Aggregate Service — Phase D3
 * ============================================
 * Reads TokenFlowModel and aggregates into TokenFlowBucketModel.
 * Bucket sizes: 1h (24h), 6h (7d), 1d (30d).
 */

import mongoose from 'mongoose';
import { TokenFlowModel } from '../flow/flow.model';
import { TokenFlowBucketModel } from './tokenFlowBucket.model';
import { tokenMetaService } from '../flow/tokenMeta.service';
import { getUniverseAddresses } from '../flow/tokenUniverse';

type WindowKey = '24h' | '7d' | '30d';

interface BucketConfig {
  window: WindowKey;
  bucketSizeMs: number;
  lookbackMs: number;
}

const CONFIGS: BucketConfig[] = [
  { window: '24h', bucketSizeMs: 3600_000,       lookbackMs: 24 * 3600_000 },     // 1h buckets
  { window: '7d',  bucketSizeMs: 6 * 3600_000,   lookbackMs: 7 * 24 * 3600_000 }, // 6h buckets
  { window: '30d', bucketSizeMs: 24 * 3600_000,   lookbackMs: 30 * 24 * 3600_000 }, // 1d buckets
];

function floorTs(ts: number, bucketMs: number): number {
  return Math.floor(ts / bucketMs) * bucketMs;
}

/**
 * Aggregate buckets for a single token + window.
 */
async function aggregateTokenWindow(params: {
  chainId: number;
  tokenAddress: string;
  tokenSymbol: string;
  config: BucketConfig;
}): Promise<number> {
  const { chainId, tokenAddress, config } = params;
  const cutoff = Date.now() - config.lookbackMs;

  // Read flows
  const flows = await TokenFlowModel.find({
    chainId,
    tokenAddress,
    blockTime: { $gte: cutoff },
  }).lean() as any[];

  if (flows.length === 0) return 0;

  // Aggregate by bucket
  const bucketMap = new Map<number, {
    inflowUsd: number;
    outflowUsd: number;
    netUsd: number;
    transfers: number;
    wallets: Set<string>;
  }>();

  for (const f of flows) {
    const bts = floorTs(f.blockTime, config.bucketSizeMs);
    if (!bucketMap.has(bts)) {
      bucketMap.set(bts, { inflowUsd: 0, outflowUsd: 0, netUsd: 0, transfers: 0, wallets: new Set() });
    }
    const b = bucketMap.get(bts)!;
    const usd = Math.abs(f.usdVolume || 0);

    if (f.side === 'BUY') {
      b.inflowUsd += usd;
      b.netUsd += usd;
    } else {
      b.outflowUsd += usd;
      b.netUsd -= usd;
    }
    b.transfers++;
    if (f.counterparty) b.wallets.add(f.counterparty);
  }

  // Upsert
  const ops = [];
  for (const [bts, acc] of bucketMap) {
    ops.push({
      updateOne: {
        filter: { chainId, tokenAddress, window: config.window, bucketTs: new Date(bts) },
        update: {
          $set: {
            chainId,
            tokenAddress,
            tokenSymbol: params.tokenSymbol,
            window: config.window,
            bucketTs: new Date(bts),
            inflowUsd: acc.inflowUsd,
            outflowUsd: acc.outflowUsd,
            netUsd: acc.netUsd,
            transfers: acc.transfers,
            uniqueWallets: acc.wallets.size,
            computedAt: new Date(),
          },
        },
        upsert: true,
      },
    });
  }

  if (ops.length > 0) {
    await TokenFlowBucketModel.bulkWrite(ops);
  }

  return ops.length;
}

/**
 * Aggregate all windows for a token.
 */
export async function aggregateTokenBuckets(chainId: number, tokenAddress: string): Promise<{ total: number; elapsed: number }> {
  const start = Date.now();
  const meta = await tokenMetaService.get(chainId, tokenAddress);
  let total = 0;

  for (const config of CONFIGS) {
    total += await aggregateTokenWindow({
      chainId,
      tokenAddress: tokenAddress.toLowerCase(),
      tokenSymbol: meta?.symbol || '',
      config,
    });
  }

  return { total, elapsed: Date.now() - start };
}

/**
 * Read pre-computed series for a token.
 */
export async function readTokenSeries(params: {
  chainId: number;
  tokenAddress: string;
  window: WindowKey;
}): Promise<{
  buckets: Array<{
    ts: string;
    inflowUsd: number;
    outflowUsd: number;
    netUsd: number;
    transfers: number;
    uniqueWallets: number;
  }>;
  stale: boolean;
}> {
  const { chainId, tokenAddress, window: win } = params;
  const config = CONFIGS.find(c => c.window === win) || CONFIGS[1];
  const cutoff = new Date(Date.now() - config.lookbackMs);

  const buckets = await TokenFlowBucketModel.find(
    { chainId, tokenAddress: tokenAddress.toLowerCase(), window: win, bucketTs: { $gte: cutoff } },
    { _id: 0, bucketTs: 1, inflowUsd: 1, outflowUsd: 1, netUsd: 1, transfers: 1, uniqueWallets: 1, computedAt: 1 }
  ).sort({ bucketTs: 1 }).lean() as any[];

  // Check staleness
  let stale = false;
  if (buckets.length > 0) {
    const lastComputed = buckets[buckets.length - 1].computedAt;
    if (lastComputed && Date.now() - new Date(lastComputed).getTime() > 30 * 60_000) {
      stale = true;
    }
  }

  return {
    buckets: buckets.map((b: any) => ({
      ts: new Date(b.bucketTs).toISOString(),
      inflowUsd: b.inflowUsd || 0,
      outflowUsd: b.outflowUsd || 0,
      netUsd: b.netUsd || 0,
      transfers: b.transfers || 0,
      uniqueWallets: b.uniqueWallets || 0,
    })),
    stale,
  };
}

/**
 * Get active tokens for aggregation (from universe).
 */
export function getActiveTokens(chainId: number): string[] {
  return getUniverseAddresses(chainId);
}
