/**
 * Wallet Snapshot Job — Phase C4
 * ================================
 * Periodically pre-computes and caches WalletProfileSnapshot for tracked wallets.
 * Also aggregates daily buckets (C2) for each tracked wallet.
 *
 * Tracked wallets come from:
 * 1. wallet_watchlist collection (manual additions)
 * 2. Recent profile lookups (auto-tracked)
 */

import mongoose from 'mongoose';
import { computeWalletProfile } from './walletProfileCompute.service';
import { aggregateWalletBuckets } from './walletBucketAggregate.service';
import { WalletSnapshotModel } from './walletSnapshot.model';
import { runPerChain } from '../system/runPerChain';
import type { WindowKey } from './contracts';

let running = false;
let lastRunAt: Date | null = null;
let lastError: string | null = null;
let tickCount = 0;
let successCount = 0;
let errorCount = 0;
let walletsProcessed = 0;

const WINDOWS: WindowKey[] = ['24h', '7d', '30d'];
const SNAPSHOT_TTL_MS = 30 * 60 * 1000; // 30 min
const MAX_WALLETS_PER_TICK = 20;

/**
 * Get wallets to track. Sources:
 * 1. wallet_watchlist collection
 * 2. Recent snapshot requests (from wallet_snapshots already)
 */
async function getTrackedWallets(chainId: number): Promise<string[]> {
  const addrs = new Set<string>();

  // Source 1: Watchlist
  try {
    const watchColl = mongoose.connection.collection('wallet_watchlist');
    const watchDocs = await watchColl.find({ chainId, active: { $ne: false } }).limit(100).toArray();
    for (const d of watchDocs) {
      const addr = String(d.address || '').toLowerCase();
      if (addr.length >= 10) addrs.add(addr);
    }
  } catch {}

  // Source 2: Previously cached snapshots (auto-refresh)
  try {
    const existing = await WalletSnapshotModel.find(
      { chainId },
      { address: 1, _id: 0 }
    ).limit(100).lean();
    for (const d of existing) {
      const addr = String((d as any).address || '').toLowerCase();
      if (addr.length >= 10) addrs.add(addr);
    }
  } catch {}

  return Array.from(addrs).slice(0, MAX_WALLETS_PER_TICK);
}

export async function runWalletSnapshotJob(): Promise<void> {
  if (running) {
    console.log('[WalletSnapshotJob] Already running, skipping');
    return;
  }
  running = true;
  tickCount++;
  walletsProcessed = 0;

  try {
    await runPerChain('WalletSnapshotJob', async (chainId) => {
      const wallets = await getTrackedWallets(chainId);

      if (wallets.length === 0) {
        console.log(`[WalletSnapshotJob] chain=${chainId}: No tracked wallets, skipping`);
        return;
      }

      console.log(`[WalletSnapshotJob] chain=${chainId}: Processing ${wallets.length} wallets...`);

      for (const address of wallets) {
        try {
          // C2: Aggregate daily buckets
          await aggregateWalletBuckets({ chainId, address, days: 30 });

          // C4: Compute and cache snapshots for each window
          for (const win of WINDOWS) {
            const snapshot = await computeWalletProfile({ chainId, address, window: win });
            const now = new Date();

            await WalletSnapshotModel.updateOne(
              { chainId, address, window: win },
              {
                $set: {
                  snapshot,
                  computedAt: now,
                  expiresAt: new Date(now.getTime() + SNAPSHOT_TTL_MS),
                  source: 'job',
                },
              },
              { upsert: true }
            );
          }

          walletsProcessed++;
        } catch (err: any) {
          console.error(`[WalletSnapshotJob] chain=${chainId} Failed for ${address.slice(0, 10)}:`, err?.message);
        }
      }
    });

    successCount++;
    lastRunAt = new Date();
    lastError = null;
    console.log(`[WalletSnapshotJob] Done: ${walletsProcessed} wallets processed`);
  } catch (e: any) {
    errorCount++;
    lastError = String(e?.message || e);
    console.error('[WalletSnapshotJob] Failed:', lastError);
  } finally {
    running = false;
  }
}

export function getWalletSnapshotJobStatus() {
  return {
    running,
    tickCount,
    successCount,
    errorCount,
    walletsProcessed,
    lastRunAt: lastRunAt?.toISOString() ?? null,
    lastError,
  };
}

export function isWalletSnapshotJobRunning(): boolean {
  return running;
}

export async function forceWalletSnapshotTick() {
  await runWalletSnapshotJob();
  return getWalletSnapshotJobStatus();
}

/**
 * Track a wallet for snapshot pre-computation.
 * Called when a user requests a profile on-demand.
 */
export async function trackWalletForSnapshots(chainId: number, address: string): Promise<void> {
  try {
    const watchColl = mongoose.connection.collection('wallet_watchlist');
    await watchColl.updateOne(
      { chainId, address: address.toLowerCase() },
      {
        $set: {
          chainId,
          address: address.toLowerCase(),
          active: true,
          trackedAt: new Date(),
        },
        $setOnInsert: { source: 'auto' },
      },
      { upsert: true }
    );
  } catch {}
}
